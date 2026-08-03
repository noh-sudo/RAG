"""
data_pipeline/build_dense.py — [①]

chunks.json의 document 텍스트를 bge-m3로 임베딩해 ChromaDB에 적재하고
meta.json을 생성한다.

■ 왜 embed_text가 아니라 document를 임베딩하는가
embed_text는 저장하지 않는 필드라 chunks.json에 없다. chunk_builder.py가
document와 embed_text를 동일한 내용으로 만들기 때문에 document를 그대로
임베딩 입력으로 재사용해도 결과가 같다.
※ 팀 확인 필요: 나중에 document(화면 표시용)와 embed_text(임베딩 전용) 내용을
  다르게 구성하기로 하면, chunk_builder.py가 embed_text를 별도 파일로 저장하게
  바꾸고 이 스크립트도 그 파일을 읽도록 고쳐야 한다.

■ 함정 2개 (기획서 §8.1, 담당①)
1. collection.add(documents=[...])만 호출하면 Chroma가 자체 기본 임베딩 함수로
   처리한다 — embeddings=vectors를 반드시 직접 넘겨야 한다.
2. 컬렉션 생성 시 metadata={"hnsw:space": "cosine"}를 명시하지 않으면 기본
   거리 함수가 코사인이 아니게 된다.

■ 배치 처리
50건씩 나눠 ollama.embed()를 호출한다 (input에 리스트를 넘기면 배치로 처리해
embeddings 리스트를 한 번에 반환한다 — Ollama 0.6+ 기준). 한 배치가 실패하면
해당 배치의 chunk_id를 로그로 남기고 다음 배치로 계속 진행한다.

■ 컬렉션 이름·모델명은 config.py를 따른다
가이드 초안 작성 시점엔 config.py가 없어 "plenary"를 임의로 썼으나, 이제
config.CHROMA_COLLECTION_NAME("minutes_chunks")이 서버(②)와 공유하는 유일한
출처이므로 여기서 하드코딩하지 않는다 (VOP-004).
"""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import chromadb

import config

EMBED_MODEL = config.EMBED_MODEL
EMBED_DIM = config.EMBED_DIM
BATCH_SIZE = 50
KST = timezone(timedelta(hours=9))


def load_chunks(chunks_path: str) -> list[dict]:
    return json.loads(Path(chunks_path).read_text(encoding="utf-8"))


def embed_batch(texts: list[str]) -> list[list[float]]:
    """ollama.embed()는 input에 리스트를 넘기면 배치로 처리해
    embeddings 리스트를 반환한다."""
    import ollama
    result = ollama.embed(model=EMBED_MODEL, input=texts)
    return result["embeddings"]


def build_metadata(chunk: dict) -> dict:
    """ChromaDB where 필터에 쓸 메타데이터만 추린다."""
    return {
        "generation_no": chunk["generation_no"],
        "meeting_no": chunk["meeting_no"],
        "session_no": chunk["session_no"],
        "meeting_date": chunk["meeting_date"],
        "meeting_date_ts": chunk["meeting_date_ts"],
        "questioner": chunk["questioner"],
        "cat_politics": chunk["cat_politics"],
        "cat_economy": chunk["cat_economy"],
        "cat_diplomacy": chunk["cat_diplomacy"],
        "cat_society": chunk["cat_society"],
    }


def build_dense(chunks_path: str, chroma_dir: str, meta_path: str, embed_fn=embed_batch) -> None:
    chunks = load_chunks(chunks_path)

    client = chromadb.PersistentClient(path=chroma_dir)
    collection = client.get_or_create_collection(
        config.CHROMA_COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
    )

    failed_chunk_ids: list[str] = []
    total_indexed = 0

    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i : i + BATCH_SIZE]
        ids = [c["chunk_id"] for c in batch]
        texts = [c["document"] for c in batch]
        metadatas = [build_metadata(c) for c in batch]

        try:
            vectors = embed_fn(texts)
            collection.upsert(ids=ids, embeddings=vectors, documents=texts, metadatas=metadatas)
            total_indexed += len(batch)
            print(f"[build_dense] {i + len(batch)}/{len(chunks)}건 처리")
        except Exception as exc:  # noqa: BLE001
            print(f"[build_dense] 배치 {i}~{i + len(batch)} 실패: {exc}")
            failed_chunk_ids.extend(ids)

    generations = sorted({c["generation_no"] for c in chunks})
    dates = sorted(c["meeting_date"] for c in chunks)

    meta = {
        "embed_model": EMBED_MODEL,
        "dim": EMBED_DIM,
        "chunk_count": total_indexed,
        "scope": {
            "generation_no": generations,
            "period_from": dates[0] if dates else None,
            "period_to": dates[-1] if dates else None,
        },
        "created_at": datetime.now(KST).isoformat(),
    }
    Path(meta_path).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[build_dense] 완료: {total_indexed}/{len(chunks)}건 인덱싱")
    if failed_chunk_ids:
        print(f"[build_dense] 실패한 chunk_id {len(failed_chunk_ids)}건: {failed_chunk_ids}")


if __name__ == "__main__":
    build_dense(
        chunks_path=str(config.CHUNKS_PATH),
        chroma_dir=str(config.CHROMA_DIR),
        meta_path=str(config.META_PATH),
    )
