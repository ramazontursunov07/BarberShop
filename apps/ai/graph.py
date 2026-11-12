"""LangGraph: sartaroshxona yordamchisi.

            START
              |
           [router]  -- LLM: savol qaysi turda?
            /     \\
        info       booking
          |           |
     [retrieve]   [booking_agent] <--> [tools]   (tool calling sikli)
          |           |
     [answer_info]   END
          |
         END

info    : qoidalar/sharhlar savollari. Ma'lumot HAR DOIM avval qidiriladi (RAG), keyin javob yoziladi.
booking : bron jarayoni. LLM tool'larni o'zi tanlaydi (bo'sh vaqt, bron yaratish va h.k.).
"""
from datetime import date

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.errors import GraphRecursionError
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

from . import rag
from .confirmation import REJECT_MESSAGE, is_confirmation, needs_confirmation
from .gemini_compat import add_thought_signature_bypass, is_gemini_endpoint
from .graph_utils import (
    EMPTY_NUDGE, fallback_reply, flatten_content, invoke_nonempty, last_user_text, make_query, parse_route,
    transcript,
)
from .lc_tools import make_tools
from .llm import conf

# Graf cheksiz aylanib ketmasligi uchun. Bron oqimi (qidiruv + tasdiq + yaratish) 5-6 tool chaqiruvi talab qilishi
# mumkin, har biri 2 qadam, shuning uchun 12 yetmaydi (book_flow_ru shu sabab yiqilgan).
RECURSION_LIMIT = 24

ROUTER_PROMPT = (
    "Sen yo'naltiruvchisan. Mijozning oxirgi xabari qaysi turga kirishini aniqla va "
    "FAQAT bitta so'z yoz: info yoki booking.\n"
    "info: sartaroshxona qoidalari (bekor qilish, kechikish, to'lov), qulayliklar, aksiyalar, "
    "usta haqida ma'lumot yoki mijoz sharhlari haqidagi savol.\n"
    "booking: bron qilish, bronni bekor qilish, mening bronlarim, bo'sh vaqt, xizmatlar va narxlar, sartaroshxonalar yoki ustalar ro'yxati, "
    "bronni tasdiqlash ('ha', 'tasdiqlayman'), salomlashish va boshqa hamma narsa.\n"
    "Agar mijoz bron jarayonining o'rtasida bo'lsa (vaqt, usta yoki tasdiq haqida gapirsa), booking de."
)

INFO_PROMPT = (
    "Sen sartaroshxona yordamchisisan. Mijoz bilan o'zbek tilida (u rus tilida yozsa, rus tilida) "
    "muloqot qil. Savolga FAQAT quyidagi KONTEKSTga tayanib javob ber. Kontekstda javob bo'lmasa, "
    "'Bu haqda ma'lumotim yo'q' de, hech narsani taxmin qilma va bron qilishni taklif qil. "
    "Javob qisqa va xushmuomala bo'lsin.\n\nKONTEKST:\n{context}"
)


def _booking_prompt() -> str:
    today = date.today()
    return (
        "Sen sartaroshxonalar uchun bron qilish yordamchisisan. "
        "Foydalanuvchi bilan o'zbek tilida (u rus tilida yozsa, rus tilida) muloqot qil. "
        f"Bugungi sana: {today.isoformat()} ({today.strftime('%A')}). "
        "'Ertaga', 'dushanba kuni' kabi so'zlarni aniq sanaga aylantir.\n"
        "Qoidalar:\n"
        "1. ID larni o'zing o'ylab topma, faqat tool natijalaridan ol.\n"
        "2. Narx va davomiylik uchun list_services, ustalar uchun list_masters ni ishlat.\n"
        "3. Qoidalar, qulayliklar va sharhlar haqidagi savollarga faqat search_shop_info natijasiga tayanib javob ber.\n"
        "4. Bo'sh vaqtlarni faqat get_available_slots yoki find_best_slots orqali tekshir.\n"
        "5. create_booking ni FAQAT shu tartibda chaqir: (a) usta, xizmat, sana va vaqt aniq; "
        "(b) bo'sh vaqtni tool bilan tekshirgansan; (c) mijozga xulosa yozib tasdiq so'ragansan, masalan: "
        "'Jasur, Soch olish, ertaga 10:00, 50 000 so'm. Tasdiqlaysizmi?'; (d) mijoz KEYINGI xabarida aniq "
        "'ha' yoki 'tasdiqlayman' degan. Mijozning dastlabki 'yozib qo'ying' so'rovi tasdiq HISOBLANMAYDI: "
        "avval xulosa yozib so'ra. Mijoz vaqt yoki ustani o'zgartirsa, yangi xulosa yozib, qayta tasdiqlat.\n"
        "6. Mijoz noaniq vaqt aytsa ('ertaga kechqurun', 'ertalab', 'soat 3 atrofida') yoki usta aytmasa, "
        "find_best_slots ni ishlat. Natijadan 2-3 ta eng mos vaqtni taklif qil. Agar natijadagi sana "
        "so'ralgan sanadan farq qilsa, buni mijozga aniq ayt. Bo'sh vaqt topilmasa, boshqa kun yoki "
        "vaqtni taklif qil.\n"
        "7. Mijozning bronlarini my_bookings orqali ko'rsat. Bronni bekor qilishdan oldin my_bookings dan id ni ol "
        "va qaysi bronni bekor qilishni mijozdan aniq tasdiqlat, keyin cancel_booking ni chaqir.\n"
        "8. Javob tili: mijozning OXIRGI xabari qaysi tilda bo'lsa, shu tilda yoz (tool natijalari "
        "o'zbekcha bo'lsa ham). Rus tilida yozgan mijozga faqat rus tilida javob ber.\n"
        "9. Mijoz 'odatdagidek', 'yana o'sha ustaga' desa yoki nima qilishni bilmasa, my_recommendations ni chaqir "
        "va tarixiga mos usta/xizmatni taklif qil (masalan: \"O'tgan safar fade qildirgansiz, shu ustaga yana yozilamizmi?\").\n"
        "10. Narxni faqat tool natijasidan ayt. Natijada discount_percent > 0 bo'lsa, mijozga chegirma borligini ayt.\n"
        "11. Bir tashrifda bir nechta xizmat (soch + soqol) so'ralsa, asosiy xizmatni service_id ga, qolganini "
        "extra_service_ids ga ber; slot va narx umumiy davomiylik/narx bo'yicha hisoblanadi.\n"
        "12. Bronni boshqa vaqtga ko'chirish so'ralsa my_bookings -> yangi vaqtni tekshir -> tasdiq so'ra -> reschedule_booking. "
        "Bekor qilib qayta bron qilma.\n"
        "13. Kerakli kunda bo'sh vaqt bo'lmasa, mijozga kutish ro'yxatini taklif qil (join_waitlist). "
        "'Qancha tushadi', 'promokod ishlaydimi' savollariga quote_price bilan javob ber.\n"
        "14. 'Hoziroq kelaman', 'navbat bormi' desa join_queue (avval tasdiq), 'navbatim qachon' desa queue_status. "
        "'Har 2 haftada shu soatga' desa create_recurring_booking (avval tasdiq).\n"
        "Javoblar qisqa va xushmuomala bo'lsin."
    )


class State(MessagesState):
    route: str
    context: str


class _GeminiChatOpenAI(ChatOpenAI):
    """Gemini 3 (OpenAI-mos rejim): tool chaqiruvlariga thought_signature qo'shadi (gemini_compat.py ga qarang)."""

    def _get_request_payload(self, *args, **kwargs):
        payload = super()._get_request_payload(*args, **kwargs)
        add_thought_signature_bypass(payload.get("messages", []))
        return payload


def _llm() -> ChatOpenAI:
    base_url = conf("LLM_BASE_URL", "https://api.groq.com/openai/v1")
    # Moslashtirish faqat Gemini endpointi uchun: boshqa provayderlar nostandart maydonni rad etishi mumkin
    use_gemini_fix = is_gemini_endpoint(base_url) and hasattr(ChatOpenAI, "_get_request_payload")
    llm_class = _GeminiChatOpenAI if use_gemini_fix else ChatOpenAI
    return llm_class(
        model=conf("LLM_MODEL", "llama-3.3-70b-versatile"),
        api_key=conf("LLM_API_KEY"),
        base_url=base_url,
        temperature=0,
        max_tokens=1000,
        timeout=60,
    )


def build_graph(user):
    llm = _llm()
    tools = make_tools(user)
    llm_with_tools = llm.bind_tools(tools)

    def router(state: State) -> dict:
        convo = transcript(state["messages"], limit=6)
        resp = llm.invoke([SystemMessage(content=ROUTER_PROMPT), HumanMessage(content=convo)])
        return {"route": parse_route(flatten_content(resp.content))}

    def retrieve(state: State) -> dict:
        found = rag.search_shop_info(query=make_query(state["messages"]))
        chunks = found.get("results", [])
        return {"context": "\n\n".join(f"- {c['text']}" for c in chunks)}

    def answer_info(state: State) -> dict:
        context = state.get("context") or "(hech narsa topilmadi)"
        system = INFO_PROMPT.replace("{context}", context)
        resp = llm.invoke([SystemMessage(content=system), *state["messages"]])
        return {"messages": [resp]}

    def booking_agent(state: State) -> dict:
        messages = [SystemMessage(content=_booking_prompt()), *state["messages"]]
        resp = invoke_nonempty(llm_with_tools.invoke, messages, HumanMessage(content=EMPTY_NUDGE))
        return {"messages": [resp]}

    guard_on = conf("AI_CONFIRM_GUARD", "on").strip().lower() != "off"  # "off": faqat tajriba (A/B) uchun

    def route_after_agent(state: State) -> str:
        """Tool so'ralmagan bo'lsa tugaydi; bron/bekor qilish so'ralsa va mijoz tasdiqlamagan bo'lsa, rad etiladi."""
        calls = getattr(state["messages"][-1], "tool_calls", None) or []
        if not calls:
            return END
        if guard_on and needs_confirmation(calls) and not is_confirmation(last_user_text(state["messages"])):
            return "reject"
        return "tools"

    def reject(state: State) -> dict:
        """Tasdiqsiz bron/bekor qilishni bajarmaydi: har bir tool chaqiruviga rad javobini qaytaradi."""
        calls = state["messages"][-1].tool_calls
        return {"messages": [
            ToolMessage(content=REJECT_MESSAGE, tool_call_id=call["id"], name=call["name"]) for call in calls
        ]}

    graph = StateGraph(State)
    graph.add_node("router", router)
    graph.add_node("retrieve", retrieve)
    graph.add_node("answer_info", answer_info)
    graph.add_node("booking_agent", booking_agent)
    graph.add_node("tools", ToolNode(tools))
    graph.add_node("reject", reject)

    graph.add_edge(START, "router")
    graph.add_conditional_edges(
        "router", lambda state: state["route"], {"info": "retrieve", "booking": "booking_agent"}
    )
    graph.add_edge("retrieve", "answer_info")
    graph.add_edge("answer_info", END)
    graph.add_conditional_edges(
        "booking_agent", route_after_agent, {"tools": "tools", "reject": "reject", END: END}
    )
    graph.add_edge("tools", "booking_agent")
    graph.add_edge("reject", "booking_agent")  # model rad javobini ko'rib, mijozdan tasdiq so'raydi
    return graph.compile()


def _history_to_messages(history: list[dict] | None) -> list:
    messages = []
    for item in history or []:
        if item["role"] == "user":
            messages.append(HumanMessage(content=item["content"]))
        elif item["role"] == "assistant":
            messages.append(AIMessage(content=item["content"]))
    return messages


def run_graph(user, message: str, history: list[dict] | None = None) -> str:
    graph = build_graph(user)
    messages = _history_to_messages(history) + [HumanMessage(content=message)]
    try:
        result = graph.invoke({"messages": messages}, config={"recursion_limit": RECURSION_LIMIT})
    except GraphRecursionError:
        # Bron yaratilib ulgurgan bo'lishi mumkin: mijozga natijani tekshirishni aytamiz
        return fallback_reply(message, busy=True)
    reply = flatten_content(result["messages"][-1].content).strip()
    return reply or fallback_reply(message)
