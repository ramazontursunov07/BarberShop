"""Qaysi Gemini modellari hozir ishlayotganini va 429 sababini ko'rsatadi.

Ishga tushirish: python check_quota.py   (loyiha ildizidan; tekshiruvdan keyin o'chirib tashlang)
Kalit chop etilmaydi.
"""
import os

import httpx

for line in open(".env", encoding="utf-8"):
    if "=" in line and not line.startswith("#"):
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip()

url = os.environ["LLM_BASE_URL"].rstrip("/") + "/chat/completions"
headers = {"Authorization": f"Bearer {os.environ['LLM_API_KEY']}", "Content-Type": "application/json"}

candidates = [
    os.environ.get("LLM_MODEL"),
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash-lite",
]
models = [m for i, m in enumerate(candidates) if m and m not in candidates[:i]]

for model in models:
    try:
        r = httpx.post(
            url,
            headers=headers,
            json={"model": model, "messages": [{"role": "user", "content": "Salom"}], "max_tokens": 20},
            timeout=60,
        )
    except Exception as exc:
        print(f"{model:30} -> ulanish xatosi: {type(exc).__name__}")
        continue
    print(f"{model:30} -> {r.status_code}")
    if r.status_code != 200:
        print("     xabar:", r.text[:700].replace("\n", " "))
        print("     retry-after:", r.headers.get("retry-after"))
