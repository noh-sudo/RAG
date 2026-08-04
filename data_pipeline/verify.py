"""
data_pipeline/verify.py — [①]

chunks.json과 ChromaDB가 서로 어긋나지 않았는지 확인하는 정합성 검증 스크립트.
검증 항목: (1) chunk_id 집합 완전 일치, (2) meta.json.chunk_count와 Chroma 건수 일치.
"""

import json
from pathlib import Path

import chromadb

import config


def load_chunk_ids(chunks_path: str) -> set:
    chunks = json.loads(Path(chunks_path).read_text(encoding="utf-8"))
    return {c["chunk_id"] for c in chunks}


def load_chroma_ids(chroma_dir: str, collection_name: str = None) -> set:
    collection_name = collection_name or config.CHROMA_COLLECTION_NAME
    client = chromadb.PersistentClient(path=chroma_dir)
    collection = client.get_collection(collection_name)
    result = collection.get(include=[])
    return set(result["ids"])


def verify(chunks_path: str, chroma_dir: str, meta_path: str) -> bool:
    chunk_ids = load_chunk_ids(chunks_path)
    chroma_ids = load_chroma_ids(chroma_dir)
    meta = json.loads(Path(meta_path).read_text(encoding="utf-8"))

    ok = True

    if chunk_ids != chroma_ids:
        only_in_chunks = chunk_ids - chroma_ids
        only_in_chroma = chroma_ids - chunk_ids
        print("[verify] chunk_id 집합 불일치")
        if only_in_chunks:
            print(f"  chunks.json에만 있음 ({len(only_in_chunks)}건): {list(only_in_chunks)[:10]}")
        if only_in_chroma:
            print(f"  ChromaDB에만 있음 ({len(only_in_chroma)}건): {list(only_in_chroma)[:10]}")
        ok = False
    else:
        print(f"[verify] chunk_id 집합 일치 ({len(chunk_ids)}건)")

    if meta["chunk_count"] != len(chroma_ids):
        print(f"[verify] chunk_count 불일치: meta.json={meta['chunk_count']}, Chroma 실제={len(chroma_ids)}")
        ok = False
    else:
        print(f"[verify] chunk_count 일치 ({meta['chunk_count']}건)")

    print("[verify] 정합성 검증 " + ("통과" if ok else "실패 — 배포하지 말 것"))
    return ok


if __name__ == "__main__":
    success = verify(
        chunks_path=str(config.CHUNKS_PATH),
        chroma_dir=str(config.CHROMA_DIR),
        meta_path=str(config.META_PATH),
    )
    raise SystemExit(0 if success else 1)
