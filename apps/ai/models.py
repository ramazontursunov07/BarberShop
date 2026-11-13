from django.conf import settings
from django.db import models
from django.db.models import Q


class KnowledgeDocument(models.Model):
    """Sartaroshxona egasi yozadigan qoidalar va ma'lumotlar (RAG manbasi)."""

    shop = models.ForeignKey("shops.Shop", on_delete=models.CASCADE, related_name="knowledge_docs")
    title = models.CharField(max_length=200)
    content = models.TextField(help_text="Qoida, aksiya yoki mijozlar tez-tez so'raydigan savolga javob")
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["shop_id", "title"]

    def __str__(self):
        return f"{self.shop.name}: {self.title}"


class Notification(models.Model):
    """Mijozga yuborilgan avtomatik xabarlar jurnali (takror yubormaslik uchun)."""

    class Kind(models.TextChoices):
        REMINDER = "reminder", "Bron eslatmasi"
        WINBACK = "winback", "Mijozni qaytarish"
        RISK_REMINDER = "risk24h", "Xavfli bron: erta eslatma"
        REVIEW_REQUEST = "review", "Sharh so'rovi"
        DAY_OFF = "dayoff", "Usta dam olish kuni: mijozga xabar"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    booking = models.ForeignKey("bookings.Booking", null=True, blank=True, on_delete=models.CASCADE,
                                related_name="notifications")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # Bitta bronga bitta turdagi xabar faqat bir marta
            models.UniqueConstraint(
                fields=["booking", "kind"], condition=Q(booking__isnull=False), name="unique_booking_notification"
            ),
        ]

    def __str__(self):
        return f"{self.kind} -> {self.user_id}"


class ChatTrace(models.Model):
    """Bitta chat so'rovining o'lchovlari (AI kuzatuvi). Matn saqlanmaydi, faqat raqamlar."""

    trace_id = models.CharField(max_length=32, unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                             related_name="ai_traces")
    engine = models.CharField(max_length=10)                   # graph | simple
    route = models.CharField(max_length=10, blank=True)        # info | booking (graph)
    tag = models.CharField(max_length=60, blank=True, db_index=True)  # "" = haqiqiy so'rov, "eval:..." = baholash
    outcome = models.CharField(max_length=20, default="ok")    # ok | empty_reply | recursion_limit | rate_limited | error
    latency_ms = models.PositiveIntegerField(default=0)
    llm_calls = models.PositiveSmallIntegerField(default=0)
    prompt_tokens = models.PositiveIntegerField(default=0)
    completion_tokens = models.PositiveIntegerField(default=0)
    tool_names = models.JSONField(default=list)                # bajarilgan tool'lar
    guard_rejections = models.PositiveSmallIntegerField(default=0)  # tasdiqsiz bron urinishlari
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.engine}/{self.route} {self.outcome} {self.latency_ms} ms"


class LLMCall(models.Model):
    """Bitta LLM (yoki embedding / ovoz / rasm) chaqiruvi. trace bo'sh bo'lsa, chat'dan tashqari chaqiruv."""

    trace = models.ForeignKey(ChatTrace, null=True, blank=True, on_delete=models.CASCADE, related_name="calls")
    kind = models.CharField(max_length=12)                     # chat | insights | vision | stt | embedding
    node = models.CharField(max_length=30, blank=True)
    model = models.CharField(max_length=80, blank=True)
    latency_ms = models.PositiveIntegerField(default=0)
    prompt_tokens = models.PositiveIntegerField(default=0)
    completion_tokens = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=12, default="ok")     # ok | rate_limited | error
    error_type = models.CharField(max_length=60, blank=True)
    tool_calls = models.JSONField(default=list)                # model so'ragan tool nomlari
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
