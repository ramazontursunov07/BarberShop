import asyncio
import os
from types import SimpleNamespace
from unittest import SkipTest, mock

import httpx
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from openai import OpenAIError
from rest_framework.test import APIClient

from apps.ai import speech
from apps.ai.speech import EmptyTranscript, SpeechNotConfigured, safe_filename, transcribe
from apps.tests.base import make_user
from telegram_bot.api import ApiError, BackendClient


def fake_stt(text):
    create = mock.Mock(return_value=SimpleNamespace(text=text))
    client = SimpleNamespace(audio=SimpleNamespace(transcriptions=SimpleNamespace(create=create)))
    return client, create


class SpeechTests(SimpleTestCase):
    def test_safe_filename_keeps_only_known_extensions(self):
        self.assertEqual(safe_filename("voice.OGG"), "voice.ogg")
        self.assertEqual(safe_filename("../../etc/passwd"), "voice.ogg")
        self.assertEqual(safe_filename("a.exe"), "voice.ogg")
        self.assertEqual(safe_filename(None), "voice.ogg")

    def test_missing_key_raises(self):
        with mock.patch.dict(os.environ, {"STT_API_KEY": ""}), override_settings(STT_API_KEY=""):
            with self.assertRaises(SpeechNotConfigured):
                transcribe(b"audio")

    def test_transcribe_cleans_text_and_sends_hint(self):
        client, create = fake_stt("  Ertaga   soch\nolish  ")
        with mock.patch.object(speech, "get_stt_client", return_value=client):
            self.assertEqual(transcribe(b"audio", "x.ogg"), "Ertaga soch olish")
        kwargs = create.call_args.kwargs
        self.assertEqual(kwargs["file"], ("voice.ogg", b"audio"))
        self.assertIn("soch olish", kwargs["prompt"])
        self.assertNotIn("language", kwargs)

    def test_language_hint_is_optional(self):
        client, create = fake_stt("salom")
        with mock.patch.object(speech, "get_stt_client", return_value=client), \
                mock.patch.dict(os.environ, {"STT_LANGUAGE": "uz"}):
            transcribe(b"audio")
        self.assertEqual(create.call_args.kwargs["language"], "uz")

    def test_empty_text_raises(self):
        client, _ = fake_stt("   ")
        with mock.patch.object(speech, "get_stt_client", return_value=client):
            with self.assertRaises(EmptyTranscript):
                transcribe(b"audio")


class TranscribeApiTests(TestCase):
    URL = "/api/ai/transcribe/"

    def setUp(self):
        cache.clear()
        self.user = make_user("+998900000321", "Mijoz")
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def upload(self, content=b"OggS-audio", name="voice.ogg"):
        return self.api.post(self.URL, {"audio": SimpleUploadedFile(name, content)}, format="multipart")

    def test_requires_login(self):
        self.api.force_authenticate(None)
        self.assertEqual(self.upload().status_code, 401)

    def test_returns_text(self):
        client, _ = fake_stt("Ertaga soat 10 da Jasurga")
        with mock.patch.object(speech, "get_stt_client", return_value=client):
            resp = self.upload()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["text"], "Ertaga soat 10 da Jasurga")

    def test_missing_or_empty_file_is_400(self):
        self.assertEqual(self.api.post(self.URL, {}, format="multipart").status_code, 400)
        self.assertEqual(self.upload(content=b"").status_code, 400)

    def test_too_large_is_413(self):
        resp = self.upload(content=b"x" * (speech.MAX_AUDIO_BYTES + 1))
        self.assertEqual(resp.status_code, 413)

    def test_not_configured_is_503(self):
        with mock.patch.object(speech, "get_stt_client", side_effect=SpeechNotConfigured()):
            self.assertEqual(self.upload().status_code, 503)

    def test_silence_is_422(self):
        client, _ = fake_stt("")
        with mock.patch.object(speech, "get_stt_client", return_value=client):
            self.assertEqual(self.upload().status_code, 422)

    def test_provider_error_is_502(self):
        client, create = fake_stt("x")
        create.side_effect = OpenAIError("boom")
        with mock.patch.object(speech, "get_stt_client", return_value=client):
            self.assertEqual(self.upload().status_code, 502)


class BackendClientTranscribeTests(SimpleTestCase):
    def make_client(self, handler):
        client = BackendClient("http://test", "secret")
        client._http = httpx.AsyncClient(base_url="http://test", transport=httpx.MockTransport(handler))
        return client

    def test_sends_multipart_with_bearer_and_returns_text(self):
        seen = {}

        def handler(request):
            seen["auth"] = request.headers["authorization"]
            seen["ctype"] = request.headers["content-type"]
            seen["path"] = request.url.path
            return httpx.Response(200, json={"text": "salom"})

        async def run():
            client = self.make_client(handler)
            try:
                return await client.transcribe("tok", b"audio")
            finally:
                await client.close()

        self.assertEqual(asyncio.run(run()), "salom")
        self.assertEqual(seen["auth"], "Bearer tok")
        self.assertTrue(seen["ctype"].startswith("multipart/form-data"))
        self.assertEqual(seen["path"], "/api/ai/transcribe/")

    def test_error_status_raises_api_error(self):
        async def run():
            client = self.make_client(lambda r: httpx.Response(422, json={"detail": "Ovozni tushunib bo'lmadi"}))
            try:
                await client.transcribe("tok", b"audio")
            finally:
                await client.close()

        with self.assertRaises(ApiError) as ctx:
            asyncio.run(run())
        self.assertEqual(ctx.exception.status, 422)


class BotVoiceHandlerTests(SimpleTestCase):
    """on_voice oqimi soxta Telegram va backend bilan: aiogram o'rnatilgan bo'lsa ishlaydi."""

    def setUp(self):
        env = {"TELEGRAM_BOT_TOKEN": "1:test", "TELEGRAM_BOT_SECRET": "s"}
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        try:
            from telegram_bot import main
        except ImportError:
            raise SkipTest("aiogram o'rnatilmagan")
        self.main = main
        main.histories.clear()

    def message(self, duration=5, file_size=1000):
        answers = []

        async def answer(text, **kwargs):
            answers.append(text)

        msg = SimpleNamespace(
            from_user=SimpleNamespace(id=42), chat=SimpleNamespace(id=42), answer=answer,
            voice=SimpleNamespace(duration=duration, file_size=file_size),
        )
        return msg, answers

    def bot(self):
        async def download(voice, destination):
            destination.write(b"ogg-bytes")

        async def chat_action(*args, **kwargs):
            pass

        return SimpleNamespace(download=download, send_chat_action=chat_action)

    def backend(self, transcribe_result="Ertaga soch olish", chat_result="Qaysi usta?"):
        async def get_token(user_id, **kw):
            return "tok"

        async def transcribe_(token, audio, filename="voice.ogg"):
            if isinstance(transcribe_result, Exception):
                raise transcribe_result
            return transcribe_result

        async def chat(token, text, history):
            return chat_result

        return SimpleNamespace(get_token=get_token, transcribe=transcribe_, chat=chat)

    def run_handler(self, msg, backend):
        with mock.patch.object(self.main, "backend", backend):
            asyncio.run(self.main.on_voice(msg, self.bot()))

    def test_too_long_voice_is_rejected_without_backend_calls(self):
        msg, answers = self.message(duration=120)
        self.run_handler(msg, backend=None)  # backend chaqirilsa AttributeError bo'lardi
        self.assertEqual(len(answers), 1)
        self.assertIn("uzun", answers[0])

    def test_voice_is_transcribed_echoed_and_sent_to_chat(self):
        msg, answers = self.message()
        self.run_handler(msg, self.backend())
        self.assertEqual(answers, ["🎤 Eshitdim: «Ertaga soch olish»", "Qaysi usta?"])
        history = list(self.main.histories[42])
        self.assertEqual(history[0], {"role": "user", "content": "Ertaga soch olish"})

    def test_unintelligible_voice_gets_friendly_reply(self):
        msg, answers = self.message()
        self.run_handler(msg, self.backend(transcribe_result=ApiError(422, "x")))
        self.assertEqual(len(answers), 1)
        self.assertIn("tushunolmadim", answers[0])
        self.assertEqual(len(self.main.histories[42]), 0)

    def test_not_configured_suggests_text(self):
        msg, answers = self.message()
        self.run_handler(msg, self.backend(transcribe_result=ApiError(503, "x")))
        self.assertIn("matn", answers[0])
