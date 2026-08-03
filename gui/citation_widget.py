"""출처 각주 렌더링 및 원문 점프.  [소유: ③]

`citation_id`는 ②가 검색 단계에서 부여한다. GUI는 렌더링만 하고
번호를 다시 매기지 않는다 — 요약문 안의 [id] 표기와 대응이 깨지기 때문이다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
from typing import Iterable, List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

ANCHOR_PREFIX = "cite-"


def anchor_for(citation_id: str) -> str:
    """원문 HTML 안에 심을 앵커 id. 원문 렌더링 쪽과 이 함수를 함께 쓴다."""
    return f"{ANCHOR_PREFIX}{citation_id}"


@dataclass(frozen=True)
class Citation:
    """요약문 한 문장이 근거로 삼은 회의록 위치."""

    citation_id: str            # ②가 부여. 요약문의 [id] 표기와 일치해야 한다
    chunk_id: str = ""          # {conference_number}-{question_number}
    label: str = ""             # 예) "21대 복지위 3차, 김OO 위원"
    snippet: str = ""           # 원문 미리보기 한 줄
    meta: dict = field(default_factory=dict)

    @property
    def anchor(self) -> str:
        return anchor_for(self.citation_id)

    @classmethod
    def from_search_result(cls, result) -> "Citation":
        """②의 SearchResult(dict 또는 dataclass)를 각주로 변환.

        필드명은 Day 1에 동결한 common/schemas.py 기준으로 맞춘다.
        """
        get = result.get if isinstance(result, dict) else lambda k, d=None: getattr(result, k, d)
        return cls(
            citation_id=str(get("citation_id", "")),
            chunk_id=str(get("chunk_id", "")),
            label=str(get("speaker", "") or get("agenda", "") or get("chunk_id", "")),
            snippet=str(get("text", ""))[:80],
        )

    def to_html(self) -> str:
        head = (
            f'<a href="{escape(self.anchor)}">'
            f'[{escape(self.citation_id)}] {escape(self.label)}</a>'
        )
        if not self.snippet:
            return head
        return f'{head}<br><span style="color:#6b7280;">{escape(self.snippet)}</span>'


class CitationWidget(QWidget):
    """각주 목록. 각주 클릭 시 원문 앵커 id를 emit 한다."""

    citation_clicked = Signal(str)

    EMPTY_TEXT = "이 요약에는 연결된 출처가 없습니다."

    def __init__(self, parent: QWidget | None = None, title: str = "출처") -> None:
        super().__init__(parent)
        self._citations: List[Citation] = []

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 8, 0, 0)
        self.layout.setSpacing(4)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-weight:600;")

        self.body_label = QLabel()
        self.body_label.setTextFormat(Qt.RichText)
        self.body_label.setWordWrap(True)
        self.body_label.setOpenExternalLinks(False)
        self.body_label.setTextInteractionFlags(
            Qt.TextBrowserInteraction | Qt.TextSelectableByMouse
        )
        self.body_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        self.body_label.linkActivated.connect(self.citation_clicked.emit)

        self.layout.addWidget(self.title_label)
        self.layout.addWidget(self.body_label)
        self.set_citations([])

    # ------------------------------------------------------------------ API
    def set_citations(self, citations: Iterable[Citation]) -> None:
        self._citations = list(citations)
        if not self._citations:
            self.body_label.setText(
                f'<span style="color:#6b7280;">{self.EMPTY_TEXT}</span>')
            return
        self.body_label.setText("<br>".join(c.to_html() for c in self._citations))

    def citations(self) -> List[Citation]:
        return list(self._citations)

    def clear(self) -> None:
        self.set_citations([])
