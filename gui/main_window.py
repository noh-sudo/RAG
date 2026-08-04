"""공통 셸.  [공통·동결 — Day 1 공동 작성. 변경은 4인 합의 후 1명이 대표 커밋]

제목 · 모드 토글 · QStackedWidget만 갖는다.
검색 상태와 데이터는 각 패널이 ②의 ModeManager를 호출해 직접 다룬다.
"""

from __future__ import annotations

import os
import sys
import uuid

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

from PySide6.QtCore import Signal, QThread, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from common.schemas import (
    ModeSwitchRequest, ModeSwitchResponse, Mode,
    ExpertSummaryResponse, EasySummaryResponse,
)
from gui.easy_panel import EasyPanel
from gui.expert_panel import ExpertPanel

LANDING_MODE = 0
EXPERT_MODE = 1
EASY_MODE = 2

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LANDING_IMAGE_PATH = os.path.join(BASE_DIR, "assembly_background.jpg")

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
QPushButton:hover { background-color: #1e40af; }
QPushButton:pressed { background-color: #163a91; }
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
QPushButton:hover { background-color: #d1d5db; }
"""

class LandingPage(QWidget):
    """첫 화면. 버튼을 누르면 시그널만 내보내고, 전환은 MainWindow가 판단한다."""

    expert_requested = Signal()
    easy_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap = QPixmap(LANDING_IMAGE_PATH)
        if self._pixmap.isNull():
            print(f"[경고] 배경 이미지를 불러오지 못했다: {LANDING_IMAGE_PATH}")

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

        expert_btn = QPushButton("전문가모드")
        expert_btn.setStyleSheet(MAIN_BUTTON_STYLE)
        expert_btn.setCursor(Qt.PointingHandCursor)
        expert_btn.clicked.connect(self.expert_requested.emit)

        easy_btn = QPushButton("쉬운모드")
        easy_btn.setStyleSheet(MAIN_BUTTON_STYLE)
        easy_btn.setCursor(Qt.PointingHandCursor)
        easy_btn.clicked.connect(self.easy_requested.emit)

        btn_row.addWidget(expert_btn)
        btn_row.addWidget(easy_btn)
        layout.addLayout(btn_row)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        if not self._pixmap.isNull():
            scaled = self._pixmap.scaled(
                self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            crop_x = max(0, (scaled.width() - self.width()) // 2)
            crop_y = max(0, (scaled.height() - self.height()) // 2)
            painter.drawPixmap(0, 0, scaled, crop_x, crop_y, self.width(), self.height())
        else:
            painter.fillRect(self.rect(), QColor(50, 60, 70))
        painter.fillRect(self.rect(), QColor(0, 0, 0, 90))
        painter.end()

class MainWindow(QMainWindow):
    def __init__(self, network_client=None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.network_client = network_client   # ← 추가
        self.setWindowTitle("국민의 소리")
        self.resize(1100, 850)
        self.session_id = str(uuid.uuid4())

        self.expert_panel = ExpertPanel(network_client=network_client, session_id=self.session_id)
        self.easy_panel = EasyPanel(network_client=network_client, session_id=self.session_id)

        self.landing_page = LandingPage()
        self.landing_page.expert_requested.connect(lambda: self.set_mode(EXPERT_MODE))
        self.landing_page.easy_requested.connect(lambda: self.set_mode(EASY_MODE))

        self.mode_change = QStackedWidget()
        self.mode_change.addWidget(self.landing_page)   # LANDING_MODE = 0
        self.mode_change.addWidget(self.expert_panel)   # EXPERT_MODE = 1
        self.mode_change.addWidget(self.easy_panel)     # EASY_MODE = 2
        self.mode_change.setCurrentIndex(LANDING_MODE)  # 처음엔 랜딩 화면

        root = QWidget()
        self.layout = QVBoxLayout(root)

        self.title_label = QLabel("국민의 소리")
        self.title_label.setStyleSheet("font-size:18px; font-weight:700;")
        self.expert_button = QPushButton("전문가모드")
        self.easy_button = QPushButton("쉬운모드")
        for button in (self.expert_button, self.easy_button):
            button.setCheckable(True)
        self.expert_button.setChecked(False)

        self.expert_button.setStyleSheet(MODE_BTN_INACTIVE)
        self.easy_button.setStyleSheet(MODE_BTN_INACTIVE)

        self.title_label.setVisible(False)
        self.expert_button.setVisible(False)
        self.easy_button.setVisible(False)

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
        is_landing = (mode == LANDING_MODE)
        self.title_label.setVisible(not is_landing)
        self.expert_button.setVisible(not is_landing)
        self.easy_button.setVisible(not is_landing)

        self.expert_button.setChecked(mode == EXPERT_MODE)
        self.easy_button.setChecked(mode == EASY_MODE)
        self.expert_button.setStyleSheet(
            MODE_BTN_ACTIVE if mode == EXPERT_MODE else MODE_BTN_INACTIVE)
        self.easy_button.setStyleSheet(
            MODE_BTN_ACTIVE if mode == EASY_MODE else MODE_BTN_INACTIVE)
        self.mode_change.setCurrentIndex(mode)

        if is_landing:
            return
        active_panel = self.expert_panel if mode == EXPERT_MODE else self.easy_panel
        active_panel.on_mode_activated()

    def _request_mode_switch(self, mode: int) -> None:
        new_mode = Mode.EXPERT if mode == EXPERT_MODE else Mode.EASY
        request = ModeSwitchRequest(session_id=self.session_id, new_mode=new_mode)

        self._mode_worker = ModeSwitchWorker(self.network_client, request)
        self._mode_worker.succeeded.connect(self._on_mode_switch_succeeded)
        self._mode_worker.failed.connect(
            lambda msg: self.statusBar().showMessage(f"모드 전환 오류: {msg}")
        )
        self._mode_worker.finished.connect(self._mode_worker.deleteLater)
        self._mode_worker.start()

    def _on_mode_switch_succeeded(self, response) -> None:
        if response.response is None:
            self.statusBar().showMessage("근거 없음 — 전환할 요약이 없습니다.")
            return
        if isinstance(response.response, ExpertSummaryResponse):
            self.expert_panel.apply_switched_response(response.response)
        else:
            self.easy_panel.apply_switched_response(response.response)
        self.statusBar().showMessage(
            "모드 전환 완료" + (" (캐시 재사용)" if response.cache_hit else "")
        )

    def set_toggle_locked(self, locked: bool) -> None:
        """요청 중에는 모드 토글을 잠근다 (§6 GUI 체크리스트)."""
        self.expert_button.setEnabled(not locked)
        self.easy_button.setEnabled(not locked)

    def closeEvent(self, event):
        """창을 닫을 때 실행 중인 검색 스레드를 안전하게 종료한다.
        Worker가 소켓 재시도 중(최대 33초)일 때 강제 종료하면 크래시가 나므로,
        quit()으로 스레드에 종료를 요청하고 최대 3초 대기한다."""
        for panel in (self.expert_panel, self.easy_panel):
            worker = getattr(panel, "_worker", None)
            if worker is not None and worker.isRunning():
                worker.quit()
                worker.wait(3000)
        event.accept()

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

def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
