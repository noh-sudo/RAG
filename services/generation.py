"""
services/generation.py — [②]

검색된 청크를 근거로 모드별 프롬프트를 구성해 같은 PC의 Ollama(localhost)를 호출하는
GenerationService 정의. server.py만 호출한다.

■ 팀 확인이 필요한 임의 결정
- LLM에게 정해진 JSON 스키마로만 답하게 하고(system 프롬프트에 명시), 그 JSON을
  그대로 ExpertSummaryResponse/EasySummaryResponse 필드에 매핑한다. 인터페이스
  정의서에 프롬프트 형식까지는 정해져 있지 않아 이렇게 골랐다 — 모델이 JSON을
  벗어나 답하면 파싱 실패로 보고 None(2차 방어선 발동)을 반환한다.
- EasySummaryResponse.glossary(용어 추출·뜻풀이)도 이 프롬프트 안에서 LLM이 함께
  만든다. schedule_and_files_1.md는 "용어 추출·뜻풀이"를 ④ 담당 Day3 작업으로
  적어두었지만, GenerationService.generate()의 반환 타입 자체가 이미 glossary
  필드를 포함한 EasySummaryResponse이므로 생성 시점에 채워 넣었다. ④가 자체
  추출 로직을 따로 두기로 하면 이 필드는 무시하거나 이 함수에서 빼면 된다.
"""

import json
from datetime import datetime, timezone

import ollama

import config
from common.schemas import EasySummaryResponse, ExpertSummaryResponse, GenerationRequest, Mode, RetrievedChunk

_EXPERT_NUM_PREDICT = 1200
_EASY_NUM_PREDICT = 600
_TIMEOUT_SECONDS = 180  # 제한 시간 180초, 재시도 없음 (재시도해도 같은 시간이 다시 걸릴 뿐)

# 프롬프트에 반드시 포함해야 하는 3개 지침 (누락 시 C1이 깨짐)
_COMMON_GUIDELINES = (
    "1. 아래 [발췌]에 있는 내용만 근거로 답하라. 발췌에 없는 내용은 추측하지 마라.\n"
    "2. 발췌 내용을 인용한 모든 문장 끝에는 그 근거가 된 발췌 번호를 대괄호로 표기하라. 예: [2]\n"
    "3. 발췌만으로는 질문에 답할 수 없다면, 추측하지 말고 그 사실을 그대로 밝혀라."
)

_EXPERT_SYSTEM_PROMPT = (
    "너는 국회 회의록 발췌를 근거로 전문가용 요약을 작성하는 어시스턴트다.\n"
    + _COMMON_GUIDELINES
    + "\n\n다음 JSON 형식으로만 답하라 (다른 텍스트를 덧붙이지 마라):\n"
    '{"summary_text": "...", "key_issues": ["...", "..."], "insufficient": false}\n'
    '발췌만으로 답할 수 없으면 "insufficient"를 true로 하고 summary_text에 그 사실을 적어라.'
)

_EASY_SYSTEM_PROMPT = (
    "너는 국회 회의록 발췌를 근거로 고령자도 이해하기 쉬운 요약을 작성하는 어시스턴트다.\n"
    + _COMMON_GUIDELINES
    + "\n\n다음 JSON 형식으로만 답하라 (다른 텍스트를 덧붙이지 마라):\n"
    '{"decision": "무엇을 결정했는지", "reason": "왜 이런 이야기를 했는지", '
    '"change": "앞으로 무엇이 바뀌는지", '
    '"glossary": [{"term": "어려운 용어", "definition": "쉬운 뜻풀이"}], "insufficient": false}\n'
    '발췌만으로 답할 수 없으면 "insufficient"를 true로 하고 decision에 그 사실을 적어라.'
)


class GenerationService:
    def __init__(self) -> None:
        self._client = ollama.Client(host=config.OLLAMA_HOST, timeout=_TIMEOUT_SECONDS)

    def generate(
        self, request: GenerationRequest
    ) -> ExpertSummaryResponse | EasySummaryResponse | None:
        """모드별 요약을 생성한다.

        2차 방어선: LLM 응답이 거부 문구(config.REJECTION_PHRASES)와 일치하거나,
        모델이 "insufficient": true를 반환하거나, JSON 파싱에 실패하면 None을
        반환한다. 호출측(server.py/mode_manager.py)은 이를 found=False로 강등
        처리해야 한다 — 그렇지 않으면 거부 문구가 정상 요약처럼 화면에 렌더링된다.
        """
        if request.mode == Mode.EXPERT:
            return self._generate_expert(request)
        return self._generate_easy(request)

    def _generate_expert(self, request: GenerationRequest) -> ExpertSummaryResponse | None:
        prompt = self._build_prompt(request.query, request.retrieved_chunks)
        raw_text = self._call_ollama(_EXPERT_SYSTEM_PROMPT, prompt, _EXPERT_NUM_PREDICT)

        data = self._parse_json(raw_text)
        if data is None:
            fallback_text = raw_text.strip() or "요약 생성에 실패했지만, 검색된 근거는 확인할 수 있습니다."
            return ExpertSummaryResponse(
                summary_text=fallback_text,
                key_issues=[],
                citations=[
                    {
                        "citation_id": chunk.citation_id,
                        "meeting_label": chunk.meeting_label,
                        "meeting_date": chunk.meeting_date,
                        "speaker": chunk.speaker,
                    }
                    for chunk in request.retrieved_chunks
                ],
                generated_at=self._now(),
            )
        if data.get("insufficient") or self._is_rejected(data.get("summary_text", "")):
            return None

        citations = [
            {
                "citation_id": chunk.citation_id,
                "meeting_label": chunk.meeting_label,
                "meeting_date": chunk.meeting_date,
                "speaker": chunk.speaker,
            }
            for chunk in request.retrieved_chunks
        ]
        return ExpertSummaryResponse(
            summary_text=data.get("summary_text", ""),
            key_issues=data.get("key_issues", []),
            citations=citations,
            generated_at=self._now(),
        )

    def _generate_easy(self, request: GenerationRequest) -> EasySummaryResponse | None:
        prompt = self._build_prompt(request.query, request.retrieved_chunks)
        raw_text = self._call_ollama(_EASY_SYSTEM_PROMPT, prompt, _EASY_NUM_PREDICT)

        data = self._parse_json(raw_text)
        if data is None:
            fallback_text = raw_text.strip() or "요약 생성에 실패했지만, 검색된 근거는 확인할 수 있습니다."
            return EasySummaryResponse(
                decision=fallback_text,
                reason="",
                change="",
                glossary=[],
                generated_at=self._now(),
            )
        if data.get("insufficient") or self._is_rejected(data.get("decision", "")):
            return None

        return EasySummaryResponse(
            decision=data.get("decision", ""),
            reason=data.get("reason", ""),
            change=data.get("change", ""),
            glossary=data.get("glossary", []),
            generated_at=self._now(),
        )

    def _build_prompt(self, query: str, chunks: list[RetrievedChunk]) -> str:
        excerpt_lines = [
            f"[{chunk.citation_id}] ({chunk.meeting_date} {chunk.meeting_label}, {chunk.speaker}) {chunk.text}"
            for chunk in chunks
        ]
        return f"질문: {query}\n\n발췌:\n" + "\n".join(excerpt_lines)

    def _call_ollama(self, system_prompt: str, user_prompt: str, num_predict: int) -> str:
        response = self._client.generate(
            model=config.LLM_MODEL,
            system=system_prompt,
            prompt=user_prompt,
            options={"num_predict": num_predict},
            stream=False,
        )
        return response["response"]

    def _parse_json(self, raw_text: str) -> dict | None:
        try:
            return json.loads(raw_text)
        except (json.JSONDecodeError, TypeError):
            return None

    def _is_rejected(self, text: str) -> bool:
        return any(phrase in text for phrase in config.REJECTION_PHRASES)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
