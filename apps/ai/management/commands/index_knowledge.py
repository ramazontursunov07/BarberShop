"""Bilimlar bazasini (vektor baza) qayta quradi: python manage.py index_knowledge

Sartaroshxona ma'lumotlari, xizmatlar, sharhlar yoki KnowledgeDocument o'zgargach qayta ishga tushiring.
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "RAG vektor bazasini qayta indekslaydi"

    def handle(self, *args, **options):
        from apps.ai import rag

        count = rag.reindex()
        self.stdout.write(self.style.SUCCESS(f"{count} ta bo'lak indekslandi."))
