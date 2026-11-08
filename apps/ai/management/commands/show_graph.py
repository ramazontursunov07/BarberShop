"""Graf sxemasini Mermaid ko'rinishida chiqaradi: python manage.py show_graph

Chiqqan matnni README.md ga ```mermaid ... ``` ichiga qo'ysangiz, GitHub uni rasm qilib ko'rsatadi.
LLM'ga so'rov yubormaydi, faqat graf to'g'ri yig'ilganini tekshiradi.
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "LangGraph sxemasini Mermaid formatida chiqaradi"

    def handle(self, *args, **options):
        from apps.ai.graph import build_graph

        self.stdout.write(build_graph(None).get_graph().draw_mermaid())
