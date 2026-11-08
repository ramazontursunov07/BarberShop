import anthropic
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from .agent import run_agent


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
            reply = run_agent(request.user, message, history)
        except anthropic.APIError:
            return Response(
                {"detail": "AI xizmati vaqtincha ishlamayapti"},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response({"reply": reply})
    