"""Xuất toạ độ 3D của toàn bộ điều luật để vẽ bản đồ ngữ nghĩa.

Chạy một lần, offline:
    .venv/bin/python -m scripts.export_vector_map
"""
import json
import os
import sys

import numpy as np
from sklearn.decomposition import PCA

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def project_to_3d(embeddings: np.ndarray) -> np.ndarray:
    """PCA 768 -> 3 chiều, chuẩn hoá về hộp [-1, 1]."""
    coords = PCA(n_components=3, random_state=0).fit_transform(embeddings)
    span = np.abs(coords).max()
    if span > 0:
        coords = coords / span
    return coords.astype(np.float32)


def main():
    from dotenv import load_dotenv
    load_dotenv()

    from src.embeddings.embedder import Embedder
    from src.vectorstore.store import VectorStore

    store = VectorStore(embedder=Embedder())
    print("Đang đọc embedding từ ChromaDB...")
    data = store.collection.get(include=["embeddings"])
    ids = data["ids"]
    emb = np.array(data["embeddings"], dtype=np.float32)
    print(f"Đọc được {len(ids)} điểm, {emb.shape[1]} chiều")

    coords = project_to_3d(emb)

    os.makedirs("web", exist_ok=True)
    coords.tofile("web/vector_map.bin")
    with open("web/vector_map.json", "w", encoding="utf-8") as f:
        json.dump({"count": len(ids), "ids": ids}, f, ensure_ascii=False)

    size_mb = os.path.getsize("web/vector_map.bin") / 1e6
    print(f"Đã ghi web/vector_map.bin ({size_mb:.2f} MB) và web/vector_map.json")


if __name__ == "__main__":
    main()
