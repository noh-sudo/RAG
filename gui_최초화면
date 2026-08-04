# -*- coding: utf-8 -*-
"""
국민의 소리 - 첫 화면(랜딩) + 전문가모드 / 쉬운모드 전환 데모
------------------------------------------------------------
- 첫 화면 배경: 첨부한 국회의사당 드론(부감) 사진을 그대로 배경으로 사용한다.
  같은 폴더에 있는 "assembly_background.jpg" 파일을 불러와 창 크기에 맞게
  꽉 채워서(비율 유지 + 크롭) 그린다.
- 전문가모드 배경: 연한 하늘색 그라데이션
- 쉬운모드 배경: 연한 보라색 그라데이션
- 중앙의 [전문가모드] / [쉬운모드] 버튼(파란 배경 + 흰 글자)을 누르면 각 화면으로 이동한다.

실행 방법 (PyCharm):
    1) 이 파일과 assembly_background.jpg 를 같은 폴더에 넣는다.
    2) 터미널에서 pip install PySide6
    3) 이 파일을 실행 (Run 'main')
"""

import os
import sys
from PySide6.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QComboBox, QListWidget, QTextEdit, QTabWidget,
    QGridLayout, QListWidgetItem, QSizePolicy
)
from PySide6.QtGui import QPainter, QLinearGradient, QColor, QFont, QPixmap
from PySide6.QtCore import Qt

# ---------------------------------------------------------------------------
# 경로 / 리소스
# ---------------------------------------------------------------------------

# 이 파일과 같은 폴더에 있는 배경 사진 경로. 실제 배포 시에는 assembly_background.jpg
# 파일을 이 py 파일과 동일한 폴더에 넣어두면 된다.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LANDING_IMAGE_PATH = os.path.join(BASE_DIR, "assembly_background.jpg")

# ---------------------------------------------------------------------------
# 공통 스타일
# ---------------------------------------------------------------------------

MAIN_BUTTON_STYLE = """
QPushButton {
    background-color: #1a56db;
    color: white;
    font-size: 22px;
    font-weight: bold;
    border-radius: 12px;
    padding: 22px 50px;
    border: none;
}
QPushButton:hover {
    background-color: #1e40af;
}
QPushButton:pressed {
    background-color: #163a91;
}
"""

MODE_BTN_ACTIVE = """
QPushButton {
    background-color: #1a56db;
    color: white;
    font-size: 13px;
    font-weight: bold;
    border-radius: 4px;
    padding: 6px 16px;
    border: none;
}
"""

MODE_BTN_INACTIVE = """
QPushButton {
    background-color: #e5e7eb;
    color: #333333;
    font-size: 13px;
    font-weight: bold;
    border-radius: 4px;
    padding: 6px 16px;
    border: none;
}
QPushButton:hover {
    background-color: #d1d5db;
}
"""

TOPIC_BTN_STYLE = """
QPushButton {
    background-color: #1a56db;
    color: white;
    font-size: 15px;
    font-weight: bold;
    border-radius: 8px;
    padding: 18px;
    border: none;
}
QPushButton:hover {
    background-color: #1e40af;
}
"""

# 창이 닫히지 않고 계속 살아있도록 참조를 붙잡아두는 전역 리스트
_open_windows = []


def _register(win):
    _open_windows.append(win)
    return win


# ---------------------------------------------------------------------------
# 배경 위젯 1: 실제 사진을 창 크기에 맞게 채우는 배경 (첫 화면용)
# ---------------------------------------------------------------------------

class PhotoBackground(QWidget):
    """실제 이미지 파일을 불러와 위젯 크기에 맞게(비율 유지 + 크롭) 채워 그리는 배경.

    글자 가독성을 위해 위에 반투명 어두운 오버레이를 한 겹 더 그린다.
    """

    def __init__(self, image_path: str, overlay_alpha: int = 90):
        super().__init__()
        self._overlay_alpha = overlay_alpha
        self._pixmap = QPixmap(image_path)
        if self._pixmap.isNull():
            print(f"[경고] 배경 이미지를 불러오지 못했다: {image_path}")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        if not self._pixmap.isNull():
            # 창 비율과 사진 비율이 달라도 여백 없이 꽉 차도록
            # KeepAspectRatioByExpanding 으로 확대한 뒤 가운데를 잘라서 그린다.
            scaled = self._pixmap.scaled(
                self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
            )
            crop_x = max(0, (scaled.width() - self.width()) // 2)
            crop_y = max(0, (scaled.height() - self.height()) // 2)
            painter.drawPixmap(0, 0, scaled, crop_x, crop_y, self.width(), self.height())
        else:
            # 이미지 로드 실패 시 대체 배경(짙은 회색)
            painter.fillRect(self.rect(), QColor(50, 60, 70))

        # 흰 글자 가독성을 위한 반투명 어두운 오버레이
        painter.fillRect(self.rect(), QColor(0, 0, 0, self._overlay_alpha))
        painter.end()


# ---------------------------------------------------------------------------
# 배경 위젯 2: 은은한 두 색 그라데이션 배경 (전문가모드 / 쉬운모드용)
# ---------------------------------------------------------------------------

class GradientBackground(QWidget):
    """위에서 아래로 연한 색이 이어지는 은은한 그라데이션 배경."""

    def __init__(self, top_color: QColor, bottom_color: QColor):
        super().__init__()
        self._top_color = top_color
        self._bottom_color = bottom_color

    def paintEvent(self, event):
        painter = QPainter(self)
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0.0, self._top_color)
        gradient.setColorAt(1.0, self._bottom_color)
        painter.fillRect(self.rect(), gradient)
        painter.end()


# 전문가모드: 연한 하늘색 그라데이션
EXPERT_GRADIENT_TOP = QColor(232, 244, 255)
EXPERT_GRADIENT_BOTTOM = QColor(196, 225, 250)

# 쉬운모드: 연한 보라색 그라데이션
EASY_GRADIENT_TOP = QColor(245, 236, 255)
EASY_GRADIENT_BOTTOM = QColor(220, 198, 245)


# ---------------------------------------------------------------------------
# 1) 첫 화면 (랜딩) - 실제 사진 배경 + 모드 선택 버튼
# ---------------------------------------------------------------------------

class LandingWindow(PhotoBackground):
    def __init__(self):
        super().__init__(LANDING_IMAGE_PATH, overlay_alpha=90)
        self.setWindowTitle("국민의 소리")
        self.resize(900, 650)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(40)

        title = QLabel("국민의 소리")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: white; font-size: 40px; font-weight: bold;")
        layout.addWidget(title)

        subtitle = QLabel("원하시는 화면을 선택해 주세요")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: white; font-size: 16px;")
        layout.addWidget(subtitle)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(60)
        btn_row.setAlignment(Qt.AlignCenter)

        self.expert_btn = QPushButton("전문가모드")
        self.expert_btn.setStyleSheet(MAIN_BUTTON_STYLE)
        self.expert_btn.setCursor(Qt.PointingHandCursor)
        self.expert_btn.clicked.connect(self.go_expert_mode)

        self.easy_btn = QPushButton("쉬운모드")
        self.easy_btn.setStyleSheet(MAIN_BUTTON_STYLE)
        self.easy_btn.setCursor(Qt.PointingHandCursor)
        self.easy_btn.clicked.connect(self.go_easy_mode)

        btn_row.addWidget(self.expert_btn)
        btn_row.addWidget(self.easy_btn)
        layout.addLayout(btn_row)

    def go_expert_mode(self):
        win = _register(ExpertModeWindow())
        win.show()
        self.close()

    def go_easy_mode(self):
        win = _register(EasyModeWindow())
        win.show()
        self.close()


# ---------------------------------------------------------------------------
# 상단 공통 모드 전환 버튼 바 (스크린샷 우측 상단 [전문가모드][쉬운모드])
# ---------------------------------------------------------------------------

def build_mode_switch_bar(parent_window, active_mode):
    """active_mode: 'expert' 또는 'easy'"""
    bar = QHBoxLayout()
    bar.addStretch()

    expert_btn = QPushButton("전문가모드")
    easy_btn = QPushButton("쉬운모드")

    if active_mode == "expert":
        expert_btn.setStyleSheet(MODE_BTN_ACTIVE)
        easy_btn.setStyleSheet(MODE_BTN_INACTIVE)
    else:
        expert_btn.setStyleSheet(MODE_BTN_INACTIVE)
        easy_btn.setStyleSheet(MODE_BTN_ACTIVE)

    def to_expert():
        win = _register(ExpertModeWindow())
        win.show()
        parent_window.close()

    def to_easy():
        win = _register(EasyModeWindow())
        win.show()
        parent_window.close()

    expert_btn.clicked.connect(to_expert)
    easy_btn.clicked.connect(to_easy)

    bar.addWidget(expert_btn)
    bar.addWidget(easy_btn)
    return bar


# ---------------------------------------------------------------------------
# 2) 전문가모드 화면 - 연한 하늘색 그라데이션 배경
# ---------------------------------------------------------------------------

class ExpertModeWindow(GradientBackground):
    def __init__(self):
        super().__init__(EXPERT_GRADIENT_TOP, EXPERT_GRADIENT_BOTTOM)
        self.setWindowTitle("국민의 소리 - 전문가모드")
        self.resize(900, 650)

        root = QVBoxLayout(self)

        root.addLayout(build_mode_switch_bar(self, active_mode="expert"))

        header = QLabel("국민의 소리")
        header.setStyleSheet("font-size: 20px; font-weight: bold;")
        root.addWidget(header)

        search_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("궁금한 안건이나 발언을 검색하세요")
        search_row.addWidget(self.search_input)
        root.addLayout(search_row)

        filter_row = QHBoxLayout()
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["정렬"])
        self.term_combo = QComboBox()
        self.term_combo.addItems(["대수"])
        self.topic_combo = QComboBox()
        self.topic_combo.addItems(["주제"])
        search_btn = QPushButton("검색")
        search_btn.clicked.connect(self.on_search)

        filter_row.addWidget(self.sort_combo)
        filter_row.addWidget(self.term_combo)
        filter_row.addWidget(self.topic_combo)
        filter_row.addStretch()
        filter_row.addWidget(search_btn)
        root.addLayout(filter_row)

        body_row = QHBoxLayout()

        left_col = QVBoxLayout()
        left_col.addWidget(QLabel("검색 결과"))
        self.result_list = QListWidget()
        self.result_list.addItem(QListWidgetItem("(검색 결과가 여기에 표시됩니다)"))
        left_col.addWidget(self.result_list)
        body_row.addLayout(left_col, 1)

        right_col = QVBoxLayout()
        self.tabs = QTabWidget()
        self.summary_view = QTextEdit()
        self.summary_view.setPlaceholderText("AI 요약본이 여기에 표시됩니다.")
        self.raw_view = QTextEdit()
        self.raw_view.setPlaceholderText("회의록 원문이 여기에 표시됩니다.")
        self.tabs.addTab(self.summary_view, "AI 요약본")
        self.tabs.addTab(self.raw_view, "회의록 원문")
        right_col.addWidget(self.tabs)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        save_btn = QPushButton("저장")
        download_btn = QPushButton("다운로드")
        btn_row.addWidget(save_btn)
        btn_row.addWidget(download_btn)
        right_col.addLayout(btn_row)

        body_row.addLayout(right_col, 2)
        root.addLayout(body_row)

    def on_search(self):
        # TODO: 실제 검색/AI 요약 로직을 여기에 연결하세요.
        pass


# ---------------------------------------------------------------------------
# 3) 쉬운모드 화면 - 연한 보라색 그라데이션 배경
# ---------------------------------------------------------------------------

class EasyModeWindow(GradientBackground):
    def __init__(self):
        super().__init__(EASY_GRADIENT_TOP, EASY_GRADIENT_BOTTOM)
        self.setWindowTitle("국민의 소리 - 쉬운모드")
        self.resize(900, 650)

        root = QVBoxLayout(self)

        root.addLayout(build_mode_switch_bar(self, active_mode="easy"))

        header = QLabel("국민의 소리")
        header.setStyleSheet("font-size: 20px; font-weight: bold;")
        root.addWidget(header)

        info = QLabel("요약설명 쉬운모드는 고령자 친화적인 화면입니다.")
        info.setStyleSheet("font-size: 14px; color: #444;")
        root.addWidget(info)

        root.addWidget(QLabel("주제 선택하기"))
        topic_grid = QGridLayout()
        topics = ["정치/경제/사회", "국방/안보/외교", "교육/문화/통일", "노동/사회"]
        for i, name in enumerate(topics):
            btn = QPushButton(name)
            btn.setStyleSheet(TOPIC_BTN_STYLE)
            btn.clicked.connect(lambda _, t=name: self.on_topic_selected(t))
            topic_grid.addWidget(btn, i // 4, i % 4)
        root.addLayout(topic_grid)

        root.addWidget(QLabel("요약 내용"))
        self.summary_box = QTextEdit()
        self.summary_box.setPlaceholderText("(검색 결과를 기다리는 중...)")
        root.addWidget(self.summary_box)

        root.addWidget(QLabel("어려운 용어 설명"))
        self.term_box = QTextEdit()
        self.term_box.setPlaceholderText("(용어 설명이 없습니다)")
        root.addWidget(self.term_box)

    def on_topic_selected(self, topic_name):
        # TODO: 주제 클릭 시 실제 검색/요약 로직을 여기에 연결하세요.
        self.summary_box.setPlainText(f"'{topic_name}' 관련 내용을 불러오는 중입니다...")


# ---------------------------------------------------------------------------
# 실행부
# ---------------------------------------------------------------------------

def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Malgun Gothic", 10))

    landing = _register(LandingWindow())
    landing.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
