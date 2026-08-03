"""공통 셸.  [공통·동결 — Day 1 공동 작성. 변경은 4인 합의 후 1명이 대표 커밋]

제목 · 모드 토글 · QStackedWidget만 갖는다.
검색 상태와 데이터는 각 패널이 ②의 ModeManager를 호출해 직접 다룬다.
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from gui.easy_panel import EasyPanel
from gui.expert_panel import ExpertPanel

EXPERT_MODE = 0
EASY_MODE = 1


class MainWindow(QMainWindow):
    def __init__(self, network_client=None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("국민의 소리")
        self.resize(1100, 700)

        # TODO: 서버(server.py) 준비되면 아래 두 줄로 원복
        # self.expert_panel = ExpertPanel(network_client=network_client)
        # self.easy_panel = EasyPanel(network_client=network_client)
        self.expert_panel = ExpertPanel(network_client=None)  # 임시: _StubService로 GUI만 확인
        self.easy_panel = EasyPanel(network_client=None)  # 임시: _StubService로 GUI만 확인

        self.mode_change = QStackedWidget()
        self.mode_change.addWidget(self.expert_panel)  # EXPERT_MODE
        self.mode_change.addWidget(self.easy_panel)    # EASY_MODE

        root = QWidget()
        self.layout = QVBoxLayout(root)

        self.title_label = QLabel("국민의 소리")
        self.title_label.setStyleSheet("font-size:18px; font-weight:700;")
        self.expert_button = QPushButton("전문가모드")
        self.easy_button = QPushButton("쉬운모드")
        for button in (self.expert_button, self.easy_button):
            button.setCheckable(True)
        self.expert_button.setChecked(True)

        self.title_layout = QHBoxLayout()
        self.title_layout.addWidget(self.title_label)
        self.title_layout.addStretch(1)
        self.title_layout.addWidget(self.expert_button)
        self.title_layout.addWidget(self.easy_button)

        self.layout.addLayout(self.title_layout)
        self.layout.addWidget(self.mode_change)
        self.setCentralWidget(root)

        self.expert_button.clicked.connect(lambda: self.set_mode(EXPERT_MODE))
        self.easy_button.clicked.connect(lambda: self.set_mode(EASY_MODE))
        for panel in (self.expert_panel, self.easy_panel):
            panel.busy_changed.connect(self.set_toggle_locked)
            panel.status_message.connect(self.statusBar().showMessage)

        self.statusBar().showMessage("준비되었습니다.")

    def set_mode(self, mode: int) -> None:
        """모드 전환은 스택 인덱스 변경뿐. 패널을 다시 만들지 않는다."""
        self.expert_button.setChecked(mode == EXPERT_MODE)
        self.easy_button.setChecked(mode == EASY_MODE)
        self.mode_change.setCurrentIndex(mode)

    def set_toggle_locked(self, locked: bool) -> None:
        """요청 중에는 모드 토글을 잠근다 (§6 GUI 체크리스트)."""
        self.expert_button.setEnabled(not locked)
        self.easy_button.setEnabled(not locked)


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
