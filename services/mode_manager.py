"""
services/mode_manager.py — [②]

세션 캐시 관리와 모드 전환(토글) 분기 로직을 담당하는 ModeManager 정의.
server.py가 TCP로 받은 ModeSwitchRequest를 그대로 넘겨준다.

캐시는 이 인스턴스(= server.py 프로세스 메모리) 안에 있다 — 클라이언트가
바뀌어도(같은 session_id면) 같은 캐시를 본다. 유효 기간은 앱 종료 시까지다.

■ 팀 확인이 필요한 임의 결정
- server.py는 query 처리 직후 remember_search()를 호출해 세션별 검색 컨텍스트
  (query/filters/top_k/found/retrieved_chunks)를 채운다. switch_mode()가 이
  컨텍스트 없이(=이 세션이 한 번도 query()를 거치지 않고 바로 모드 전환을 요청한
  경우) 들어오는 경우는 인터페이스 정의서에 명시가 없어, 재검색에 쓸 질의어 자체가
  없으므로 근거 없음으로 처리했다. 실제로 GUI가 이런 순서로 요청을 보낼 수 있는지
  ③④ 담당과 확인이 필요하다.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone

from common.schemas import (
    EasySummaryResponse,
    ExpertSummaryResponse,
    GenerationRequest,
    Mode,
    ModeSwitchRequest,
    ModeSwitchResponse,
    RetrievedChunk,
    SearchFilters,
    SearchRequest,
)
from services.generation import GenerationService
from services.retrieval import RetrievalService

_NO_EVIDENCE_EXPERT_TEXT = "제공된 회의록 발췌만으로는 답변할 수 없습니다. 검색어를 바꿔 다시 시도해주세요."
_NO_EVIDENCE_EASY_TEXT = "죄송하지만 관련된 회의 내용을 찾지 못했습니다. 다른 주제를 선택해주세요."


@dataclass
class _SessionCache:
    query: str
    filters: SearchFilters
    top_k: int
    found: bool
    retrieved_chunks: list[RetrievedChunk] = field(default_factory=list)


class ModeManager:
    def __init__(self, retrieval_service: RetrievalService, generation_service: GenerationService) -> None:
        self._retrieval = retrieval_service
        self._generation = generation_service
        self._cache: dict[str, _SessionCache] = {}

    def remember_search(
        self,
        session_id: str,
        query: str,
        filters: SearchFilters,
        top_k: int,
        found: bool,
        retrieved_chunks: list[RetrievedChunk],
    ) -> None:
        """server.py가 RemoteQueryRequest 처리 직후 호출해 세션 캐시를 채운다."""
        self._cache[session_id] = _SessionCache(
            query=query, filters=filters, top_k=top_k, found=found, retrieved_chunks=retrieved_chunks
        )

    def switch_mode(self, req: ModeSwitchRequest) -> ModeSwitchResponse:
        entry = self._cache.get(req.session_id)

        if entry is None:
            return ModeSwitchResponse(cache_hit=False, response=self._no_evidence_response(req.new_mode))

        if not entry.found:
            # T8: 직전 검색이 found=False였다면 토글해도 근거 없음 화면을 유지하고
            # 생성하지 않는다.
            return ModeSwitchResponse(cache_hit=True, response=self._no_evidence_response(req.new_mode))

        if entry.retrieved_chunks:
            # 캐시에 retrieved_chunks가 있으면 검색을 생략하고 generate()만 새
            # 모드로 재호출한다 (T7: 모드 전환이 빠르고 출처가 동일해야 함).
            chunks = entry.retrieved_chunks
            cache_hit = True
        else:
            # 캐시가 없으면 search()를 재실행한 뒤 generate()를 호출한다.
            search_result = self._retrieval.search(
                SearchRequest(
                    session_id=req.session_id, query=entry.query, filters=entry.filters, top_k=entry.top_k
                )
            )
            entry.found = search_result.found
            entry.retrieved_chunks = search_result.chunks
            if not search_result.found:
                return ModeSwitchResponse(cache_hit=False, response=self._no_evidence_response(req.new_mode))
            chunks = search_result.chunks
            cache_hit = False

        gen_response = self._generation.generate(
            GenerationRequest(
                session_id=req.session_id, query=entry.query, mode=req.new_mode, retrieved_chunks=chunks
            )
        )
        if gen_response is None:
            entry.found = False
            return ModeSwitchResponse(cache_hit=cache_hit, response=self._no_evidence_response(req.new_mode))

        return ModeSwitchResponse(cache_hit=cache_hit, response=gen_response)

    def _no_evidence_response(self, mode: Mode) -> ExpertSummaryResponse | EasySummaryResponse:
        now = datetime.now(timezone.utc).isoformat()
        if mode == Mode.EXPERT:
            return ExpertSummaryResponse(
                summary_text=_NO_EVIDENCE_EXPERT_TEXT, key_issues=[], citations=[], generated_at=now
            )
        return EasySummaryResponse(
            decision=_NO_EVIDENCE_EASY_TEXT, reason="", change="", glossary=[], generated_at=now
        )
