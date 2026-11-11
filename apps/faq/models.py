from django.db import models


class FAQItem(models.Model):
    """Tez-tez so'raladigan savol va javob. Mijozlar ro'yxatni ko'radi, AI agent ham shundan javob beradi (RAG)."""

    shop = models.ForeignKey("shops.Shop", on_delete=models.CASCADE, related_name="faq_items")
    question = models.CharField(max_length=300)
    answer = models.TextField()
    position = models.PositiveSmallIntegerField(default=0, help_text="Kichik raqam yuqorida ko'rinadi")
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["shop_id", "position", "id"]

    def __str__(self):
        return f"{self.shop.name}: {self.question[:60]}"
    