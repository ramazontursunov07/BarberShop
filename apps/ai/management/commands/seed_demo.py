"""Test uchun demo ma'lumot yaratadi: python manage.py seed_demo

Qayta ishga tushirsa ham dublikat yaratmaydi.
"""
from datetime import datetime, time
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.ai.models import KnowledgeDocument
from apps.bookings.models import Booking
from apps.masters.models import Master, WorkSchedule
from apps.reviews.models import Review
from apps.services.models import Service
from apps.shops.models import Shop

PASSWORD = "demo12345"  # faqat lokal test uchun!
TZ = ZoneInfo("Asia/Tashkent")

DOCS = [
    (
        "Bronni bekor qilish qoidalari",
        "Bronni kelish vaqtidan kamida 2 soat oldin bekor qilish mumkin. "
        "Kechroq bekor qilingan yoki kelinmagan bron 'kelmadi' deb belgilanadi. "
        "Ketma-ket 3 marta kelmagan mijoz 7 kunga bloklanadi.",
    ),
    (
        "Kechikish qoidasi",
        "Mijoz belgilangan vaqtdan 15 daqiqadan ko'proq kechiksa, usta bronni bekor qilishi mumkin. "
        "5–10 daqiqalik kechikishda xizmat qisqartirilmaydi, lekin keyingi mijozga tegmasa.",
    ),
    (
        "To'lov usullari",
        "To'lov xizmat tugagandan keyin amalga oshiriladi: naqd pul yoki plastik karta (Uzcard, Humo). "
        "Oldindan to'lov talab qilinmaydi.",
    ),
    (
        "Qo'shimcha qulayliklar",
        "Sartaroshxonada bepul Wi-Fi, choy va qahva bor. "
        "Bolalar uchun alohida o'rindiq mavjud, 6 yoshgacha bolalar uchun chegirma 20%. "
        "Binoning oldida bepul avtoturargoh bor.",
    ),
]

REVIEWS = {
    "Jasur": (5, "Jasur juda yaxshi soch oladi, tez va toza ishlaydi. Har safar o'zimga yoqqan natija chiqadi."),
    "Bobur": (4, "Bobur soqolni a'lo darajada oladi, lekin bir marta navbat kutishga to'g'ri keldi."),
}


class Command(BaseCommand):
    help = "Demo sartaroshxona, ustalar, xizmatlar, qoidalar va sharhlar yaratadi"

    def _user(self, phone, first_name, role):
        User = get_user_model()
        user = User.objects.filter(phone=phone).first()
        if user is None:
            user = User.objects.create_user(
                phone=phone, password=PASSWORD, first_name=first_name, role=role
            )
        return user

    def handle(self, *args, **options):
        owner = self._user("+998900000001", "Egasi", "owner")
        client = self._user("+998900000004", "Test", "client")

        shop, _ = Shop.objects.get_or_create(
            name="Demo Barbershop",
            defaults=dict(
                owner=owner,
                description="Zamonaviy sartaroshxona: soch, soqol va styling xizmatlari.",
                phone="+998900000001",
                city="Toshkent",
                district="Yunusobod",
                address="Amir Temur ko'chasi 1",
                opens_at=time(9, 0),
                closes_at=time(19, 0),
                is_approved=True,
                is_active=True,
            ),
        )

        services = {}
        for name, price, minutes in [
            ("Soch olish", 50000, 30),
            ("Soqol olish", 30000, 20),
            ("Soch + soqol", 70000, 50),
        ]:
            services[name], _ = Service.objects.get_or_create(
                shop=shop,
                name=name,
                defaults=dict(price=price, duration_minutes=minutes, is_active=True),
            )

        masters = {}
        bios = {
            "Jasur": "Jasur 8 yillik tajribaga ega, klassik va fade soch turmaklari bo'yicha mutaxassis.",
            "Bobur": "Bobur soqol va mo'ylov parvarishi bo'yicha usta, 5 yillik tajriba.",
        }
        for phone, first_name in [("+998900000002", "Jasur"), ("+998900000003", "Bobur")]:
            user = self._user(phone, first_name, "master")
            master, _ = Master.objects.get_or_create(
                user=user, defaults=dict(shop=shop, bio=bios[first_name])
            )
            masters[first_name] = master
            for weekday in range(0, 6):  # Dushanba-Shanba
                WorkSchedule.objects.get_or_create(
                    master=master,
                    weekday=weekday,
                    defaults=dict(start_time=time(9, 0), end_time=time(18, 0)),
                )

        for title, content in DOCS:
            KnowledgeDocument.objects.get_or_create(
                shop=shop, title=title, defaults=dict(content=content)
            )

        # O'tgan bajarilgan bronlar va ularga sharhlar (RAG uchun)
        past = {
            "Jasur": (datetime(2026, 10, 20, 10, 0, tzinfo=TZ), datetime(2026, 10, 20, 10, 30, tzinfo=TZ), "Soch olish"),
            "Bobur": (datetime(2026, 10, 22, 15, 0, tzinfo=TZ), datetime(2026, 10, 22, 15, 20, tzinfo=TZ), "Soqol olish"),
        }
        for name, (start, end, service_name) in past.items():
            service = services[service_name]
            booking, _ = Booking.objects.get_or_create(
                client=client,
                master=masters[name],
                service=service,
                start_time=start,
                defaults=dict(end_time=end, price=service.price, status=Booking.Status.COMPLETED),
            )
            rating, comment = REVIEWS[name]
            Review.objects.get_or_create(
                booking=booking,
                defaults=dict(client=client, rating=rating, comment=comment),
            )

        self.stdout.write(self.style.SUCCESS("Demo ma'lumot tayyor."))
        self.stdout.write(f"Test mijoz: phone={client.phone}  password={PASSWORD}")
        self.stdout.write("Keyingi qadam: python manage.py index_knowledge")
