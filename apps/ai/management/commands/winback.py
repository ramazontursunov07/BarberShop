"""4-6 haftadan beri kelmagan mijozlarga shaxsiy Telegram xabar yuboradi.

Haftada bir marta cron orqali ishga tushiring:
    python manage.py winback
    python manage.py winback --min-weeks 4 --max-weeks 6 --dry-run
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Max, Q
from django.utils import timezone

from apps.ai.models import Notification
from apps.ai.notify import send_telegram
from apps.bookings.models import Booking
from apps.bookings.services import ACTIVE_STATUSES, master_name
from apps.users.models import User


def build_winback(user: User, last: Booking, weeks: int) -> str:
    name = user.first_name or "Salom"
    return (
        f"Salom, {name}! 👋\n\n"
        f"{master_name(last.master)} ustadan «{last.service.name}» qildirganingizga {weeks} hafta bo'ldi. "
        f"Yana yozilamizmi?\n\n"
        f"Shunchaki yozing, masalan: «Ertaga kechqurun {master_name(last.master)}ga {last.service.name.lower()}»."
    )


class Command(BaseCommand):
    help = "Uzoq vaqt kelmagan mijozlarga qaytarish xabarini yuboradi"

    def add_arguments(self, parser):
        parser.add_argument("--min-weeks", type=int, default=4)
        parser.add_argument("--max-weeks", type=int, default=6)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        now = timezone.now()
        newest = now - timedelta(weeks=options["min_weeks"])
        oldest = now - timedelta(weeks=options["max_weeks"])

        candidates = (
            User.objects.filter(role="client", telegram_id__isnull=False)
            .filter(Q(blocked_until__isnull=True) | Q(blocked_until__lte=now))
            .annotate(
                last_visit=Max("bookings__start_time", filter=Q(bookings__status=Booking.Status.COMPLETED))
            )
            .filter(last_visit__gte=oldest, last_visit__lte=newest)
            # Kelajakda faol broni bor mijozga yozmaymiz
            .exclude(bookings__status__in=ACTIVE_STATUSES, bookings__start_time__gte=now)
            # Oxirgi tashrifdan keyin allaqachon qaytarish xabari olgan bo'lsa, takrorlamaymiz
            .distinct()
        )

        sent = failed = 0
        for user in candidates:
            if Notification.objects.filter(
                user=user, kind=Notification.Kind.WINBACK, created_at__gte=user.last_visit
            ).exists():
                continue
            last = (
                Booking.objects.filter(client=user, status=Booking.Status.COMPLETED, start_time=user.last_visit)
                .select_related("master__user", "service")
                .first()
            )
            if last is None:
                continue
            weeks = max((now - user.last_visit).days // 7, options["min_weeks"])
            if options["dry_run"]:
                self.stdout.write(f"[dry-run] {user.id} ({weeks} hafta)")
                continue
            if send_telegram(user.telegram_id, build_winback(user, last, weeks)):
                Notification.objects.create(user=user, kind=Notification.Kind.WINBACK)
                sent += 1
            else:
                failed += 1

        self.stdout.write(self.style.SUCCESS(f"Yuborildi: {sent}, xato: {failed}"))
        