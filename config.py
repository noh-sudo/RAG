"""
설정 파일 — 국민의 소리

서버(server.py)와 클라이언트(main.py)가 이 파일 하나를 함께 쓴다.
코드 수정 없이 이 파일만 바꿔서 접속 정보를 변경할 수 있게 한다 (VOP-004).
"""

import os
import socket
from pathlib import Path


def _detect_default_host() -> str:
    """현재 머신의 실제 LAN IP를 자동으로 찾아 반환한다."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


# ── RAG 서버 접속 주소 (클라이언트가 사용) ──────────────────────
# 다른 PC에서 접속할 때는 클라이언트 쪽에서 RAG_SERVER_HOST 환경변수로 이 서버의 IP를 지정하면 된다.
SERVER_HOST = os.getenv("RAG_SERVER_HOST", "10.10.10.137")
SERVER_PORT = int(os.getenv("RAG_SERVER_PORT", "9000"))

# ── Ollama (서버 전용) ──────────────────────────────────────
# 서버 프로세스와 Ollama가 같은 PC에 있으므로 localhost로 접속한다.
OLLAMA_HOST = "http://localhost:11434"

# 생성 모델. 모델 교체는 이 한 줄만 수정한다 (GGUF 로딩 실패 시 대체 모델 전환용).
LLM_MODEL = "qwen2.5:14b"

# 임베딩 모델. 서버 기동 시 data/meta.json의 embed_model·dim과 대조한다 (인터페이스 정의서 §3.5).
EMBED_MODEL = "bge-m3"
EMBED_DIM = 1024

# ── 검색 (서버 전용) ────────────────────────────────────────
# 임계값 게이트 기준값. services/threshold_eval.py의 Day 4 실측 결과로 갱신한다.
THRESHOLD = 0.5

# 검색 결과 기본 반환 건수 (인터페이스 정의서 §3.6)
TOP_K_DEFAULT = 5

# 2차 방어선 판정용 거부 문구. LLM 응답이 이 문구 중 하나와 일치하면
# found=False로 강등한다 (§4.3). 화면에 표시하는 안내 문구와는 분리한다.
# services/generation.py 담당자가 실제 응답 패턴을 보고 채운다.
REJECTION_PHRASES = [
    "발췌만으로는 답할 수 없습니다",
]

# ── 데이터 경로 (서버 전용 — 클라이언트 PC에는 이 디렉터리가 없다) ──
DATA_DIR = Path(__file__).parent / "data"
CHUNKS_PATH = DATA_DIR / "chunks.json"
META_PATH = DATA_DIR / "meta.json"
CHROMA_DIR = DATA_DIR / "chroma"
CHROMA_COLLECTION_NAME = "minutes_chunks"