"""AI chatni terminalda sinash. Avval boshqa terminalda `python manage.py runserver` ishlab turishi kerak.

Ishga tushirish: python chat_cli.py
Chiqish: bo'sh qator yoki Ctrl+C
"""
import json
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"
PHONE = "+998900000004"
PASSWORD = "demo12345"


def post(path, data, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        BASE + path, data=json.dumps(data).encode(), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")
    except urllib.error.URLError as e:
        return 0, f"Serverga ulanib bo'lmadi: {e.reason}"


status, body = post("/api/users/login/", {"phone": PHONE, "password": PASSWORD})
if status != 200:
    raise SystemExit(f"Login xatosi ({status}): {body}\nAvval: python manage.py seed_demo")
token = body["access"]
print("Kirdingiz. Savol yozing (bo'sh qator - chiqish).\n")

history = []
while True:
    try:
        text = input("Siz: ").strip()
    except (KeyboardInterrupt, EOFError):
        break
    if not text:
        break
    status, body = post("/api/ai/chat/", {"message": text, "history": history}, token)
    if status != 200:
        print(f"[Xato {status}] {body}\n")
        continue
    print(f"AI: {body['reply']}\n")
    history += [
        {"role": "user", "content": text},
        {"role": "assistant", "content": body["reply"]},
    ]
