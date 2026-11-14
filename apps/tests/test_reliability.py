"""Ishonchlilik: Telegram qayta urinish/bloklash, zaxira nusxa."""
import os
import tempfile
import time
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.ai import notify
from apps.ai.management.commands.backup_db import prune
from apps.users.models import User


def resp(code, body=None):
    r = MagicMock()
    r.status_code = code
    r.json.return_value = body or {}
    return r


@patch("apps.ai.notify.time.sleep")
@patch("apps.ai.notify.conf", return_value="TOKEN")
class SendTelegramTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone="+998901112233", first_name="A", telegram_id=555)

    def test_retries_then_succeeds(self, _conf, sleep):
        with patch("apps.ai.notify.httpx.post", side_effect=[resp(502), resp(429, {"parameters": {"retry_after": 2}}),
                                                             resp(200)]) as post:
            self.assertTrue(notify.send_telegram(555, "salom"))
        self.assertEqual(post.call_count, 3)
        self.assertEqual([c.args[0] for c in sleep.call_args_list], [0.5, 2.0])

    def test_gives_up_after_three_network_errors(self, _conf, sleep):
        with patch("apps.ai.notify.httpx.post", side_effect=httpx.ConnectError("x")) as post:
            self.assertFalse(notify.send_telegram(555, "salom"))
        self.assertEqual(post.call_count, 3)

    def test_400_is_not_retried(self, _conf, sleep):
        with patch("apps.ai.notify.httpx.post", return_value=resp(400)) as post:
            self.assertFalse(notify.send_telegram(555, "salom"))
        self.assertEqual(post.call_count, 1)

    def test_blocked_user_marked_and_skipped_until_relink(self, _conf, sleep):
        with patch("apps.ai.notify.httpx.post", return_value=resp(403)) as post:
            self.assertFalse(notify.send_telegram(555, "salom"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.telegram_blocked)
        with patch("apps.ai.notify.httpx.post") as post2:
            self.assertFalse(notify.send_telegram(555, "yana"))
        post2.assert_not_called()

    @override_settings(TELEGRAM_BOT_SECRET="s3cret")
    def test_bot_auth_clears_block(self, _conf, sleep):
        User.objects.filter(pk=self.user.pk).update(telegram_blocked=True)
        r = self.client.post("/api/users/telegram/auth/", {"telegram_id": 555}, content_type="application/json",
                             headers={"X-Bot-Secret": "s3cret"})
        self.assertEqual(r.status_code, 200, r.content)
        self.user.refresh_from_db()
        self.assertFalse(self.user.telegram_blocked)


class BackupTests(TestCase):
    def test_sqlite_backup_and_prune(self):
        from django.conf import settings
        if not settings.DATABASES["default"]["ENGINE"].endswith("sqlite3"):
            self.skipTest("SQLite zaxirasi faqat SQLite'da sinaladi")
        with tempfile.TemporaryDirectory() as d, \
                patch.dict(os.environ, {"BACKUP_DIR": d}), \
                patch("apps.ai.management.commands.backup_db.shutil.copy2") as cp:
            cp.side_effect = lambda src, dst: Path(dst).write_bytes(b"x")
            old = Path(d, "db_old.sqlite3")
            old.write_bytes(b"x")
            past = time.time() - 40 * 86400
            os.utime(old, (past, past))
            out = StringIO()
            call_command("backup_db", "--keep-days", "14", stdout=out)
            files = sorted(p.name for p in Path(d).iterdir())
            self.assertEqual(len(files), 1)
            self.assertNotIn("db_old.sqlite3", files)
            self.assertIn("Zaxira", out.getvalue())

    def test_prune_only_old_backups(self):
        with tempfile.TemporaryDirectory() as d:
            keep, drop, other = Path(d, "db_new.sql.gz"), Path(d, "db_old.sql.gz"), Path(d, "notes.txt")
            for f in (keep, drop, other):
                f.write_bytes(b"x")
            past = time.time() - 30 * 86400
            for f in (drop, other):
                os.utime(f, (past, past))
            self.assertEqual(prune(Path(d), 14), 1)
            self.assertTrue(keep.exists() and other.exists() and not drop.exists())
