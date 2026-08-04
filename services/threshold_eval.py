"""
services/threshold_eval.py — [②]

THRESHOLD 값을 직관이 아니라 실측으로 정하기 위한 평가 스크립트 (Day 4 필수 작업).
RetrievalService.raw_query()로 게이트(THRESHOLD)를 거치지 않은 원시 dense 유사도를
직접 조회해, 인덱싱 범위 안/밖 질문의 유사도 분포가 갈라지는 지점을 찾는다.

입력: tests/questions.json (③ 담당, Day 3 산출물). 범위 안 질문 20개 + 범위 밖
질문 20개, 총 40개. 각 항목 형식(②③ 간 확인 필요, 인터페이스 정의서에 명시 없음):
    {"question": "...", "in_scope": true, "answer_chunk_id": "052147-0002"}
answer_chunk_id가 있는 항목만 Recall@5 집계에 포함한다 (§7.2).

실행: python -m services.threshold_eval
산출물이 정해지면 config.py의 THRESHOLD를 이 스크립트가 추천한 값으로 갱신한다.
"""

import json
import sys
from pathlib import Path

import config
from services.retrieval import RetrievalService

QUESTIONS_PATH = Path(__file__).parent.parent / "tests" / "questions.json"


def load_questions(path: Path = QUESTIONS_PATH) -> list[dict]:
    if not path.exists():
        print(f"{path}가 없습니다. ③ 담당의 Day 3 산출물(tests/questions.json)이 먼저 있어야 합니다.")
        sys.exit(1)
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate(questions: list[dict], top_k: int = 5) -> dict:
    retrieval = RetrievalService()

    in_scope_top1: list[float] = []
    out_scope_top1: list[float] = []
    recall_hits = 0
    recall_total = 0

    for q in questions:
        chunks = retrieval.raw_query(q["question"], top_k=top_k)
        top1 = chunks[0].dense_similarity if chunks else 0.0

        if q.get("in_scope"):
            in_scope_top1.append(top1)
            answer_chunk_id = q.get("answer_chunk_id")
            if answer_chunk_id:
                recall_total += 1
                if any(chunk.chunk_id == answer_chunk_id for chunk in chunks):
                    recall_hits += 1
        else:
            out_scope_top1.append(top1)

    return {
        "in_scope_top1": in_scope_top1,
        "out_scope_top1": out_scope_top1,
        "recall_hits": recall_hits,
        "recall_total": recall_total,
    }


def suggest_threshold(in_scope_top1: list[float], out_scope_top1: list[float]) -> tuple[float, int]:
    """in/out 분포를 후보 임계값으로 스캔해, 오판정(FN+FP)이 최소인 값을 고른다."""
    candidates = sorted(set(round(v, 4) for v in in_scope_top1 + out_scope_top1))
    if not candidates:
        return config.THRESHOLD, 0

    best_threshold = candidates[0]
    best_errors = None
    for candidate in candidates:
        false_negatives = sum(1 for v in in_scope_top1 if v < candidate)
        false_positives = sum(1 for v in out_scope_top1 if v >= candidate)
        errors = false_negatives + false_positives
        if best_errors is None or errors < best_errors:
            best_errors = errors
            best_threshold = candidate

    return best_threshold, best_errors


def main() -> None:
    questions = load_questions()
    result = evaluate(questions)

    print(f"범위 안 질문 {len(result['in_scope_top1'])}개, 범위 밖 질문 {len(result['out_scope_top1'])}개")
    print(f"범위 안 top-1 유사도: {sorted(result['in_scope_top1'])}")
    print(f"범위 밖 top-1 유사도: {sorted(result['out_scope_top1'])}")

    threshold, errors = suggest_threshold(result["in_scope_top1"], result["out_scope_top1"])
    print(f"\n추천 THRESHOLD = {threshold} (오판정 {errors}건)")
    print("이 값을 config.py의 THRESHOLD에 반영한다.")

    if result["recall_total"]:
        recall = result["recall_hits"] / result["recall_total"]
        print(f"\nRecall@5 = {result['recall_hits']}/{result['recall_total']} ({recall:.1%})")
    else:
        print("\nRecall@5: questions.json에 answer_chunk_id가 없어 측정하지 않았습니다.")


if __name__ == "__main__":
    main()
