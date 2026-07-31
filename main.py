"""
애플리케이션 진입점 — 국민의 소리 (클라이언트)

DB를 직접 열지 않는다. NetworkClient로 서버(server.py)에 TCP 접속해 검색·요약을 요청한다.
로그인 절차 없음 — 공개 정보 서비스이므로 실행하면 바로 검색 화면이 뜬다 (VOP-001).

NetworkClient에 대한 가정 (common/network_client.py, 공통, 아직 없음):
- NetworkClient(host: str, port: int)
- 연결 확인·요청 전송은 MainWindow가 QThread Worker에서 비동기로 수행하고
  Signal(connection_checked 등)로 결과를 받는다 (인터페이스 정의서 §4.4).
  main.py는 연결을 미리 확인하지 않는다 — GUI 스레드를 막지 않기 위해서다.
"""

import sys

from PySide6.QtWidgets import QApplication

import config
from common.network_client import NetworkClient
from gui.main_window import MainWindow


def main() -> None:
    client = NetworkClient(config.SERVER_HOST, config.SERVER_PORT)

    app = QApplication(sys.argv)
    window = MainWindow(network_client=client)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()