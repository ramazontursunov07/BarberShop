"""Embedding modeli va chromadb ishlashini tekshiradi. Tekshiruvdan keyin o'chirib tashlang."""
import os

from openai import OpenAI

for line in open(".env", encoding="utf-8"):
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ[k.strip()] = v.strip()

client = OpenAI(
    api_key=os.environ["LLM_API_KEY"],
    base_url=os.environ["LLM_BASE_URL"],
)

MODELS = [
    "gemini-embedding-001",
    "gemini-embedding-2",
    "gemini-embedding-2-preview",
    "models/gemini-embedding-001",
]

print("--- Embedding modellari")
for model in MODELS:
    try:
        r = client.embeddings.create(
            model=model,
            input=["Soch olish qancha turadi?", "Bronni bekor qilish qoidalari"],
        )
        print("OK  ", model, "-> vektor o'lchami:", len(r.data[0].embedding))
    except Exception as e:
        print("XATO", model, "->", type(e).__name__, str(e)[:150])

print("--- Chroma vektor baza")
try:
    import chromadb

    chroma = chromadb.EphemeralClient()
    col = chroma.create_collection("sinov")
    col.add(ids=["1"], embeddings=[[0.1, 0.2, 0.3]], documents=["salom"])
    found = col.query(query_embeddings=[[0.1, 0.2, 0.3]], n_results=1)
    print("OK   chromadb", chromadb.__version__, "->", found["documents"][0])
except Exception as e:
    print("XATO chromadb ->", type(e).__name__, str(e)[:200])
