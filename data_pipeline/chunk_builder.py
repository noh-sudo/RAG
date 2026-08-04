"""
data_pipeline/chunk_builder.py — [①]

AI Hub 국회 회의록 원본 JSON(본회의 한정)을 읽어 ChunkData로 변환하고
chunks.json으로 직렬화한다. embed_text는 인터페이스 정의서 §4.1에 따라
저장하지 않는다 — chunks.json에는 document만 남긴다.
"""

import json
import re
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Iterator

from common.schemas import ChunkData

EXPECTED_COMMITTEE_NAME = "국회본회의"

CAT_KEYWORDS = {
    "cat_politics": ["정치"],
    "cat_economy": ["경제"],
    "cat_diplomacy": ["외교", "통일", "안보"],
    "cat_society": ["교육", "사회", "문화"],
}


def normalize_agenda(raw: str) -> str:
    """번호 접두사 제거 + 가운뎃점(U+2024 ․ → U+00B7 ·) 통일."""
    s = re.sub(r"^\d+\.\s*", "", raw.strip())
    return s.replace("․", "·")


def classify_categories(agenda_norm: str) -> dict:
    """병합형 안건(예: '외교·통일·안보')은 여러 카테고리가 동시에 True가 될 수 있다."""
    return {
        cat: any(keyword in agenda_norm for keyword in keywords)
        for cat, keywords in CAT_KEYWORDS.items()
    }


def extract_number(text: str) -> int:
    """'제400회', '제5차'처럼 숫자가 섞인 문자열에서 정수만 추출한다."""
    match = re.search(r"\d+", text)
    if not match:
        raise ValueError(f"숫자를 찾을 수 없습니다: {text!r}")
    return int(match.group())


def parse_meeting_date(date_str: str) -> tuple[str, int]:
    """'2022년9월21일(수)' → ('2022-09-21', epoch초). 시각 정보가 없어 자정 기준,
    시스템 로컬 타임존으로 계산한다 (팀에서 KST 고정이 필요하면 여기를 수정)."""
    match = re.match(r"(\d{4})년(\d{1,2})월(\d{1,2})일", date_str.strip())
    if not match:
        raise ValueError(f"날짜 형식을 해석할 수 없습니다: {date_str!r}")
    year, month, day = (int(g) for g in match.groups())
    dt = datetime(year, month, day)
    return dt.strftime("%Y-%m-%d"), int(dt.timestamp())


def _build_text_block(agenda_norm, questioner, questioner_position, question_comment,
                       answerer, answerer_position, answer_comment) -> str:
    """document와 embed_text 둘 다 이 재료로 구성한다 (인터페이스 정의서 §4.1)."""
    return (
        f"[안건] {agenda_norm}\n"
        f"[질문] {questioner} {questioner_position}: {question_comment}\n"
        f"[답변] {answerer} {answerer_position}: {answer_comment}"
    )


def build_chunk(raw: dict) -> ChunkData:
    committee_name = raw.get("committee_name", "").strip()
    if committee_name != EXPECTED_COMMITTEE_NAME:
        raise ValueError(
            f"committee_name이 '{EXPECTED_COMMITTEE_NAME}'이 아님: {committee_name!r} "
            "(본회의 범위 밖 데이터로 판단해 건너뜀)"
        )

    agenda_raw = raw["agenda"]
    agenda_norm = normalize_agenda(agenda_raw)
    categories = classify_categories(agenda_norm)

    questioner = raw.get("questioner_name", "").strip()
    questioner_position = raw.get("questioner_position", "").strip()
    answerer = raw.get("answerer_name", "").strip()
    answerer_position = raw.get("answerer_position", "").strip()
    answerer_affiliation = raw.get("answerer_affiliation", "").strip() or "미상"

    question_comment = raw["question"]["comment"]
    answer_comment = raw["answer"]["comment"]

    meeting_date, meeting_date_ts = parse_meeting_date(raw["date"])
    chunk_id = f"{raw['conference_number']}-{raw['question_number']}"

    text_block = _build_text_block(
        agenda_norm, questioner, questioner_position, question_comment,
        answerer, answerer_position, answer_comment,
    )

    return ChunkData(
        chunk_id=chunk_id,
        document=text_block,
        embed_text=text_block,
        question_text=question_comment,
        answer_text=answer_comment,
        questioner=questioner,
        questioner_position=questioner_position,
        answerer=answerer,
        answerer_position=answerer_position,
        answerer_affiliation=answerer_affiliation,
        agenda_raw=agenda_raw,
        agenda_norm=agenda_norm,
        cat_politics=categories["cat_politics"],
        cat_economy=categories["cat_economy"],
        cat_diplomacy=categories["cat_diplomacy"],
        cat_society=categories["cat_society"],
        generation_no=int(raw["generation_number"]),
        meeting_no=extract_number(raw["meeting_number"]),
        session_no=extract_number(raw["session_number"]),
        meeting_date=meeting_date,
        meeting_date_ts=meeting_date_ts,
        source_url=raw.get("original", ""),
    )


def _chunk_to_json_dict(chunk: ChunkData) -> dict:
    """chunks.json에 저장할 형태. embed_text는 저장하지 않는다."""
    data = asdict(chunk)
    data.pop("embed_text", None)
    return data


def iter_source_files(source_dir: Path) -> Iterator[Path]:
    yield from sorted(source_dir.glob("*.json"))


def build_chunks(source_dir: str, output_path: str) -> None:
    """source_dir의 모든 JSON을 chunks.json으로 변환한다.
    일부 JSON이 손상되었거나 필드가 없으면 해당 파일만 건너뛰고 계속 처리한다 (VOP-010)."""
    src = Path(source_dir)
    chunks: list[ChunkData] = []
    skipped: list[tuple[str, str]] = []

    for path in iter_source_files(src):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            chunks.append(build_chunk(raw))
        except Exception as exc:  # noqa: BLE001
            skipped.append((path.name, str(exc)))
            continue

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps([_chunk_to_json_dict(c) for c in chunks], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"[chunk_builder] {len(chunks)}건 변환 완료 → {output_path}")
    if skipped:
        print(f"[chunk_builder] {len(skipped)}건 건너뜀:")
        for name, reason in skipped:
            print(f"  - {name}: {reason}")


if __name__ == "__main__":
    build_chunks(source_dir="data/raw", output_path="data/chunks.json")
