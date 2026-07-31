from dataclasses import dataclass, field
from enum import Enum

# ── 1. 파이프라인(①) → 서비스(②) ──────────────
@dataclass
class ChunkData:
    chunk_id: str                  # "052147-0002"
    document: str                  # ChromaDB documents 파라미터용, 화면 표시 원문. [안건]+[질문]+[답변], 저장함
    embed_text: str                # dense 임베딩 전용 입력. [안건]+질문자·질문+답변자·답변. 저장 안 함
    question_text: str
    answer_text: str
    questioner: str
    questioner_position: str
    answerer: str
    answerer_position: str
    answerer_affiliation: str
    agenda_raw: str
    agenda_norm: str
    cat_politics: bool
    cat_economy: bool
    cat_diplomacy: bool
    cat_society: bool
    generation_no: int
    meeting_no: int
    session_no: int
    meeting_date: str
    meeting_date_ts: int
    source_url: str

# ── 2. 서버 내부(②) 검색 요청 — 서버 전용, 클라이언트는 직접 호출 안 함 ──
class Mode(str, Enum):
    EXPERT = "EXPERT"
    EASY = "EASY"

@dataclass
class SearchFilters:
    generation_no: int | None = None
    period_from: str | None = None
    period_to: str | None = None
    questioner: str | None = None
    category: str | None = None   # "cat_economy" 등

@dataclass
class SearchRequest:
    session_id: str
    query: str
    filters: SearchFilters
    top_k: int = 5

# ── 3. 서버 내부(②) 검색 결과 — 서버 전용 ────────
@dataclass
class RetrievedChunk:
    chunk_id: str
    text: str
    dense_similarity: float
    meeting_date: str
    meeting_label: str
    speaker: str
    citation_id: int

@dataclass
class SearchResult:
    session_id: str
    found: bool
    top_similarity: float
    chunks: list[RetrievedChunk]
    search_time_ms: int

# ── 4. 응답 생성 요청/응답 ──────────────────────
@dataclass
class GenerationRequest:
    session_id: str
    query: str
    mode: Mode
    retrieved_chunks: list[RetrievedChunk]

@dataclass
class ExpertSummaryResponse:
    summary_text: str
    key_issues: list[str]
    citations: list[dict]   # citation_id, meeting_label, meeting_date, speaker
    generated_at: str

@dataclass
class EasySummaryResponse:
    decision: str
    reason: str
    change: str
    glossary: list[dict]    # term, definition
    generated_at: str

# ── 5. 클라이언트 ↔ 서버 TCP 요청/응답 (§4.4) ────
@dataclass
class RemoteQueryRequest:
    session_id: str
    query: str
    filters: SearchFilters
    mode: Mode
    top_k: int = 5

@dataclass
class RemoteQueryResponse:
    session_id: str
    found: bool
    top_similarity: float
    chunks: list[RetrievedChunk]
    response: ExpertSummaryResponse | EasySummaryResponse | None
    error: str | None
    search_time_ms: int

# ── 6. 모드 전환(토글) 요청/응답 ─────────────────
@dataclass
class ModeSwitchRequest:
    session_id: str
    new_mode: Mode

@dataclass
class ModeSwitchResponse:
    cache_hit: bool
    response: ExpertSummaryResponse | EasySummaryResponse