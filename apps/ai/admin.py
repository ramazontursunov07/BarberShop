from django.contrib import admin

from .models import KnowledgeDocument


@admin.register(KnowledgeDocument)
class KnowledgeDocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "shop", "is_active", "updated_at")
    list_filter = ("shop", "is_active")
    search_fields = ("title", "content")
