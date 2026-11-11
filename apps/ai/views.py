import logging

from openai import OpenAIError, RateLimitError
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from apps.shops.models import Shop
from apps.shops.permissions import IsOwnerRole

from .llm import conf
from .review_insights import InsightsError, analyze_shop_reviews
from .speech import MAX_AUDIO_BYTES, EmptyTranscript, SpeechNotConfigured, transcribe

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


class AiInsightsThrottle(UserRateThrottle):
    scope = "ai_insights"
    rate = "10/min"


class ReviewInsightsView(APIView):
    """Egasiga o'z sartaroshxonasi sharhlari tahlili: GET /api/ai/review-insights/?shop=<id>"""

    permission_classes = [IsAuthenticated, IsOwnerRole]
    throttle_classes = [AiInsightsThrottle]

    def get(self, request):
        try:
            shop_id = int(request.query_params.get("shop", ""))
        except ValueError:
            return Response({"detail": "shop majburiy (son)"}, status=status.HTTP_400_BAD_REQUEST)
        # Faqat o'z sartaroshxonasi: boshqaning sartaroshxonasi 404 beradi (mavjudligi ham sezilmaydi)
        shop = Shop.objects.filter(id=shop_id, owner=request.user).first()
        if shop is None:
            return Response({"detail": "Sartaroshxona topilmadi"}, status=status.HTTP_404_NOT_FOUND)
        try:
            return Response(analyze_shop_reviews(shop))
        except RateLimitError:
            logger.warning("LLM limiti tugadi (sharhlar tahlili)")
            return Response({"detail": "AI limiti tugadi, keyinroq urinib ko'ring"},
                            status=status.HTTP_429_TOO_MANY_REQUESTS)
        except (OpenAIError, InsightsError):
            logger.exception("Sharhlar tahlilida xato")
            return Response({"detail": "Tahlilni hozir tayyorlab bo'lmadi"},
                            status=status.HTTP_502_BAD_GATEWAY)


class AiTranscribeThrottle(UserRateThrottle):
    scope = "ai_transcribe"
    rate = "20/min"


class TranscribeView(APIView):
    """Ovozli xabarni matnga aylantiradi: POST multipart, maydon nomi `audio`. Javob: {"text": "..."}"""

    permission_classes = [IsAuthenticated]
    throttle_classes = [AiTranscribeThrottle]
    parser_classes = [MultiPartParser]

    def post(self, request):
        audio = request.FILES.get("audio")
        if audio is None or audio.size == 0:
            return Response({"detail": "audio fayli majburiy"}, status=status.HTTP_400_BAD_REQUEST)
        if audio.size > MAX_AUDIO_BYTES:
            return Response({"detail": "Ovozli xabar juda katta"}, status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
        try:
            text = transcribe(audio.read(), audio.name)
        except SpeechNotConfigured:
            return Response({"detail": "Ovozli xabarlar sozlanmagan"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except EmptyTranscript:
            return Response({"detail": "Ovozni tushunib bo'lmadi"}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        except RateLimitError:
            logger.warning("STT limiti tugadi")
            return Response({"detail": "AI limiti tugadi, keyinroq urinib ko'ring"},
                            status=status.HTTP_429_TOO_MANY_REQUESTS)
        except OpenAIError as exc:
            logger.error("STT provayderi xatosi: %s", getattr(exc, "message", exc))
            return Response({"detail": "Ovozni matnga aylantirib bo'lmadi"}, status=status.HTTP_502_BAD_GATEWAY)
        return Response({"text": text})
