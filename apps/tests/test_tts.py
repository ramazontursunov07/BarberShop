"""AI javobini ovozga aylantirish (TTS)."""
import base64
import os
from unittest.mock import MagicMock, patch

import httpx
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.ai import tts
from apps.tests.base import BookingTestBase

GOOGLE = "https://generativelanguage.googleapis.com/v1beta/openai/"
PCM = base64.b64encode(b"\x01\x02" * 200).decode()


def gemini_ok():
    resp = MagicMock(status_code=200, text="")
    resp.json.return_value = {"candidates": [{"content": {"parts": [
        {"inlineData": {"mimeType": "audio/L16;codec=pcm;rate=24000", "data": PCM}}]}}]}
    return resp


def raw(status=200, body=b"AUDIO"):
    return MagicMock(status_code=status, content=body, text="err")


class CleanTextTests(BookingTestBase):
    def test_strips_markdown_links_and_emoji(self):
        text = tts.clean_text("**Salom!** 😀 Bron: [havola](https://x.uz) `kod`\n- soat 15:00\nhttps://a.b/c")
        self.assertEqual(text, "Salom! Bron: havola kod soat 15:00")

    def test_long_text_is_cut_at_sentence(self):
        long = ("Bu uzun gap bo'ladi. " * 80)
        out = tts.clean_text(long)
        self.assertLessEqual(len(out), tts.MAX_TTS_CHARS)
        self.assertTrue(out.endswith("."))


class SpeakApiTests(BookingTestBase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.api = APIClient()
        self.api.force_authenticate(self.client_user)
        self.env = {"TTS_PROVIDER": "", "TTS_API_KEY": "", "LLM_API_KEY": "", "LLM_BASE_URL": ""}

    def speak(self, env, text="Salom, bron tayyor", **extra):
        with patch.dict(os.environ, {**self.env, **env}):
            return self.api.post("/api/ai/speak/", {"text": text, **extra}, format="json")

    def test_requires_login(self):
        res = APIClient().post("/api/ai/speak/", {"text": "x"}, format="json")
        self.assertEqual(res.status_code, 401)

    def test_not_configured_is_503(self):
        self.assertEqual(self.speak({}).status_code, 503)
        self.assertEqual(self.speak({"TTS_PROVIDER": "gemini"}).status_code, 503)  # kalit yo'q
        with patch.dict(os.environ, self.env):
            self.assertFalse(tts.is_configured())

    def test_empty_text_is_400(self):
        self.assertEqual(self.speak({"TTS_PROVIDER": "gemini", "TTS_API_KEY": "k"}, text="  😀 ").status_code, 400)

    def test_gemini_returns_wav_with_own_key(self):
        with patch("apps.ai.tts.httpx.post", return_value=gemini_ok()) as post:
            res = self.speak({"TTS_PROVIDER": "gemini", "TTS_API_KEY": "tts-key"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Content-Type"], "audio/wav")
        self.assertTrue(res.content.startswith(b"RIFF"))
        self.assertEqual(post.call_args.kwargs["headers"]["x-goog-api-key"], "tts-key")
        body = post.call_args.kwargs["json"]
        self.assertEqual(body["generationConfig"]["responseModalities"], ["AUDIO"])

    def test_gemini_reuses_llm_key_only_for_google(self):
        with patch("apps.ai.tts.httpx.post", return_value=gemini_ok()) as post:
            res = self.speak({"TTS_PROVIDER": "gemini", "LLM_API_KEY": "llm-key", "LLM_BASE_URL": GOOGLE})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(post.call_args.kwargs["headers"]["x-goog-api-key"], "llm-key")
        # boshqa provayder (masalan Groq) kaliti Google'ga yuborilmaydi
        res = self.speak({"TTS_PROVIDER": "gemini", "LLM_API_KEY": "groq-key",
                          "LLM_BASE_URL": "https://api.groq.com/openai/v1"}, text="boshqa matn")
        self.assertEqual(res.status_code, 503)

    def test_openai_mp3_and_ogg(self):
        env = {"TTS_PROVIDER": "openai", "TTS_API_KEY": "k"}
        with patch("apps.ai.tts.httpx.post", return_value=raw()) as post:
            res = self.speak(env)
            self.assertEqual(res["Content-Type"], "audio/mpeg")
            self.assertEqual(post.call_args.kwargs["json"]["response_format"], "mp3")
            res = self.speak(env, format="ogg")
            self.assertEqual(res["Content-Type"], "audio/ogg")
            self.assertEqual(post.call_args.kwargs["json"]["response_format"], "opus")
            self.assertEqual(post.call_args.args[0], "https://api.openai.com/v1/audio/speech")

    def test_same_text_is_cached(self):
        env = {"TTS_PROVIDER": "openai", "TTS_API_KEY": "k"}
        with patch("apps.ai.tts.httpx.post", return_value=raw()) as post:
            self.speak(env)
            self.speak(env)
        self.assertEqual(post.call_count, 1)

    def test_provider_errors(self):
        env = {"TTS_PROVIDER": "openai", "TTS_API_KEY": "k"}
        with patch("apps.ai.tts.httpx.post", return_value=raw(429)):
            self.assertEqual(self.speak(env, text="bir").status_code, 429)
        with patch("apps.ai.tts.httpx.post", return_value=raw(500)):
            self.assertEqual(self.speak(env, text="ikki").status_code, 502)
        with patch("apps.ai.tts.httpx.post", side_effect=httpx.ConnectError("x")):
            self.assertEqual(self.speak(env, text="uch").status_code, 502)

    def test_gemini_ogg_needs_ffmpeg(self):
        with patch("apps.ai.tts.httpx.post", return_value=gemini_ok()), patch("apps.ai.tts.shutil.which", return_value=None):
            res = self.speak({"TTS_PROVIDER": "gemini", "TTS_API_KEY": "k"}, format="ogg")
        self.assertEqual(res.status_code, 502)


import shutil  # noqa: E402
from unittest import skipUnless  # noqa: E402


class ConvertTests(BookingTestBase):
    @skipUnless(shutil.which("ffmpeg"), "ffmpeg o'rnatilmagan")
    def test_gemini_wav_converts_to_ogg_opus_and_mp3(self):
        env = {"TTS_PROVIDER": "gemini", "TTS_API_KEY": "k"}
        with patch.dict(os.environ, env), patch("apps.ai.tts.httpx.post", return_value=gemini_ok()):
            ogg, mime = tts.synthesize("Salom", "ogg")
            self.assertEqual((ogg[:4], mime), (b"OggS", "audio/ogg"))
            mp3, mime = tts.synthesize("Salom", "mp3")
            self.assertEqual(mime, "audio/mpeg")
            self.assertTrue(mp3[:3] == b"ID3" or mp3[0] == 0xFF)
