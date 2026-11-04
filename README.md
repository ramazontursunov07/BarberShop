# BarberShop

Sartaroshxonalar uchun online bron qilish platformasi (backend API).
Bir nechta sartaroshxona o'z kabinetiga ega, mijozlar usta va vaqtni tanlab bron qiladi.

## Texnologiyalar
- Python, Django, Django REST Framework
- JWT autentifikatsiya (simplejwt)
- SQLite (development)

## Ishga tushirish

```bash
git clone https://github.com/ramazontursunov07/BarberShop.git
cd BarberShop
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

`.env` fayl yarating (`.env.example` dan nusxa oling):

```
SECRET_KEY=your-secret-key
DEBUG=True
```

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## Loyiha tuzilmasi
- `apps/users`: foydalanuvchilar va rollar
- `apps/shops`: sartaroshxonalar
- `apps/masters`: ustalar va ish jadvali
- `apps/services`: xizmatlar
- `apps/bookings`: bronlar

## Holati
Ishlab chiqish jarayonida.
