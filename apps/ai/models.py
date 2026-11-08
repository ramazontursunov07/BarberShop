from django.db import models


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
