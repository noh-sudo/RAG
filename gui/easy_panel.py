"""
쉬운모드 GUI 패널 (gui/easy_panel.py)
국민의 소리 - 고령자 친화 대시보드 B

역할:
- 카테고리 버튼 4개 (정치/경제/외교/사회)
- 3문답 요약 표시 (결정/이유/변화)
- 용어 풀이 위젯 통합
- 고령자를 위한 큰 글씨, 굵은 폰트
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QScrollArea
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Signal, QThread

from common.schemas import (
    RemoteQueryRequest, RemoteQueryResponse, RetrievedChunk,
    SearchFilters, Mode, EasySummaryResponse
)
from gui.glossary_widget import GlossaryWidget

class _StubService:
    """②의 H2 인터페이스가 나오기 전까지 쓰는 고정 응답. Day 5 통합 때 교체한다."""

    def query(self, request: RemoteQueryRequest) -> RemoteQueryResponse:
        if not request.filters.category:
            return RemoteQueryResponse(
                session_id=request.session_id,
                found=False,
                top_similarity=0.0,
                chunks=[],
                response=None,
                error=None,
                search_time_ms=0,
            )
        return RemoteQueryResponse(
            session_id=request.session_id,
            found=True,
            top_similarity=0.71,
            chunks=[
                RetrievedChunk(
                    chunk_id="052147-0002",
                    text="간병비 부담이 가구 소득의 절반을 넘는 사례가 늘고 있습니다.",
                    dense_similarity=0.71,
                    meeting_date="2024-09-01",
                    meeting_label="제422회 본회의 3차",
                    speaker="김OO 위원 → 이OO 장관",
                    citation_id=1,
                ),
            ],
            response=EasySummaryResponse(
                decision="간병비 지원을 늘리기로 했어요.",
                reason="어르신 돌봄 비용이 너무 많이 들어서 걱정하는 분들이 많았어요.",
                change="내년부터 10개 지역에서 먼저 시범적으로 지원이 시작돼요.",
                glossary=[
                    {"term": "시범사업", "definition": "본격 시행 전에 일부 지역에서 먼저 해보는 것"},
                ],
                generated_at="2024-09-01T00:00:00",
            ),
            error=None,
            search_time_ms=110,
        )

class SearchWorker(QThread):
    """NetworkClient.query()를 백그라운드 스레드에서 실행한다."""

    succeeded = Signal(object)
    failed = Signal(str)

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

class EasyPanel(QWidget):
    """쉬운모드 패널 - 고령자 친화 인터페이스"""

    # Signal 정의
    search_requested = Signal(RemoteQueryRequest)
    mode_switch_requested = Signal(dict)
    busy_changed = Signal(bool)
    status_message = Signal(str)

    # 카테고리 매핑
    CATEGORY_MAP = {
        "나라 살림": "cat_politics",
        "물가와 일자리": "cat_economy",
        "안보와 통일": "cat_diplomacy",
        "교육·복지": "cat_society"
    }

    def __init__(self, network_client=None, parent=None):
        super().__init__(parent)
        self.network_client = network_client or _StubService()
        self.session_id = "easy_mode"
        self.current_response = None
        self._busy = False
        self.init_ui()

    def init_ui(self):
        """UI 초기화"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        self.setStyleSheet("background-color: white;")

        # ────── 1. 헤더 타이틀 ──────────
        header_layout = QHBoxLayout()
        title_label = QLabel("요약설명 쉬운모드")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #333333;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        main_layout.addLayout(header_layout)

        # ────── 2. 카테고리 버튼 섹션 ──────────
        category_label = QLabel("주제 선택하기")
        category_font = QFont()
        category_font.setPointSize(14)
        category_font.setBold(True)
        category_label.setFont(category_font)
        main_layout.addWidget(category_label)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)

        self.category_buttons = {}
        for category_name in self.CATEGORY_MAP.keys():
            btn = self._create_category_button(category_name)
            self.category_buttons[category_name] = btn
            button_layout.addWidget(btn)

        main_layout.addLayout(button_layout)

        # ────── 3. 3문답 요약 섹션 ──────────
        summary_label = QLabel("요약 내용")
        summary_font = QFont()
        summary_font.setPointSize(14)
        summary_font.setBold(True)
        summary_label.setFont(summary_font)
        main_layout.addWidget(summary_label)

        # 스크롤 영역
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet(
            "QScrollArea { border: 1px solid #cccccc; background-color: white; }"
        )

        summary_widget = QWidget()
        summary_layout = QVBoxLayout(summary_widget)
        summary_layout.setContentsMargins(15, 15, 15, 15)
        summary_layout.setSpacing(15)

        # 결정사항
        decision_title = QLabel("📌 무엇을 결정했나요?")
        decision_title_font = QFont()
        decision_title_font.setPointSize(13)
        decision_title_font.setBold(True)
        decision_title.setFont(decision_title_font)
        decision_title.setStyleSheet("color: #0052CC;")
        summary_layout.addWidget(decision_title)

        self.decision_text = QLabel("(검색 결과를 기다리는 중...)")
        self.decision_text.setWordWrap(True)
        self.decision_text.setStyleSheet("color: #333333; line-height: 1.6;")
        decision_font = QFont()
        decision_font.setPointSize(12)
        decision_font.setBold(True)
        self.decision_text.setFont(decision_font)
        self.decision_text.setMinimumHeight(60)
        summary_layout.addWidget(self.decision_text)

        # 이유
        reason_title = QLabel("💭 왜 이런 이야기를 했나요?")
        reason_title_font = QFont()
        reason_title_font.setPointSize(13)
        reason_title_font.setBold(True)
        reason_title.setFont(reason_title_font)
        reason_title.setStyleSheet("color: #0052CC;")
        summary_layout.addWidget(reason_title)

        self.reason_text = QLabel("(검색 결과를 기다리는 중...)")
        self.reason_text.setWordWrap(True)
        self.reason_text.setStyleSheet("color: #333333; line-height: 1.6;")
        reason_font = QFont()
        reason_font.setPointSize(12)
        reason_font.setBold(True)
        self.reason_text.setFont(reason_font)
        self.reason_text.setMinimumHeight(60)
        summary_layout.addWidget(self.reason_text)

        # 변화
        change_title = QLabel("🔄 앞으로 무엇이 바뀌나요?")
        change_title_font = QFont()
        change_title_font.setPointSize(13)
        change_title_font.setBold(True)
        change_title.setFont(change_title_font)
        change_title.setStyleSheet("color: #0052CC;")
        summary_layout.addWidget(change_title)

        self.change_text = QLabel("(검색 결과를 기다리는 중...)")
        self.change_text.setWordWrap(True)
        self.change_text.setStyleSheet("color: #333333; line-height: 1.6;")
        change_font = QFont()
        change_font.setPointSize(12)
        change_font.setBold(True)
        self.change_text.setFont(change_font)
        self.change_text.setMinimumHeight(60)
        summary_layout.addWidget(self.change_text)

        summary_layout.addStretch()
        scroll_area.setWidget(summary_widget)
        main_layout.addWidget(scroll_area, 1)

        # ────── 4. 용어 풀이 위젯 ──────────
        glossary_label = QLabel("어려운 용어 설명")
        glossary_font = QFont()
        glossary_font.setPointSize(14)
        glossary_font.setBold(True)
        glossary_label.setFont(glossary_font)
        main_layout.addWidget(glossary_label)

        self.glossary_widget = GlossaryWidget()
        main_layout.addWidget(self.glossary_widget, 1)

        # 신호 연결
        self._connect_signals()

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.enable_buttons(not busy)

    def _create_category_button(self, category_name: str) -> QPushButton:
        """카테고리 버튼 생성"""
        btn = QPushButton(category_name)
        btn.setMinimumHeight(60)
        btn.setMinimumWidth(120)

        # 폰트 설정 - 큰 글씨, 굵음
        btn_font = QFont()
        btn_font.setPointSize(11)
        btn_font.setBold(True)
        btn.setFont(btn_font)

        # 스타일 설정 - 파란색 배경, 흰색 글씨
        btn.setStyleSheet("""
            QPushButton {
                background-color: #0052CC;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: bold;
                font-size: 11pt;
            }
            QPushButton:hover {
                background-color: #0040AA;
            }
            QPushButton:pressed {
                background-color: #003399;
            }
        """)

        btn.clicked.connect(
            lambda: self._on_category_clicked(category_name)
        )
        return btn

    def _on_category_clicked(self, category_name: str):
        """카테고리 버튼 클릭 핸들러"""
        if self._busy:
            return
        category_filter = self.CATEGORY_MAP[category_name]
        filters = SearchFilters(category=category_filter)
        request = RemoteQueryRequest(
            session_id=self.session_id,
            query="",
            filters=filters,
            mode=Mode.EASY,
            top_k=5
        )

        self._set_busy(True)
        self.busy_changed.emit(True)

        self._worker = SearchWorker(self.network_client, request)
        self._worker.succeeded.connect(self._on_search_succeeded)
        self._worker.failed.connect(self._on_search_failed)
        self._worker.finished.connect(self._on_search_finished)
        self._worker.start()

    def _on_search_succeeded(self, response) -> None:
        if not response.found:
            self.display_no_evidence()
            self.status_message.emit(
                f"근거 없음 (최고 유사도 {response.top_similarity:.2f})")
            return
        self.display_summary(response.response)
        self.status_message.emit(f"검색 결과 {len(response.chunks)}건")

    def _on_search_failed(self, error_message: str) -> None:
        self.display_no_evidence()
        self.status_message.emit(f"오류: {error_message}")

    def _on_search_finished(self) -> None:
        self._set_busy(False)
        self.busy_changed.emit(False)

    def _connect_signals(self):
        """신호 연결"""
        # 이 메서드는 추후 메인 윈도우와의 신호 연결을 위함
        pass

    def display_summary(self, response: EasySummaryResponse):
        """요약 결과 표시"""
        self.current_response = response

        # 결정사항 표시
        self.decision_text.setText(response.decision)

        # 이유 표시
        self.reason_text.setText(response.reason)

        # 변화 표시
        self.change_text.setText(response.change)

        # 용어 풀이 표시
        if response.glossary:
            glossary_items = [
                {"term": item.get("term", ""), "definition": item.get("definition", "")}
                for item in response.glossary
            ]
            self.glossary_widget.display_glossary(glossary_items)
        else:
            self.glossary_widget.clear()

    def display_no_evidence(self):
        """근거 없음 상태 표시"""
        self.decision_text.setText(
            "죄송하지만, 해당 주제에 대한 검색 결과를 찾을 수 없습니다.\n"
            "다른 주제를 선택하거나 다시 검색해주세요."
        )
        self.reason_text.setText("")
        self.change_text.setText("")
        self.glossary_widget.clear()

    def display_loading(self):
        """로딩 상태 표시"""
        self.decision_text.setText("📍 검색 중입니다. 잠시 기다려주세요...")
        self.reason_text.setText("")
        self.change_text.setText("")
        self.glossary_widget.clear()

    def reset(self):
        """초기 상태로 리셋"""
        self.decision_text.setText("(주제를 선택하면 결과가 표시됩니다)")
        self.reason_text.setText("")
        self.change_text.setText("")
        self.glossary_widget.clear()
        self.current_response = None

    def enable_buttons(self, enabled: bool = True):
        """카테고리 버튼 활성화/비활성화"""
        for btn in self.category_buttons.values():
            btn.setEnabled(enabled)
