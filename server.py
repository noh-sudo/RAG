"""
server.py — [②] RAG 서버 진입점 (신규)

server.py를 실행하는 PC에만 data/ 를 둔다. config.py를 읽고, §3.5 인덱스 검증
(구 main.py의 몫이었던 것을 이관)을 수행한 뒤 TCP 소켓 리스닝을 시작한다.

- 스레드 기반 다대일 서버(팀 프로젝트 "푸드코트 주문 시스템"과 동일한 패턴)
  — 클라이언트 접속마다 스레드 1개
- 요청(RemoteQueryRequest) 수신 → RetrievalService.search()
  → (found=True면) GenerationService.generate() → RemoteQueryResponse 조립 → 회신
- ModeSwitchRequest도 같은 소켓으로 받아 ModeManager.switch_mode()에 위임

메시지 프레이밍은 common/network_client.py와 동일하게 맞췄다: 4바이트 빅엔디안
길이 헤더 + UTF-8 JSON body, {"type", "session_id", "payload"} 봉투이고 응답도
{"payload": {...}} 형태로 돌려준다 (network_client.py의 raw.get("payload", raw)
처리 덕분에 이 형태를 그대로 기대한다).
"""

import json
import socket
import struct
import sys
import threading
import time
from dataclasses import asdict

import chromadb

import config
from common.schemas import (
    GenerationRequest,
    Mode,
    ModeSwitchRequest,
    ModeSwitchResponse,
    RemoteQueryRequest,
    RemoteQueryResponse,
    SearchFilters,
    SearchRequest,
)
from services.generation import GenerationService
from services.mode_manager import ModeManager
from services.retrieval import RetrievalService

_HEADER_SIZE = 4


def verify_index() -> None:
    """§3.5 인덱스 검증. 실패 시 ERR_INDEX_MISMATCH로 즉시 종료한다."""
    if not config.META_PATH.exists():
        _fail_index(f"data/meta.json이 없습니다 ({config.META_PATH})")

    meta = json.loads(config.META_PATH.read_text(encoding="utf-8"))

    if meta.get("embed_model") != config.EMBED_MODEL or meta.get("dim") != config.EMBED_DIM:
        _fail_index(
            f"meta.json(embed_model={meta.get('embed_model')}, dim={meta.get('dim')})이 "
            f"config.py(EMBED_MODEL={config.EMBED_MODEL}, EMBED_DIM={config.EMBED_DIM})와 다릅니다"
        )

    client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
    try:
        collection = client.get_collection(config.CHROMA_COLLECTION_NAME)
    except Exception:
        _fail_index(f"ChromaDB 컬렉션 '{config.CHROMA_COLLECTION_NAME}'을 찾을 수 없습니다")
        return

    actual_count = collection.count()
    expected_count = meta.get("chunk_count")
    if expected_count is not None and actual_count != expected_count:
        _fail_index(f"청크 수 불일치: meta.json={expected_count}건, Chroma 실제={actual_count}건")

    print(f"[server.py] 인덱스 검증 통과 — {actual_count}건, embed_model={meta.get('embed_model')}")


def _fail_index(reason: str) -> None:
    print(f"[ERR_INDEX_MISMATCH] {reason}")
    sys.exit(1)


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    chunks = []
    remaining = n
    while remaining > 0:
        chunk = sock.recv(remaining)
        if not chunk:
            raise ConnectionError("클라이언트 연결이 끊겼습니다")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _receive_message(sock: socket.socket) -> dict:
    header = _recv_exact(sock, _HEADER_SIZE)
    (length,) = struct.unpack(">I", header)
    body = _recv_exact(sock, length)
    return json.loads(body.decode("utf-8"))


def _send_message(sock: socket.socket, message: dict) -> None:
    body = json.dumps(message, ensure_ascii=False).encode("utf-8")
    header = struct.pack(">I", len(body))
    sock.sendall(header + body)


def _coerce_mode(value: object) -> Mode:
    if isinstance(value, Mode):
        return value
    if isinstance(value, str):
        normalized = value.upper()
        if normalized in {Mode.EXPERT.value, Mode.EASY.value}:
            return Mode(normalized)
    raise ValueError(f"지원하지 않는 모드 값: {value}")


def _payload_to_remote_query_request(payload: dict) -> RemoteQueryRequest:
    filters = SearchFilters(**(payload.get("filters") or {}))
    return RemoteQueryRequest(
        session_id=payload["session_id"],
        query=payload["query"],
        filters=filters,
        mode=_coerce_mode(payload["mode"]),
        top_k=payload.get("top_k", config.TOP_K_DEFAULT),
    )


def _payload_to_mode_switch_request(payload: dict) -> ModeSwitchRequest:
    return ModeSwitchRequest(session_id=payload["session_id"], new_mode=_coerce_mode(payload["new_mode"]))


class ClientHandler(threading.Thread):
    """클라이언트 접속 1건당 스레드 1개. 지속 연결이므로 끊길 때까지 반복 수신한다."""

    def __init__(
        self,
        conn: socket.socket,
        addr,
        retrieval: RetrievalService,
        generation: GenerationService,
        mode_manager: ModeManager,
    ) -> None:
        super().__init__(daemon=True)
        self._conn = conn
        self._addr = addr
        self._retrieval = retrieval
        self._generation = generation
        self._mode_manager = mode_manager

    def run(self) -> None:
        try:
            while True:
                message = _receive_message(self._conn)
                self._handle_message(message)
        except (ConnectionError, OSError, json.JSONDecodeError, struct.error) as exc:
            print(f"[server.py] {self._addr} 연결 종료: {exc}")
        finally:
            self._conn.close()

    def _handle_message(self, message: dict) -> None:
        msg_type = message.get("type")
        payload = message.get("payload", {})

        if msg_type == "query":
            try:
                response = self._handle_query(payload)
            except Exception as exc:
                print(f"[server.py] {self._addr} query 처리 실패: {exc}")
                response = RemoteQueryResponse(
                    session_id=payload.get("session_id", ""),
                    found=False,
                    top_similarity=0.0,
                    chunks=[],
                    response=None,
                    error=f"ERR_INTERNAL: {exc}",
                    search_time_ms=0,
                )
            _send_message(self._conn, {"payload": asdict(response)})

        elif msg_type == "mode_switch":
            try:
                response = self._handle_mode_switch(payload)
            except Exception as exc:
                print(f"[server.py] {self._addr} mode_switch 처리 실패: {exc}")
                return
            _send_message(self._conn, {"payload": asdict(response)})

    def _handle_query(self, payload: dict) -> RemoteQueryResponse:
        request = _payload_to_remote_query_request(payload)
        start = time.perf_counter()

        search_result = self._retrieval.search(
            SearchRequest(
                session_id=request.session_id,
                query=request.query,
                filters=request.filters,
                top_k=request.top_k,
            )
        )

        found = search_result.found
        chunks = search_result.chunks
        summary_response = None

        if found:
            summary_response = self._generation.generate(
                GenerationRequest(
                    session_id=request.session_id,
                    query=request.query,
                    mode=request.mode,
                    retrieved_chunks=chunks,
                )
            )
            if summary_response is None:
                # 2차 방어선: 거부 문구 감지 → found=False로 강등
                found = False
                chunks = []

        self._mode_manager.remember_search(
            session_id=request.session_id,
            query=request.query,
            filters=request.filters,
            top_k=request.top_k,
            found=found,
            retrieved_chunks=chunks,
        )

        search_time_ms = int((time.perf_counter() - start) * 1000)
        return RemoteQueryResponse(
            session_id=request.session_id,
            found=found,
            top_similarity=search_result.top_similarity,
            chunks=chunks,
            response=summary_response,
            error=None,
            search_time_ms=search_time_ms,
        )

    def _handle_mode_switch(self, payload: dict) -> ModeSwitchResponse:
        request = _payload_to_mode_switch_request(payload)
        return self._mode_manager.switch_mode(request)


def main() -> None:
    verify_index()

    retrieval = RetrievalService()
    generation = GenerationService()
    mode_manager = ModeManager(retrieval, generation)

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(("0.0.0.0", config.SERVER_PORT))
    server_sock.listen()
    print(f"[server.py] 리스닝 시작 — 0.0.0.0:{config.SERVER_PORT}")

    try:
        while True:
            conn, addr = server_sock.accept()
            print(f"[server.py] 클라이언트 접속: {addr}")
            ClientHandler(conn, addr, retrieval, generation, mode_manager).start()
    except KeyboardInterrupt:
        print("[server.py] 종료합니다")
    finally:
        server_sock.close()


if __name__ == "__main__":
    main()
