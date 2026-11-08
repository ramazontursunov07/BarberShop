import logging

from openai import OpenAIError, RateLimitError
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from .llm import conf

logger = logging.getLogger(__name__)


class AiChatThrottle(UserRateThrottle):
    scope = "ai_chat"
    rate = "20/min"  # LLM chaqiruvlari pul turadi


def _clean_history(raw) -> list[dict]:
    """Klientdan kelgan tarixni faqat oddiy matnli xabarlarga cheklaymiz."""
    cleaned = []
    if not isinstance(raw, list):
        return cleaned
    for item in raw[-20:]:
        if (
                isinstance(item, dict)
                and item.get("role") in ("user", "assistant")
                and isinstance(item.get("content"), str)
        ):
            cleaned.append({"role": item["role"], "content": item["content"][:2000]})
    return cleaned


def _get_runner():
    """AI_ENGINE=graph (LangGraph, standart) yoki AI_ENGINE=simple (qo'lda yozilgan sikl)."""
    if conf("AI_ENGINE", "graph") == "simple":
        from .agent import run_agent

        return run_agent
    from .graph import run_graph

    return run_graph


class ChatView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [AiChatThrottle]

    def post(self, request):
        message = (request.data.get("message") or "").strip()
        if not message:
            return Response({"detail": "message majburiy"}, status=status.HTTP_400_BAD_REQUEST)
        if len(message) > 1000:
            return Response({"detail": "Xabar juda uzun"}, status=status.HTTP_400_BAD_REQUEST)

        history = _clean_history(request.data.get("history"))

        try:
            reply = _get_runner()(request.user, message, history)
        except RateLimitError:
            # RateLimitError OpenAIError'ning ichida, shuning uchun u ALBATTA oldin turishi kerak
            logger.warning("LLM limiti tugadi")
            return Response(
                {"detail": "AI limiti tugadi, keyinroq urinib ko'ring"},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        except OpenAIError as exc:
            # Provayderning haqiqiy javobini logga yozamiz (kalit bu yerda chiqmaydi)
            logger.exception(
                "LLM provayderi xatosi: %s | body=%s",
                getattr(exc, "message", exc),
                getattr(exc, "body", None),
            )
            return Response(
                {"detail": "AI xizmati vaqtincha ishlamayapti"},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except Exception:
            logger.exception("AI agentida kutilmagan xato")
            return Response(
                {"detail": "AI yordamchida ichki xato yuz berdi"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response({"reply": reply})
