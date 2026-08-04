"""전문가모드 패널 (대시보드 A).  [소유: ③]

검색창 · 필터 · 결과 목록 · 요약/원문 탭.
데이터는 ②의 ModeManager를 호출해서만 얻는다. 세션 캐시는 직접 만지지 않는다.
②의 실물 인터페이스(H2, Day 2)가 나오기 전까지는 _StubService로 단독 실행한다.
"""

from __future__ import annotations

from typing import Iterable, List, Optional, Sequence
import uuid

from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from gui.citation_widget import Citation, CitationWidget, anchor_for
from common.schemas import (
    RemoteQueryRequest,
    RemoteQueryResponse,
    RetrievedChunk,
    SearchFilters,
    Mode,
    ExpertSummaryResponse,
    ModeSwitchRequest,
    ModeSwitchResponse
)

SUMMARY_TAB = 0
RAW_TAB = 1

SORTS = ["관련순", "최신순"]
CATEGORY_QUERIES = {
    "정치/경제": "정치 경제",
    "국방/안보/외교": "국방 안보 외교",
    "교육/문화/통일": "교육 문화 통일",
    "노동/사회": "노동 사회",
}

GRADIENT_TOP = QColor(232, 244, 255)      # 연한 하늘색
GRADIENT_BOTTOM = QColor(196, 225, 250)

# 거부 응답 문구는 ③④ 소유. ②는 found=False와 top_similarity만 준다.
NO_EVIDENCE_TEXT = (
    "<p>회의록에서 이 질문에 답할 근거를 찾지 못했습니다.</p>"
    "<p style='color:#6b7280;'>대수·기간 필터를 넓히거나, 회의에서 실제로 다뤘을 만한 "
    "표현으로 바꿔 검색해 보세요.</p>"
)

class SearchWorker(QThread):
    """NetworkClient.query()를 백그라운드 스레드에서 실행한다.
    GUI 스레드를 막지 않기 위한 필수 구조 (인터페이스 정의서 §3.2)."""

    succeeded = Signal(object)   # RemoteQueryResponse
    failed = Signal(str)         # 에러 메시지

    def __init__(self, network_client, request, parent=None):
        super().__init__(parent)
        self.network_client = network_client
        self.request = request

    def run(self) -> None:
        try:
            response = self.network_client.query(self.request)
            self.succeeded.emit(response)
        except Exception as exc:
            self.failed.emit(str(exc))

class ModeSwitchWorker(QThread):
    """NetworkClient.switch_mode()를 백그라운드 스레드에서 실행한다."""

    succeeded = Signal(object)   # ModeSwitchResponse
    failed = Signal(str)

    def __init__(self, network_client, request, parent=None):
        super().__init__(parent)
        self.network_client = network_client
        self.request = request

    def run(self) -> None:
        try:
            response = self.network_client.switch_mode(self.request)
            self.succeeded.emit(response)
        except Exception as exc:
            self.failed.emit(str(exc))

class ExpertPanel(QWidget):
    """시그널
        busy_changed(bool)      요청 중 여부. 셸이 모드 토글을 잠그는 데 쓴다
        status_message(str)     상태바 문구
    """

    busy_changed = Signal(bool)
    status_message = Signal(str)

    def __init__(self, network_client=None, session_id: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.network_client = network_client
        self.session_id = session_id or str(uuid.uuid4())
        self._last_response = None
        
        self._results: List[dict] = []
        self._busy = False
        self._selected_category = None

        self.layout = QVBoxLayout(self)
        self._build_search()
        self._build_body()
        self._connect()

    # ------------------------------------------------------------------ 구성
    def _build_search(self) -> None:
        self.search = QLineEdit()
        self.search.setPlaceholderText("궁금한 안건이나 발언을 검색하세요")
        self.search.setClearButtonEnabled(True)

        self.sort = QComboBox()
        self.sort.addItems(SORTS)
        self.search_button = QPushButton("검색")

        self.search_layout = QHBoxLayout()
        self.search_layout.addWidget(self.search)
        self.search_layout.addWidget(self.search_button)        

        self.category_buttons = {}
        self.filter_layout = QHBoxLayout()
        for label in CATEGORY_QUERIES:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.clicked.connect(lambda _, name=label: self._on_category_clicked(name))
            self.category_buttons[label] = btn
            self.filter_layout.addWidget(btn)

        self.layout.addLayout(self.search_layout)
     
    def _build_body(self) -> None:
        self.result_layout = QVBoxLayout()
        self.result_layout.addLayout(self.filter_layout)
        self.result_filtering = QHBoxLayout()
        self.result_title = QLabel("검색 결과")
        self.result_list = QListWidget()
        self.result_list.setMinimumWidth(260)
        self.result_filtering.addWidget(self.result_title)
        self.result_filtering.addWidget(self.sort)
        self.result_layout.addLayout(self.result_filtering)
        self.result_layout.addWidget(self.result_list)

        self.content_tab = QTabWidget()

        self.summary_page = QWidget()
        self.sum_layout = QVBoxLayout(self.summary_page)
        self.summary_title = QLabel()
        self.summary_title.setStyleSheet("font-weight:600;")
        self.summary = QTextBrowser()
        self.summary.setOpenExternalLinks(False)
        self.citation_widget = CitationWidget()
        self.sum_layout.addWidget(self.summary_title)
        self.sum_layout.addWidget(self.summary)
        self.sum_layout.addWidget(self.citation_widget)

        self.raw_page = QWidget()
        self.raw_layout = QVBoxLayout(self.raw_page)
        self.raw_title = QLabel()
        self.raw_title.setStyleSheet("font-weight:600;")
        self.raw = QTextBrowser()
        self.raw.setOpenExternalLinks(False)
        self.raw_layout.addWidget(self.raw_title)
        self.raw_layout.addWidget(self.raw)

        self.content_tab.addTab(self.summary_page, "AI 요약본")
        self.content_tab.addTab(self.raw_page, "회의록 원문")

        self.main_layout = QHBoxLayout()
        self.main_layout.addLayout(self.result_layout, 1)
        self.main_layout.addWidget(self.content_tab, 2)
        self.layout.addLayout(self.main_layout)
        self.clear_document()

    def paintEvent(self, event):
        painter = QPainter(self)
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0.0, GRADIENT_TOP)
        gradient.setColorAt(1.0, GRADIENT_BOTTOM)
        painter.fillRect(self.rect(), gradient)
        painter.end()

    def _connect(self) -> None:
        self.search.returnPressed.connect(self.run_search)
        self.search_button.clicked.connect(self.run_search)
        self.result_list.currentItemChanged.connect(self._on_result_selected)
        self.citation_widget.citation_clicked.connect(self.jump_to_source)
        self.sort.currentTextChanged.connect(self.on_sort_changed)

    # ------------------------------------------------------------------ 검색
    def current_request(self) -> RemoteQueryRequest:
        keyword = self.search.text().strip()
        category_query = (
            CATEGORY_QUERIES[self._selected_category]
            if self._selected_category else "")
        combined_query = f"{keyword} {category_query}".strip()

        return RemoteQueryRequest(
            session_id=self.session_id,
            query=combined_query,
            filters=SearchFilters(),
            mode=Mode.EXPERT,
            top_k=5,
        )

    def _sorted_results(self, sort_key: str) -> list[RetrievedChunk]:
        """sort_key: 'similarity' 또는 'recent'"""
        if sort_key == "recent":
            return sorted(self._results, key=lambda r: r.meeting_date, reverse=True)
        return sorted(self._results, key=lambda r: r.dense_similarity, reverse=True)


    def run_search(self) -> None:
        if self._busy:
            return
        if not self.search.text().strip() and self._selected_category is None:
            self.status_message.emit("검색어를 입력하거나 주제를 선택해주세요.")
            return
        self._set_busy(True)

        self._worker = SearchWorker(self.network_client, self.current_request())
        self._worker.succeeded.connect(self._on_search_succeeded)
        self._worker.failed.connect(self._on_search_failed)
        self._worker.finished.connect(lambda: self._set_busy(False))
        self._worker.start()

    def on_mode_activated(self) -> None:
        """상단 토글로 전문가모드가 활성화될 때 MainWindow가 호출한다.
        검색을 다시 하지 않고 서버 세션 캐시로 재생성만 요청한다 (§4.5)."""
        if self._busy or self._last_response is None:
            return  # 아직 검색을 한 적 없으면 전환할 것이 없다
        if not self._last_response.found:
            return  # 근거 없음 상태는 전환해도 유지 (§4.5 분기)

        self._set_busy(True)
        request = ModeSwitchRequest(session_id=self.session_id, new_mode=Mode.EXPERT)

        self._mode_worker = ModeSwitchWorker(self.network_client, request)
        self._mode_worker.succeeded.connect(self._on_mode_switch_succeeded)
        self._mode_worker.failed.connect(self._on_mode_switch_failed)
        self._mode_worker.finished.connect(lambda: self._set_busy(False))
        self._mode_worker.finished.connect(self._mode_worker.deleteLater)
        self._mode_worker.start()

    def _on_mode_switch_succeeded(self, response) -> None:
        if response.response is None:
            return
        self._last_response.response = response.response
        summary = response.response
        citations = [Citation.from_search_result(r) for r in self._results]
        self.summary.setHtml(summary.summary_text)
        self.summary.verticalScrollBar().setValue(0)   
        self.citation_widget.set_citations(citations)
        self.status_message.emit(
            "모드 전환 완료" + (" (캐시 재사용)" if response.cache_hit else "")
        )

    def _on_mode_switch_failed(self, error_message: str) -> None:
        self.status_message.emit(f"모드 전환 오류: {error_message}")

    def _on_search_succeeded(self, response) -> None:
        self._last_response = response
        self._results = list(response.chunks)
        self.set_results(self._sorted_results(self.current_sort_key()))

        if not response.found:
            self.summary_title.setText("근거 없음")
            self.summary.setHtml(NO_EVIDENCE_TEXT)
            self.citation_widget.clear()
            self.raw.setHtml("")
            self.content_tab.setCurrentIndex(SUMMARY_TAB)
            self.status_message.emit(
                f"근거 없음 (최고 유사도 {response.top_similarity:.2f})")
            return
        self.status_message.emit(f"검색 결과 {len(self._results)}건")
        if self._results:
            self.result_list.setCurrentRow(0)

    def _on_search_failed(self, error_message: str) -> None:
        self.summary_title.setText("서버 연결 실패")
        self.summary.setHtml(f"<p>{error_message}</p>")
        self.status_message.emit(f"오류: {error_message}")

    def set_results(self, results: Sequence[RetrievedChunk]) -> None:
        self.result_list.blockSignals(True)
        self.result_list.clear()
        for result in results:
            label = f"{result.chunk_id} · {result.speaker}"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, result.chunk_id)
            self.result_list.addItem(item)
        self.result_list.blockSignals(False)
        self.result_title.setText(f"검색 결과 {len(results)}건")
        if not results:
            self.clear_document()

    # ------------------------------------------------------------------ 표시
    def show_document(self, chunk_id: str) -> None:
        if self._last_response is None or self._last_response.response is None:
            return

        summary = self._last_response.response  # ExpertSummaryResponse
        citations = [Citation.from_search_result(r) for r in self._results]

        self.summary_title.setText(chunk_id)
        self.summary.setHtml(summary.summary_text)
        self.summary.verticalScrollBar().setValue(0)   
        self.citation_widget.set_citations(citations)
        self.raw_title.setText(f"{chunk_id} — 회의록 원문")
        self.raw.setHtml(self._build_raw_html(self._results))
        self.raw.verticalScrollBar().setValue(0)  
        self.content_tab.setCurrentIndex(SUMMARY_TAB)

    def current_sort_key(self) -> str:
        return "recent" if self.sort.currentText() == "최신순" else "similarity"

    def on_sort_changed(self) -> None:
        if not self._results:
            return
        self.set_results(self._sorted_results(self.current_sort_key()))

    def _on_category_clicked(self, label: str) -> None:
        """주제 버튼은 토글이다. 같은 버튼을 다시 누르면 해제된다."""
        if self._busy:
            self.category_buttons[label].setChecked(
                self._selected_category == label)
            return

        self._selected_category = (
            None if self._selected_category == label else label)
        for name, btn in self.category_buttons.items():
            btn.setChecked(name == self._selected_category)

        self.run_search()

    @staticmethod
    def _build_raw_html(results: Sequence[RetrievedChunk]) -> str:
        """각주 클릭으로 점프할 앵커를 심어 원문을 만든다."""
        parts = []
        for result in results:
            anchor = anchor_for(str(result.citation_id))
            parts.append(
                f'<p><a name="{anchor}"></a><b>{result.speaker}</b> '
                f'{result.text}</p>'
            )
        return "".join(parts)

    def clear_document(self) -> None:
        self.summary_title.setText("결과를 선택하면 요약이 표시됩니다.")
        self.summary.setHtml("")
        self.raw_title.setText("")
        self.raw.setHtml("")
        self.citation_widget.clear()

    def jump_to_source(self, anchor: str) -> None:
        self.content_tab.setCurrentIndex(RAW_TAB)
        self.raw.scrollToAnchor(anchor)

    # -------------------------------------------------------------- private
    def _set_busy(self, busy: bool) -> None:
        """요청 중 검색·저장 버튼을 잠근다. 연타로 중복 요청이 쌓이지 않게."""
        self._busy = busy
        for widget in (self.search, self.search_button, self.sort, self.result_list):
            widget.setEnabled(not busy)
        for btn in self.category_buttons.values():
            btn.setEnabled(not busy)
        self.busy_changed.emit(busy)

    def _on_result_selected(self, current: Optional[QListWidgetItem], _prev=None) -> None:
        if current is None:
            self.clear_document()
            return
        self.show_document(current.data(Qt.UserRole))

    @staticmethod
    def _combo_value(combo: QComboBox, placeholder: str) -> Optional[str]:
        value = combo.currentText()
        return None if value == placeholder else value
