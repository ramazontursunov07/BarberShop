"""Sharhlar tahlilini sinash uchun qo'shimcha demo sharhlar: python manage.py seed_reviews

Avval `seed_demo` ishga tushirilgan bo'lishi kerak. Qayta ishga tushirsa ham dublikat yaratmaydi.
Sharhlarda ataylab bir necha mavzu bor (kutish vaqti, usta mahorati, tozalik, narx), o'zbek va rus tilida.
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.bookings.models import Booking
from apps.masters.models import Master
from apps.reviews.models import Review
from apps.services.models import Service
from apps.shops.models import Shop

PASSWORD = "demo12345"  # faqat lokal test uchun!
TZ = ZoneInfo("Asia/Tashkent")
SHOP_NAME = "Demo Barbershop"
FIRST_DAY = datetime(2026, 9, 1, 10, 0, tzinfo=TZ)

# (usta, xizmat, baho, sharh)
SAMPLES = [
    ("Jasur", "Soch olish", 5, "Jasur akaga rahmat, juda chiroyli qilib oldi. Sartaroshxona ham toza."),
    ("Jasur", "Soch olish", 4, "Soch yaxshi chiqdi, lekin 25 daqiqa navbat kutdim. Vaqtida boshlasa yaxshi bo'lardi."),
    ("Bobur", "Soqol olish", 5, "Bobur soqolni a'lo oladi, qo'li yengil. Albatta yana kelaman."),
    ("Bobur", "Soqol olish", 3, "Usta yaxshi, lekin yarim soatdan ortiq kutib o'tirdim, band ekan. Narx ham biroz qimmat."),
    ("Jasur", "Soch olish", 5, "Отличный мастер, стрижка получилась именно такая, как хотел. Чисто и уютно."),
    ("Bobur", "Soqol olish", 2, "Kutish juda uzoq bo'ldi, bron qilgan bo'lsam ham 40 daqiqa o'tirdim."),
    ("Jasur", "Soch olish", 4, "Мастер хороший, но пришлось ждать около 20 минут. Цены нормальные."),
    ("Bobur", "Soqol olish", 5, "Juda toza, asboblar tozalangan. Usta mahoratli, tavsiya qilaman."),
]


class Command(BaseCommand):
    help = "Sharhlar tahlilini sinash uchun qo'shimcha demo sharhlar yaratadi"

    def _client(self, index):
        User = get_user_model()
        phone = f"+99890000010{index}"
        user = User.objects.filter(phone=phone).first()
        if user is None:
            user = User.objects.create_user(phone=phone, password=PASSWORD,
                                            first_name=f"Mijoz{index}", role="client")
        return user

    def handle(self, *args, **options):
        shop = Shop.objects.filter(name=SHOP_NAME).first()
        if shop is None:
            raise CommandError("Demo sartaroshxona topilmadi. Avval: python manage.py seed_demo")

        created = 0
        for i, (master_name, service_name, rating, comment) in enumerate(SAMPLES):
            master = Master.objects.filter(shop=shop, user__first_name=master_name).first()
            service = Service.objects.filter(shop=shop, name=service_name).first()
            if master is None or service is None:
                raise CommandError(f"Usta yoki xizmat topilmadi: {master_name} / {service_name}")
            client = self._client(i)
            start = FIRST_DAY + timedelta(days=i)
            booking, _ = Booking.objects.get_or_create(
                client=client, master=master, service=service, start_time=start,
                defaults=dict(end_time=start + timedelta(minutes=service.duration_minutes),
                              price=service.price, status=Booking.Status.COMPLETED),
            )
            _, was_created = Review.objects.get_or_create(
                booking=booking, defaults=dict(client=client, rating=rating, comment=comment))
            created += was_created

        self.stdout.write(self.style.SUCCESS(f"Yangi sharhlar: {created} (jami {len(SAMPLES)} ta namunadan)."))
        self.stdout.write("Eslatma: RAG qidiruvida ham chiqishi uchun: python manage.py index_knowledge")
