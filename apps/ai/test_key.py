import os
import anthropic

# .env ni qo'lda o'qiymiz (faqat shu test uchun)
for line in open(".env", encoding="utf-8"):
    if line.startswith("ANTHROPIC_API_KEY="):
        os.environ["ANTHROPIC_API_KEY"] = line.strip().split("=", 1)[1]

client = anthropic.Anthropic()
resp = client.messages.create(
    model="claude-sonnet-5-5",
    max_tokens=100,
    messages=[{"role": "user", "content": "Salom! Bir gap bilan javob ber."}],
)
print(resp.content[0].text)
