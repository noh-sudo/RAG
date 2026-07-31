"""
common/network_client.py — [공통]

클라이언트 GUI가 서버와 TCP로 통신하는 유일한 창구.
RetrievalService/GenerationService를 직접 호출하지 않고, 이 클래스를 거쳐서만
서버와 RemoteQueryRequest/RemoteQueryResponse, ModeSwitchRequest/ModeSwitchResponse를
주고받는다 (인터페이스 정의서 §4.4, §4.5).

■ 팀 확인 사항 (2026-07-31 대화 기준 확정된 설계 결정)
- 연결 모델: 지속 연결. connect()를 앱 시작 시 1회 호출하고, 이후 모든 요청은
  같은 소켓을 재사용한다. 끊기면 자동 재연결을 시도한다.
- Signal 책임: 이 클래스는 PySide6에 의존하지 않는 순수 로직이다. Signal emit은
  이 클래스를 호출하는 QThread Worker(또는 main_window.py)가 담당한다.
  (§3.2 규약 — 검색·생성은 QThread Worker에서 실행하고 Signal로 결과를 전달)
- session_id: 앱 시작 시 1회(uuid4) 생성해 이후 모든 요청에 재사용한다.
- 메시지 프레이밍: 4바이트 빅엔디안 길이 헤더 + UTF-8 JSON body.
  (참고: 예시로 참고한 이전 프로젝트의 protocol.py는 개행 구분자 방식이었으나,
   인터페이스 정의서 v2.0 §4.4 원문의 "메시지 앞에 길이를 붙여 경계 구분"이라는
   문구는 길이 헤더 방식을 가리키므로 이를 따랐다.)
- 소켓 타임아웃: 연결 시도는 10초, 연결 후 요청/응답은 200초
  (서버 생성 제한시간 180초 + 여유 20초).
- 재연결 정책: 고정 3회 재시도, 시도 사이 backoff_base * 시도횟수 초 대기.
  3회 모두 실패하면 ServerConnectionError(ERR_SERVER_CONN)를 던진다.

■ 팀 확인이 필요한 임의 결정 (인터페이스 정의서에 명시 없어 이 파일에서 정한 것)
- 서버가 query/switch_mode 요청을 구분할 wire-level 식별자가 정의서에 없어서,
  {"type": "query" | "mode_switch", "session_id": ..., "payload": {...}} 형태로
  감쌌다. 서버(②) 구현과 이 필드명이 일치하는지 반드시 맞춰봐야 한다.
- 서버 응답도 같은 형태({"payload": {...}})로 온다고 가정했다. 서버가 payload로
  감싸지 않고 최상위에 바로 필드를 담아 보낸다면 _to_remote_query_response /
  _to_mode_switch_response의 raw.get("payload", raw) 처리 덕분에 두 형태 다
  동작하지만, 실제 서버 구현을 보고 한 번은 확인이 필요하다.
- ExpertSummaryResponse와 EasySummaryResponse 중 무엇이 왔는지 판별할 필드가
  정의서에 없어서, "summary_text" 키 유무로 임시 구분했다. 서버가 별도의
  판별 필드(예: "mode")를 함께 보내주면 그걸로 바꾸는 게 더 안전하다.
"""

import json
import socket
import struct
import threading
import time
import uuid
from dataclasses import asdict
from typing import Optional, Union

from common.schemas import (
    RemoteQueryRequest,
    RemoteQueryResponse,
    ModeSwitchRequest,
    ModeSwitchResponse,
    RetrievedChunk,
    ExpertSummaryResponse,
    EasySummaryResponse,
)

SummaryResponse = Union[ExpertSummaryResponse, EasySummaryResponse]


class ServerConnectionError(Exception):
    """서버 연결 실패 또는 통신 끊김. GUI 쪽에서는 항상 ERR_SERVER_CONN으로 취급한다."""

    def __init__(self, message: str = "서버에 연결할 수 없습니다 (ERR_SERVER_CONN)"):
        super().__init__(message)


class NetworkClient:
    """서버와의 TCP 통신을 전담하는 클래스. PySide6에 의존하지 않는다."""

    HEADER_SIZE = 4  # 4바이트 빅엔디안 길이 헤더

    def __init__(
        self,
        host: str,
        port: int,
        connect_timeout: float = 10.0,
        request_timeout: float = 200.0,  # 서버 생성 제한시간 180초 + 여유 20초
        max_retries: int = 3,
        backoff_base: float = 1.0,       # 1차 1초, 2차 2초, 3차 3초 대기
    ):
        self.host = host
        self.port = port
        self.connect_timeout = connect_timeout
        self.request_timeout = request_timeout
        self.max_retries = max_retries
        self.backoff_base = backoff_base

        # 앱 시작 시 1회 생성, 이후 모든 요청에서 그대로 재사용한다
        self.session_id: str = str(uuid.uuid4())

        self._sock: Optional[socket.socket] = None
        # 지속 연결 소켓을 여러 스레드가 동시에 건드리지 않도록 보호.
        # (검색 중엔 GUI가 버튼을 비활성화하지만, 방어적으로 둔다)
        self._lock = threading.Lock()

    # ── 연결 관리 ──────────────────────────────────────────

    @property
    def is_connected(self) -> bool:
        return self._sock is not None

    def connect(self) -> bool:
        """최초 연결(또는 재연결)을 시도한다. 고정 max_retries회 재시도 + 짧은 백오프.

        예외를 던지지 않고 bool을 반환한다 — 앱 기동 시에는 연결 실패해도 앱을
        계속 띄우고 '연결 안 됨' 상태로 표시해야 하기 때문이다 (3.5의 0단계와 동일한 정책).
        """
        self._close_socket()

        for attempt in range(1, self.max_retries + 1):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(self.connect_timeout)
                sock.connect((self.host, self.port))
                sock.settimeout(self.request_timeout)  # 연결 후에는 요청 타임아웃으로 전환
                self._sock = sock
                return True
            except OSError:
                if attempt < self.max_retries:
                    time.sleep(self.backoff_base * attempt)

        self._sock = None
        return False

    def _close_socket(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    def close(self) -> None:
        """앱 종료 시 호출해 소켓을 정리한다."""
        with self._lock:
            self._close_socket()

    # ── 공개 API ──────────────────────────────────────────

    def query(self, request: RemoteQueryRequest) -> RemoteQueryResponse:
        """검색+생성 통합 요청 (§4.4).

        QThread Worker에서 호출한다 — 서버 왕복(검색+LLM 생성) 전체가 끝날 때까지
        블로킹되므로 메인 스레드에서 직접 호출하면 안 된다.
        """
        payload = self._request_to_payload(request)
        raw = self._send_and_receive("query", payload)
        return self._parse_remote_query_response(raw)

    def switch_mode(self, request: ModeSwitchRequest) -> ModeSwitchResponse:
        """모드 전환 요청 (§4.5)."""
        payload = self._request_to_payload(request)
        raw = self._send_and_receive("mode_switch", payload)
        return self._parse_mode_switch_response(raw)

    # ── 내부: 송수신 ──────────────────────────────────────

    def _send_and_receive(self, msg_type: str, payload: dict) -> dict:
        """연결이 끊겨 있으면 재연결 후 전송한다.

        전송/수신 도중 연결이 끊기면 재연결 후 같은 요청을 다시 보낸다.
        max_retries회를 모두 소진하면 ServerConnectionError를 던진다.
        """
        with self._lock:
            last_error: Optional[Exception] = None

            for attempt in range(1, self.max_retries + 1):
                if not self.is_connected:
                    if not self.connect():
                        last_error = ServerConnectionError("서버에 연결할 수 없습니다")
                        if attempt < self.max_retries:
                            continue
                        break

                try:
                    message = {
                        "type": msg_type,
                        "session_id": self.session_id,
                        "payload": payload,
                    }
                    self._send(message)
                    return self._receive()
                except (OSError, socket.timeout, ConnectionError) as exc:
                    last_error = exc
                    self._close_socket()
                    if attempt < self.max_retries:
                        time.sleep(self.backoff_base * attempt)
                        continue

            raise ServerConnectionError(
                f"서버 응답을 받지 못했습니다 (ERR_SERVER_CONN): {last_error}"
            )

    def _send(self, message: dict) -> None:
        body = json.dumps(message, ensure_ascii=False).encode("utf-8")
        header = struct.pack(">I", len(body))
        self._sock.sendall(header + body)

    def _receive(self) -> dict:
        header = self._recv_exact(self.HEADER_SIZE)
        (length,) = struct.unpack(">I", header)
        body = self._recv_exact(length)
        return json.loads(body.decode("utf-8"))

    def _recv_exact(self, n: int) -> bytes:
        """정확히 n바이트를 받을 때까지 반복 recv한다.
        중간에 연결이 끊기면(빈 바이트 수신) ConnectionError를 던진다."""
        chunks = []
        remaining = n
        while remaining > 0:
            chunk = self._sock.recv(remaining)
            if not chunk:
                raise ConnectionError("서버와의 연결이 끊겼습니다")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    # ── 내부: 직렬화/역직렬화 ────────────────────────────

    def _request_to_payload(self, request) -> dict:
        """dataclass를 dict로 변환. Enum 필드는 .value 문자열로 바꾼다."""
        data = asdict(request)
        for enum_field in ("mode", "new_mode"):
            if enum_field in data:
                value = getattr(request, enum_field)
                data[enum_field] = getattr(value, "value", value)
        return data

    def _parse_remote_query_response(self, raw: dict) -> RemoteQueryResponse:
        p = raw.get("payload", raw)
        chunks = [RetrievedChunk(**c) for c in p.get("chunks", [])]
        return RemoteQueryResponse(
            session_id=p["session_id"],
            found=p["found"],
            top_similarity=p["top_similarity"],
            chunks=chunks,
            response=self._parse_summary_response(p.get("response")),
            error=p.get("error"),
            search_time_ms=p["search_time_ms"],
        )

    def _parse_mode_switch_response(self, raw: dict) -> ModeSwitchResponse:
        p = raw.get("payload", raw)
        return ModeSwitchResponse(
            cache_hit=p["cache_hit"],
            response=self._parse_summary_response(p.get("response")),
        )

    def _parse_summary_response(self, data: Optional[dict]) -> Optional[SummaryResponse]:
        """전문가/쉬운모드 응답 중 어느 쪽인지 판별한다.

        임시 규칙: ExpertSummaryResponse에만 있는 "summary_text" 키 유무로 구분한다.
        서버가 판별용 필드를 별도로 보내주게 되면 그 필드로 바꾸는 게 더 안전하다.
        """
        if data is None:
            return None
        if "summary_text" in data:
            return ExpertSummaryResponse(**data)
        return EasySummaryResponse(**data)