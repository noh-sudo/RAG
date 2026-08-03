"""
services/retrieval.py — [②]

사용자 검색어와 필터를 받아 dense 검색을 수행하고 근거 유무를 판정하는
RetrievalService 정의. server.py만 호출한다.

■ 팀 확인이 필요한 임의 결정
- 쿼리 임베딩은 data_pipeline/build_dense.py(①)와 동일하게 ollama.embed(model=
  config.EMBED_MODEL, ...)로 만든다 — Ollama가 서빙하는 bge-m3를 그대로 호출해야
  build_dense.py가 만든 벡터와 같은 공간에 놓이기 때문이다(feature/data 브랜치의
  build_dense.py 실제 구현 확인 완료, 2026-08-03).
- RetrievedChunk.speaker는 질문자/답변자 중 누구를 넣어야 하는지 인터페이스 정의서에
  명시가 없어, 각주에 인용되는 쪽이 보통 답변 내용이라고 보아 답변자를 기본값으로
  삼았다. ③ 담당(citation_widget.py)이 다른 표기를 요구하면 _to_retrieved_chunk()만
  고치면 된다.
"""

import time
from datetime import datetime

import chromadb
import ollama

import config
from common.schemas import RetrievedChunk, SearchFilters, SearchRequest, SearchResult


class RetrievalService:
    def __init__(self) -> None:
        self._client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
        self._collection = self._client.get_collection(config.CHROMA_COLLECTION_NAME)

    def search(self, request: SearchRequest) -> SearchResult:
        """§4.3 검색 흐름. 임계값 게이트(1차 방어선)를 여기서 적용한다.

        dense 유사도 최댓값이 config.THRESHOLD 미만이면 found=False와 빈 리스트를
        반환하고 끝난다 — LLM은 호출하지 않는다. found=False는 오류가 아니라
        정상 응답이다(VOP-015, ERR_SEARCH_EMPTY를 발생시키지 않음).
        """
        start = time.perf_counter()
        chunks = self.raw_query(request.query, request.top_k, request.filters)
        search_time_ms = int((time.perf_counter() - start) * 1000)

        top_similarity = chunks[0].dense_similarity if chunks else 0.0

        if top_similarity < config.THRESHOLD:
            return SearchResult(
                session_id=request.session_id,
                found=False,
                top_similarity=top_similarity,
                chunks=[],
                search_time_ms=search_time_ms,
            )

        return SearchResult(
            session_id=request.session_id,
            found=True,
            top_similarity=top_similarity,
            chunks=chunks,
            search_time_ms=search_time_ms,
        )

    def raw_query(
        self, query: str, top_k: int, filters: SearchFilters | None = None
    ) -> list[RetrievedChunk]:
        """게이트(THRESHOLD)를 거치지 않는 원시 dense 조회.

        search()와 threshold_eval.py(Day 4, THRESHOLD 실측)가 이 메서드 하나를
        공유한다 — THRESHOLD를 정하는 도구가 아직 정해지지 않은 THRESHOLD에
        의존하면 안 되기 때문이다.
        """
        where = self._build_where(filters) if filters else None
        # build_dense.py의 embed_batch()와 동일한 호출 (ollama.embed는 input에
        # 리스트를 받아 embeddings 리스트를 반환한다).
        embedding = ollama.embed(model=config.EMBED_MODEL, input=[query])["embeddings"][0]

        result = self._collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
            where=where,
        )

        if not result["ids"] or not result["ids"][0]:
            return []

        # ChromaDB query()는 distance를 반환한다. distance가 작을수록(=유사도가
        # 높을수록) 앞에 오도록 이미 정렬돼 있다. 1 - distance가 유사도다.
        # 부호를 헷갈리면 게이트가 정확히 거꾸로 동작하므로(무관한 결과만 통과)
        # Day 2에 실측으로 이 변환이 맞는지 재확인해야 한다.
        rows = zip(
            result["ids"][0],
            result["documents"][0],
            result["metadatas"][0],
            result["distances"][0],
        )
        return [
            self._to_retrieved_chunk(rank, chunk_id, document, meta, 1 - distance)
            for rank, (chunk_id, document, meta, distance) in enumerate(rows, start=1)
        ]

    def _build_where(self, filters: SearchFilters) -> dict | None:
        """SearchFilters를 ChromaDB where 절로 변환한다."""
        clauses = []

        if filters.generation_no is not None:
            clauses.append({"generation_no": filters.generation_no})
        if filters.questioner:
            clauses.append({"questioner": filters.questioner})
        if filters.category:
            clauses.append({filters.category: True})
        if filters.period_from or filters.period_to:
            range_clause: dict = {}
            if filters.period_from:
                range_clause["$gte"] = self._date_to_ts(filters.period_from)
            if filters.period_to:
                range_clause["$lte"] = self._date_to_ts(filters.period_to)
            clauses.append({"meeting_date_ts": range_clause})

        if not clauses:
            return None
        if len(clauses) == 1:
            return clauses[0]
        return {"$and": clauses}

    def _date_to_ts(self, date_str: str) -> int:
        return int(datetime.strptime(date_str, "%Y-%m-%d").timestamp())

    def _to_retrieved_chunk(
        self, rank: int, chunk_id: str, document: str, meta: dict, similarity: float
    ) -> RetrievedChunk:
        meeting_label = (
            f"제{meta['generation_no']}대 국회 제{meta['meeting_no']}회 "
            f"제{meta['session_no']}차 본회의"
        )
        speaker = f"{meta['answerer']} ({meta['answerer_position']}, {meta['answerer_affiliation']})"

        return RetrievedChunk(
            chunk_id=chunk_id,
            text=document,
            dense_similarity=similarity,
            meeting_date=meta["meeting_date"],
            meeting_label=meeting_label,
            speaker=speaker,
            citation_id=rank,
        )

