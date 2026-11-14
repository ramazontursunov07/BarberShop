"""Bazaning zaxira nusxasi. Kuniga 1 marta (Celery beat) yoki qo'lda:
    python manage.py backup_db                 # BACKUP_DIR (standart: ./backups), 14 kun saqlanadi
    python manage.py backup_db --keep-days 30

PostgreSQL: pg_dump (siqilgan .sql.gz); SQLite: fayl nusxasi. Tashqi omborga (S3 va h.k.) yuborish uchun
BACKUP_UPLOAD_CMD ni o'rnating, masalan: "rclone copy {file} remote:barber-backups". {file} — yaratilgan fayl yo'li.
"""
import gzip
import os
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


def backup_dir() -> Path:
    return Path(os.getenv("BACKUP_DIR", settings.BASE_DIR / "backups"))


def make_backup(target: Path) -> Path:
    db = settings.DATABASES["default"]
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target.mkdir(parents=True, exist_ok=True)
    if db["ENGINE"].endswith("sqlite3"):
        out = target / f"db_{stamp}.sqlite3"
        shutil.copy2(db["NAME"], out)
        return out
    if not shutil.which("pg_dump"):
        raise CommandError("pg_dump topilmadi (postgresql-client o'rnatilmagan)")
    out = target / f"db_{stamp}.sql.gz"
    env = {**os.environ, "PGPASSWORD": db.get("PASSWORD", "")}
    cmd = ["pg_dump", "-h", db["HOST"], "-p", str(db["PORT"] or 5432), "-U", db["USER"], "--no-owner", db["NAME"]]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    with gzip.open(out, "wb") as gz:
        shutil.copyfileobj(proc.stdout, gz)
    err = proc.stderr.read().decode(errors="replace")
    if proc.wait() != 0:
        out.unlink(missing_ok=True)
        raise CommandError(f"pg_dump xatosi: {err[:300]}")
    return out


def prune(target: Path, keep_days: int) -> int:
    limit = time.time() - keep_days * 86400
    removed = 0
    for f in target.glob("db_*"):
        if f.is_file() and f.stat().st_mtime < limit:
            f.unlink()
            removed += 1
    return removed


class Command(BaseCommand):
    help = "Bazaning zaxira nusxasini yaratadi va eskilarini o'chiradi"

    def add_arguments(self, parser):
        parser.add_argument("--keep-days", type=int, default=14)

    def handle(self, *args, **options):
        target = backup_dir()
        out = make_backup(target)
        size_kb = out.stat().st_size // 1024
        removed = prune(target, options["keep_days"])
        upload = os.getenv("BACKUP_UPLOAD_CMD", "").strip()
        if upload:
            res = subprocess.run(upload.format(file=str(out)), shell=True, capture_output=True, text=True, timeout=600)
            if res.returncode != 0:
                raise CommandError(f"Yuklash xatosi: {res.stderr[:300]}")
        self.stdout.write(self.style.SUCCESS(f"Zaxira: {out.name} ({size_kb} KB), eskilari o'chirildi: {removed}"))
