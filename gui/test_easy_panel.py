# 스키마 테스트에서는 db연동을 해 봐야 알겠다. 애러 1건
"""
쉬운모드 테스트 및 데모 스크립트 (test_easy_panel.py)
PyCharm에서 직접 실행 가능

실행 방법:
    python test_easy_panel.py
"""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from PySide6.QtCore import Qt

# 공통 스키마 임포트 (프로젝트 구조에 맞게 수정)
from dataclasses import dataclass
from enum import Enum


# ────── 공통 스키마 정의 (실제는 common/schemas.py에서 임포트) ──────────
class Mode(str, Enum):
    EXPERT = "EXPERT"
    EASY = "EASY"


@dataclass
class SearchFilters:
    generation_no: int = None
    period_from: str = None
    period_to: str = None
    questioner: str = None
    category: str = None


@dataclass
class SearchRequest:
    session_id: str
    query: str
    filters: SearchFilters
    top_k: int = 5


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
    chunks: list = None
    search_time_ms: int = 0


@dataclass
class GenerationRequest:
    session_id: str
    query: str
    mode: Mode
    retrieved_chunks: list = None


@dataclass
class EasySummaryResponse:
    decision: str
    reason: str
    change: str
    glossary: list = None
    generated_at: str = ""


# ────── 쉬운모드 모듈 임포트 (직접 포함) ──────────

from PySide6.QtWidgets import (
    QPushButton, QLabel, QScrollArea, QMessageBox, QVBoxLayout, QHBoxLayout
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Signal, pyqtSignal

from typing import Optional


class GlossaryItem:
    """개별 용어-뜻풀이 카드 (간단한 버전)"""

    def __init__(self, term: str, definition: str):
        self.term = term
        self.definition = definition


class GlossaryWidget(QWidget):
    """용어 풀이 위젯 (간단한 버전)"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.glossary_cache = {}
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet(
            "QScrollArea { border: 1px solid #e0e0e0; background-color: white; }"
        )

        self.scroll_container = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_container)
        self.scroll_layout.setContentsMargins(10, 10, 10, 10)
        self.scroll_layout.setSpacing(10)

        self.empty_label = QLabel("(용어 설명이 없습니다)")
        empty_font = QFont()
        empty_font.setPointSize(11)
        empty_font.setItalic(True)
        self.empty_label.setFont(empty_font)
        self.empty_label.setStyleSheet("color: #999999;")

        self.scroll_layout.addWidget(self.empty_label)
        self.scroll_area.setWidget(self.scroll_container)
        layout.addWidget(self.scroll_area)

    def display_glossary(self, glossary_items: list[dict]):
        """용어 풀이 목록 표시"""
        self._clear_scroll_layout()

        if not glossary_items:
            self.scroll_layout.addWidget(self.empty_label)
            return

        for item in glossary_items:
            term = item.get("term", "").strip()
            definition = item.get("definition", "").strip()

            if not term or not definition:
                continue

            self.glossary_cache[term] = definition

            # 간단한 카드 표시
            card_layout = QVBoxLayout()

            term_label = QLabel(term)
            term_font = QFont()
            term_font.setPointSize(12)
            term_font.setBold(True)
            term_label.setFont(term_font)
            term_label.setStyleSheet("color: #0052CC;")

            def_label = QLabel(definition)
            def_label.setWordWrap(True)
            def_font = QFont()
            def_font.setPointSize(11)
            def_label.setFont(def_font)
            def_label.setStyleSheet("color: #333333;")

            card_layout.addWidget(term_label)
            card_layout.addWidget(def_label)

            card_widget = QWidget()
            card_widget.setLayout(card_layout)
            card_widget.setStyleSheet(
                "QWidget { background-color: #F0F5FF; border: 2px solid #0052CC; "
                "border-radius: 8px; padding: 12px; }"
            )

            self.scroll_layout.addWidget(card_widget)

        self.scroll_layout.addStretch()

    def _clear_scroll_layout(self):
        while self.scroll_layout.count():
            child = self.scroll_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def clear(self):
        self._clear_scroll_layout()
        self.scroll_layout.addWidget(self.empty_label)


class EasyPanel(QWidget):
    """쉬운모드 패널"""

    search_requested = pyqtSignal(SearchRequest)

    CATEGORY_MAP = {
        "나라 살림": "cat_politics",
        "물가와 일자리": "cat_economy",
        "안보와 통일": "cat_diplomacy",
        "교육·복지": "cat_society"
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.session_id = "easy_mode"
        self.current_response = None
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        self.setStyleSheet("background-color: white;")

        # 헤더
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

        # 카테고리 라벨
        category_label = QLabel("주제 선택하기")
        category_font = QFont()
        category_font.setPointSize(14)
        category_font.setBold(True)
        category_label.setFont(category_font)
        main_layout.addWidget(category_label)

        # 카테고리 버튼
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)
        self.category_buttons = {}

        for category_name in self.CATEGORY_MAP.keys():
            btn = QPushButton(category_name)
            btn.setMinimumHeight(60)
            btn.setMinimumWidth(120)

            btn_font = QFont()
            btn_font.setPointSize(11)
            btn_font.setBold(True)
            btn.setFont(btn_font)

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
                lambda checked, cat=category_name: self._on_category_clicked(cat)
            )
            self.category_buttons[category_name] = btn
            button_layout.addWidget(btn)

        main_layout.addLayout(button_layout)

        # 요약 라벨
        summary_label = QLabel("요약 내용")
        summary_font = QFont()
        summary_font.setPointSize(14)
        summary_font.setBold(True)
        summary_label.setFont(summary_font)
        main_layout.addWidget(summary_label)

        # 요약 스크롤 영역
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet(
            "QScrollArea { border: 1px solid #cccccc; background-color: white; }"
        )

        summary_widget = QWidget()
        summary_layout = QVBoxLayout(summary_widget)
        summary_layout.setContentsMargins(15, 15, 15, 15)
        summary_layout.setSpacing(15)

        # 결정
        decision_title = QLabel("📌 무엇을 결정했나요?")
        decision_title.setStyleSheet("color: #0052CC;")
        decision_title_font = QFont()
        decision_title_font.setPointSize(13)
        decision_title_font.setBold(True)
        decision_title.setFont(decision_title_font)
        summary_layout.addWidget(decision_title)

        self.decision_text = QLabel("(주제를 선택하면 결과가 표시됩니다)")
        self.decision_text.setWordWrap(True)
        decision_font = QFont()
        decision_font.setPointSize(12)
        decision_font.setBold(True)
        self.decision_text.setFont(decision_font)
        self.decision_text.setStyleSheet("color: #333333; line-height: 1.6;")
        self.decision_text.setMinimumHeight(60)
        summary_layout.addWidget(self.decision_text)

        # 이유
        reason_title = QLabel("💭 왜 이런 이야기를 했나요?")
        reason_title.setStyleSheet("color: #0052CC;")
        reason_title_font = QFont()
        reason_title_font.setPointSize(13)
        reason_title_font.setBold(True)
        reason_title.setFont(reason_title_font)
        summary_layout.addWidget(reason_title)

        self.reason_text = QLabel("")
        self.reason_text.setWordWrap(True)
        reason_font = QFont()
        reason_font.setPointSize(12)
        reason_font.setBold(True)
        self.reason_text.setFont(reason_font)
        self.reason_text.setStyleSheet("color: #333333; line-height: 1.6;")
        self.reason_text.setMinimumHeight(60)
        summary_layout.addWidget(self.reason_text)

        # 변화
        change_title = QLabel("🔄 앞으로 무엇이 바뀌나요?")
        change_title.setStyleSheet("color: #0052CC;")
        change_title_font = QFont()
        change_title_font.setPointSize(13)
        change_title_font.setBold(True)
        change_title.setFont(change_title_font)
        summary_layout.addWidget(change_title)

        self.change_text = QLabel("")
        self.change_text.setWordWrap(True)
        change_font = QFont()
        change_font.setPointSize(12)
        change_font.setBold(True)
        self.change_text.setFont(change_font)
        self.change_text.setStyleSheet("color: #333333; line-height: 1.6;")
        self.change_text.setMinimumHeight(60)
        summary_layout.addWidget(self.change_text)

        summary_layout.addStretch()
        scroll_area.setWidget(summary_widget)
        main_layout.addWidget(scroll_area, 1)

        # 용어 풀이
        glossary_label = QLabel("어려운 용어 설명")
        glossary_font = QFont()
        glossary_font.setPointSize(14)
        glossary_font.setBold(True)
        glossary_label.setFont(glossary_font)
        main_layout.addWidget(glossary_label)

        self.glossary_widget = GlossaryWidget()
        main_layout.addWidget(self.glossary_widget, 1)

    def _on_category_clicked(self, category_name: str):
        """카테고리 버튼 클릭"""
        category_filter = self.CATEGORY_MAP[category_name]

        filters = SearchFilters(category=category_filter)
        request = SearchRequest(
            session_id=self.session_id,
            query="",
            filters=filters,
            top_k=5
        )

        self.search_requested.emit(request)

    def display_summary(self, response: EasySummaryResponse):
        """요약 결과 표시"""
        self.decision_text.setText(response.decision)
        self.reason_text.setText(response.reason)
        self.change_text.setText(response.change)

        if response.glossary:
            glossary_items = [
                {"term": item.get("term", ""), "definition": item.get("definition", "")}
                for item in response.glossary
            ]
            self.glossary_widget.display_glossary(glossary_items)

    def display_no_evidence(self):
        """근거 없음 표시"""
        self.decision_text.setText(
            "죄송하지만, 해당 주제에 대한 검색 결과를 찾을 수 없습니다.\n"
            "다른 주제를 선택하거나 다시 검색해주세요."
        )
        self.reason_text.setText("")
        self.change_text.setText("")
        self.glossary_widget.clear()

    def reset(self):
        """리셋"""
        self.decision_text.setText("(주제를 선택하면 결과가 표시됩니다)")
        self.reason_text.setText("")
        self.change_text.setText("")
        self.glossary_widget.clear()


# ────── 메인 윈도우 및 데모 ──────────

class DemoWindow(QMainWindow):
    """쉬운모드 데모 윈도우"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("쉬운모드 데모 - 국민의 소리")
        self.setGeometry(100, 100, 1000, 900)

        # 쉬운모드 패널
        self.easy_panel = EasyPanel()
        self.setCentralWidget(self.easy_panel)

        # 신호 연결
        self.easy_panel.search_requested.connect(self._on_search_requested)

        # 더미 데이터로 테스트
        self._load_demo_data()

    def _on_search_requested(self, request: SearchRequest):
        """검색 요청 처리"""
        # 더미 요약 데이터 표시
        response = EasySummaryResponse(
            decision="국회에서는 저출생 문제 해결을 위해 영아 수당 제도를 신설하기로 결정했습니다.",
            reason="저출생으로 인한 국가 경제 위기가 심각해지고 있으며, 선진국의 사례에서도 "
                   "현금 지원이 효과적임을 확인했기 때문입니다.",
            change="앞으로 모든 영아 가정은 매달 100만원의 수당을 받게 되며, "
                   "이는 내년 1월부터 시행될 예정입니다.",
            glossary=[
                {
                    "term": "저출생",
                    "definition": "태어나는 아이의 수가 적어지는 현상입니다. 나라가 발전하면서 "
                                "아이를 적게 낳는 경향이 생기고 있습니다."
                },
                {
                    "term": "영아 수당",
                    "definition": "태어난 지 얼마 안 된 어린 아기가 있는 가정에 정부가 "
                                "매달 주는 돈입니다."
                },
                {
                    "term": "신설",
                    "definition": "새로 만드는 것입니다. 전에 없던 새로운 제도나 규칙을 "
                                "처음으로 만드는 것을 말합니다."
                }
            ],
            generated_at="2026-07-31T10:30:00Z"
        )
        self.easy_panel.display_summary(response)

    def _load_demo_data(self):
        """초기 데모 데이터 로드"""
        pass


def main():
    app = QApplication(sys.argv)
    window = DemoWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
