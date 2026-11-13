"""RAG: bilimlarni yig'ish, embedding, Chroma vektor bazasiga yozish va qidirish.

Oqim:
  reindex():  DB -> matn bo'laklari -> embedding (Gemini) -> Chroma
  search():   savol -> embedding -> Chroma'dan eng yaqin bo'laklar (shop bo'yicha filtr)
"""
import time

from django.conf import settings
from openai import RateLimitError

from apps.reviews.models import Review
from apps.services.models import Service
from apps.shops.models import Shop
from apps.masters.models import Master

from . import observability, services
from .chunking import chunk_text
from .llm import conf, get_client
from .models import KnowledgeDocument

COLLECTION = "shop_knowledge"
EMBED_BATCH = 16


# ------------------------------------------------------------ embedding

def embed_texts(texts: list[str]) -> list[list[float]]:
    client = get_client()
    model = conf("LLM_EMBED_MODEL", "gemini-embedding-001")
    vectors: list[list[float]] = []
    for i in range(0, len(texts), EMBED_BATCH):
        batch = texts[i:i + EMBED_BATCH]
        for attempt in range(3):
            try:
                with observability.track("embedding", "embed", model) as call:
                    resp = client.embeddings.create(model=model, input=batch)
                    call.usage(resp)
                break
            except RateLimitError:  # bepul limit: biroz kutib qayta urinamiz
                if attempt == 2:
                    raise
                time.sleep(15)
        data = list(resp.data)
        # Ba'zi provayderlar (Gemini) index ni bermaydi (None): shunda tartibga ishonamiz
        if all(getattr(d, "index", None) is not None for d in data):
            data.sort(key=lambda d: d.index)
        vectors.extend(d.embedding for d in data)
    return vectors


# ------------------------------------------------------------ Chroma

def _chroma():
    import chromadb

    return chromadb.PersistentClient(path=str(settings.BASE_DIR / "chroma_db"))


def _collection(client, recreate: bool = False):
    if recreate:
        try:
            client.delete_collection(COLLECTION)
        except Exception:
            pass
    return client.get_or_create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})


# ------------------------------------------------------------ bilimlarni yig'ish

def collect_documents() -> list[dict]:
    """DB'dagi ma'lumotlarni {id, shop_id, source, text} ko'rinishida yig'adi."""
    docs: list[dict] = []

    for s in Shop.objects.filter(is_active=True):
        text = (
            f"[{s.name}] Sartaroshxona haqida: {s.description}\n"
            f"Manzil: {s.city}, {s.district}, {s.address}. "
            f"Ish vaqti: {s.opens_at:%H:%M}–{s.closes_at:%H:%M}. Telefon: {s.phone}."
        )
        docs.append({"id": f"shop:{s.id}", "shop_id": s.id, "source": "shop", "text": text})

    for sv in Service.objects.filter(is_active=True, shop__is_active=True).select_related("shop"):
        text = (
            f"[{sv.shop.name}] Xizmat: {sv.name}. Narxi: {int(sv.price)} so'm. "
            f"Davomiyligi: {sv.duration_minutes} daqiqa. {sv.description}"
        )
        docs.append({"id": f"service:{sv.id}", "shop_id": sv.shop_id, "source": "service", "text": text})

    for m in Master.objects.filter(is_active=True, shop__is_active=True).select_related("user", "shop"):
        text = f"[{m.shop.name}] Usta: {services._master_name(m)}. {m.bio}"
        docs.append({"id": f"master:{m.id}", "shop_id": m.shop_id, "source": "master", "text": text})

    reviews = (
        Review.objects.exclude(comment="")
        .select_related("booking__master__user", "booking__master__shop", "booking__service")
    )
    for r in reviews:
        master = r.booking.master
        text = (
            f"[{master.shop.name}] Mijoz sharhi ({r.rating}/5), usta {services._master_name(master)}, "
            f"xizmat: {r.booking.service.name}. Sharh: {r.comment}"
        )
        docs.append({"id": f"review:{r.id}", "shop_id": master.shop_id, "source": "review", "text": text})

    kdocs = KnowledgeDocument.objects.filter(is_active=True, shop__is_active=True).select_related("shop")
    for d in kdocs:
        for n, chunk in enumerate(chunk_text(d.content)):
            text = f"[{d.shop.name}] {d.title}\n{chunk}"
            docs.append({"id": f"doc:{d.id}:{n}", "shop_id": d.shop_id, "source": "doc", "text": text})

    from apps.faq.models import FAQItem  # lazy: faq app ixtiyoriy bog'liqlik

    for f in FAQItem.objects.filter(is_active=True, shop__is_active=True).select_related("shop"):
        text = f"[{f.shop.name}] Savol: {f.question}\nJavob: {f.answer}"
        docs.append({"id": f"faq:{f.id}", "shop_id": f.shop_id, "source": "faq", "text": text})

    return docs


def reindex() -> int:
    """Vektor bazani noldan qayta quradi. Indekslangan bo'laklar sonini qaytaradi."""
    docs = collect_documents()
    client = _chroma()
    col = _collection(client, recreate=True)
    if not docs:
        return 0

    vectors = embed_texts([d["text"] for d in docs])
    col.add(
        ids=[d["id"] for d in docs],
        embeddings=vectors,
        documents=[d["text"] for d in docs],
        metadatas=[{"shop_id": d["shop_id"], "source": d["source"]} for d in docs],
    )
    return len(docs)


# ------------------------------------------------------------ qidirish

def search_shop_info(query: str, shop_id: int | None = None, n_results: int = 4) -> dict:
    query = (query or "").strip()
    if not query:
        return {"error": "Qidiruv so'rovi bo'sh"}

    col = _collection(_chroma())
    if col.count() == 0:
        return {"results": [], "note": "Bilimlar bazasi hali indekslanmagan"}

    where = {"shop_id": int(shop_id)} if shop_id else None
    vector = embed_texts([query])[0]
    found = col.query(
        query_embeddings=[vector],
        n_results=min(n_results, col.count()),
        where=where,
    )

    results = []
    for text, meta, dist in zip(found["documents"][0], found["metadatas"][0], found["distances"][0]):
        results.append(
            {"text": text, "source": meta.get("source"), "relevance": round(1 - dist, 3)}
        )
    if not results:
        return {"results": [], "note": "Mos ma'lumot topilmadi"}
    return {"results": results}
