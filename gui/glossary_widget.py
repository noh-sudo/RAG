"""
용어 풀이 위젯 (gui/glossary_widget.py)
국민의 소리 - 어려운 용어 설명 모듈

역할:
- 요약문에 등장한 어려운 용어 추출 및 뜻풀이 표시
- 뜻풀이 캐시로 반복 조회 최소화
- 고령자를 위한 큰 글씨, 구분하기 쉬운 레이아웃
- 용어별 카드 형식으로 표시
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QScrollArea, QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor
from typing import Optional


class GlossaryItem(QFrame):
    """개별 용어-뜻풀이 카드"""

    def __init__(self, term: str, definition: str, parent=None):
        super().__init__(parent)
        self.term = term
        self.definition = definition
        self.init_ui()

    def init_ui(self):
        """카드 UI 초기화"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # 프레임 스타일 (연한 파란색 배경)
        self.setStyleSheet("""
            QFrame {
                background-color: #F0F5FF;
                border: 2px solid #0052CC;
                border-radius: 8px;
            }
        """)
        self.setFrameStyle(QFrame.StyledPanel | QFrame.Plain)

        # 용어명 (큰 글씨, 굵음, 파란색)
        term_label = QLabel(self.term)
        term_font = QFont()
        term_font.setPointSize(12)
        term_font.setBold(True)
        term_label.setFont(term_font)
        term_label.setStyleSheet("color: #0052CC;")
        layout.addWidget(term_label)

        # 뜻풀이 (읽기 쉬운 크기, 검은색)
        definition_label = QLabel(self.definition)
        definition_label.setWordWrap(True)
        definition_font = QFont()
        definition_font.setPointSize(11)
        definition_label.setFont(definition_font)
        definition_label.setStyleSheet(
            "color: #333333; line-height: 1.6; padding: 0px;"
        )
        layout.addWidget(definition_label)


class GlossaryWidget(QWidget):
    """용어 풀이 위젯 - 캐시 및 렌더링"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.glossary_cache = {}  # {term: definition} 캐시
        self.current_items = []   # 현재 표시 중인 아이템 목록
        self.init_ui()

    def init_ui(self):
        """UI 초기화"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(10)
        self.setStyleSheet("background-color: white;")

        # 스크롤 영역
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet(
            "QScrollArea { "
            "border: 1px solid #e0e0e0; "
            "background-color: white; "
            "}"
        )

        # 컨테이너 위젯
        self.scroll_container = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_container)
        self.scroll_layout.setContentsMargins(10, 10, 10, 10)
        self.scroll_layout.setSpacing(10)

        self.scroll_area.setWidget(self.scroll_container)
        main_layout.addWidget(self.scroll_area)

        # 빈 상태 라벨
        self.empty_label = QLabel("(용어 설명이 없습니다)")
        self.empty_label.setStyleSheet("color: #999999;")
        empty_font = QFont()
        empty_font.setPointSize(11)
        empty_font.setItalic(True)
        self.empty_label.setFont(empty_font)
        self.scroll_layout.addWidget(self.empty_label)

    def display_glossary(self, glossary_items: list[dict]):
        """
        용어 풀이 목록 표시

        Args:
            glossary_items: [{"term": "...", "definition": "..."}, ...]
        """
        # 스크롤 영역 초기화
        self._clear_scroll_layout()
        self.current_items = []

        if not glossary_items:
            self.scroll_layout.addWidget(self.empty_label)
            return

        # 각 용어 카드 추가
        for item in glossary_items:
            term = item.get("term", "").strip()
            definition = item.get("definition", "").strip()

            if not term or not definition:
                continue

            # 캐시에 저장
            self._cache_glossary_item(term, definition)

            # 카드 생성 및 추가
            card = GlossaryItem(term, definition)
            self.current_items.append(card)
            self.scroll_layout.addWidget(card)

        # 스트레치 추가 (아래 여백)
        self.scroll_layout.addStretch()

    def _cache_glossary_item(self, term: str, definition: str):
        """
        용어 풀이 캐시에 저장

        Args:
            term: 용어명
            definition: 뜻풀이
        """
        if term not in self.glossary_cache:
            self.glossary_cache[term] = definition

    def get_cached_definition(self, term: str) -> Optional[str]:
        """
        캐시에서 용어의 뜻풀이 조회

        Args:
            term: 용어명

        Returns:
            뜻풀이 문자열, 없으면 None
        """
        return self.glossary_cache.get(term)

    def _clear_scroll_layout(self):
        """스크롤 레이아웃 초기화"""
        while self.scroll_layout.count():
            child = self.scroll_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def clear(self):
        """용어 풀이 내용 초기화"""
        self._clear_scroll_layout()
        self.current_items = []
        self.scroll_layout.addWidget(self.empty_label)

    def get_cache_stats(self) -> dict:
        """캐시 통계 반환"""
        return {
            "cached_terms": len(self.glossary_cache),
            "displayed_items": len(self.current_items),
            "cache": self.glossary_cache.copy()
        }


class GlossaryManager:
    """
    용어 풀이 관리자 - 캐시 및 용어 추출 로직
    (선택사항: 향후 LLM 기반 용어 자동 추출 시 확장)
    """

    def __init__(self):
        self.global_cache = {}  # 애플리케이션 전역 캐시

    def cache_glossary(self, term: str, definition: str):
        """
        전역 캐시에 용어 저장

        Args:
            term: 용어명
            definition: 뜻풀이
        """
        if term and definition:
            self.global_cache[term] = definition

    def get_definition(self, term: str) -> Optional[str]:
        """
        전역 캐시에서 용어 조회

        Args:
            term: 용어명

        Returns:
            뜻풀이, 없으면 None
        """
        return self.global_cache.get(term)

    def bulk_cache(self, glossary_items: list[dict]):
        """
        여러 용어를 한 번에 캐시

        Args:
            glossary_items: [{"term": "...", "definition": "..."}, ...]
        """
        for item in glossary_items:
            term = item.get("term", "").strip()
            definition = item.get("definition", "").strip()
            if term and definition:
                self.cache_glossary(term, definition)

    def get_cache_info(self) -> dict:
        """캐시 정보 반환"""
        return {
            "total_cached_terms": len(self.global_cache),
            "cache_entries": self.global_cache.copy()
        }
