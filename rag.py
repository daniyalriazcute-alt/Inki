from __future__ import annotations

import json
from pathlib import Path

import faiss
import numpy as np
import streamlit as st
from sentence_transformers import SentenceTransformer

BASE_DIR = Path(__file__).resolve().parent
KB_FILE = BASE_DIR / "data" / "knowledge_base.json"


@st.cache_resource(show_spinner=False)
def _load_rag():
    records = json.loads(KB_FILE.read_text(encoding="utf-8"))
    texts = [
        f"Title: {r['title']}\nCategory: {r['category']}\nContent: {r['content']}"
        for r in records
    ]

    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    embeddings = model.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    embeddings = np.asarray(embeddings, dtype="float32")

    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)
    return model, index, records, texts


def retrieve_context(query: str, k: int = 4) -> str:
    model, index, records, texts = _load_rag()
    vector = model.encode([query], normalize_embeddings=True)
    vector = np.asarray(vector, dtype="float32")
    scores, ids = index.search(vector, min(k, len(records)))

    chunks = []
    for score, idx in zip(scores[0], ids[0]):
        if idx < 0:
            continue
        chunks.append(
            f"[Similarity {float(score):.3f}]\n{texts[idx]}"
        )
    return "\n\n".join(chunks)
