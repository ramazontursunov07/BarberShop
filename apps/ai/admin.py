from django.contrib import admin

from .models import ChatTrace, KnowledgeDocument, LLMCall


@admin.register(KnowledgeDocument)
class KnowledgeDocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "shop", "is_active", "updated_at")
    list_filter = ("shop", "is_active")
    search_fields = ("title", "content")


@admin.register(ChatTrace)
class ChatTraceAdmin(admin.ModelAdmin):
    list_display = ("created_at", "engine", "route", "outcome", "latency_ms", "llm_calls", "prompt_tokens",
                    "completion_tokens", "guard_rejections", "tag")
    list_filter = ("engine", "route", "outcome")
    date_hierarchy = "created_at"


@admin.register(LLMCall)
class LLMCallAdmin(admin.ModelAdmin):
    list_display = ("created_at", "kind", "node", "model", "latency_ms", "prompt_tokens", "completion_tokens", "status")
    list_filter = ("kind", "node", "status")
