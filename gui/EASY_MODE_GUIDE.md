# 쉬운모드 구현 가이드

**작성자**: 신입 프로그램 개발자  
**프로젝트**: 국민의 소리 - RAG 기반 국회 회의록 검색·요약 서비스  
**모드**: 쉬운모드 (대시보드 B, 고령자 친화)  
**작성일**: 2026-07-31

---

## 📋 개요

쉬운모드는 고령자와 일반 국민을 위한 간단하고 읽기 쉬운 요약 화면입니다.

### 핵심 특징
- **4개 카테고리 버튼**: 정치, 경제, 외교·안보, 교육·복지
- **3문답 요약**: 결정 / 이유 / 변화 형식
- **용어 풀이**: 어려운 용어의 쉬운 설명
- **고령자 친화 디자인**: 큰 글씨, 굵은 폰트, 강렬한 색상

---

## 🗂️ 파일 구조

```
gui/
├── easy_panel.py              # 쉬운모드 메인 패널
└── glossary_widget.py         # 용어 풀이 위젯
```

### 프로젝트 전체 구조에서의 위치

```
국민의_소리/
├── common/
│   └── schemas.py             # 공통 dataclass (SearchRequest, EasySummaryResponse 등)
├── services/
│   ├── retrieval.py           # 검색 엔진 (RetrievalService.search())
│   └── generation.py          # 생성 엔진 (GenerationService.generate())
├── gui/
│   ├── main_window.py         # 메인 윈도우 (모드 토글)
│   ├── expert_panel.py        # 전문가모드 패널 (③ 담당)
│   ├── easy_panel.py          # 쉬운모드 패널 (④ 담당)
│   └── glossary_widget.py     # 용어 풀이 위젯 (④ 담당)
└── main.py                    # 앱 진입점
```

---

## 🎨 UI 디자인 명세

### 색상 팔레트
- **배경**: 흰색 (`#FFFFFF`)
- **버튼**: 파란색 배경 (`#0052CC`) + 흰색 글씨
- **버튼 호버**: 짙은 파란색 (`#0040AA`)
- **제목**: 검은색 (`#333333`)
- **용어 풀이 카드**: 연한 파란색 배경 (`#F0F5FF`) + 파란색 테두리

### 글씨 크기 (pt 단위)
| 요소 | 크기 | 굵음 |
|------|------|------|
| 상단 타이틀 | 18pt | ✓ |
| 섹션 라벨 | 14pt | ✓ |
| 질문 제목 (3문답) | 13pt | ✓ |
| 카테고리 버튼 | 11pt | ✓ |
| 답변 본문 | 12pt | ✓ |
| 용어명 | 12pt | ✓ |
| 용어 정의 | 11pt | - |

### 레이아웃 간격
- 섹션 간: 20px
- 내부 요소 간: 10~15px
- 패딩: 15~20px

---

## 📦 import 규칙

```python
# common/schemas.py에서 임포트
from common.schemas import (
    SearchRequest, SearchFilters, Mode, 
    EasySummaryResponse, RetrievedChunk
)

# PySide6 임포트
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QScrollArea
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

# 쉬운모드 모듈 임포트
from gui.glossary_widget import GlossaryWidget
```

---

## 🔧 클래스 API

### EasyPanel (gui/easy_panel.py)

#### 클래스 변수
```python
CATEGORY_MAP = {
    "나라 살림": "cat_politics",
    "물가와 일자리": "cat_economy",
    "안보와 통일": "cat_diplomacy",
    "교육·복지": "cat_society"
}
```

#### 신호 (Signal)
```python
search_requested = pyqtSignal(SearchRequest)
# 카테고리 버튼 클릭 시 발생 → MainWindow가 수신

mode_switch_requested = pyqtSignal(dict)
# 추후 모드 전환 시 사용 (MainWindow 담당)
```

#### 주요 메서드

| 메서드 | 입력 | 역할 |
|-------|------|------|
| `init_ui()` | - | UI 초기화 |
| `display_summary(response)` | `EasySummaryResponse` | 요약 결과 화면에 표시 |
| `display_no_evidence()` | - | 검색 결과 없음 메시지 표시 |
| `display_loading()` | - | 로딩 상태 표시 |
| `reset()` | - | 초기 상태로 복원 |
| `enable_buttons(enabled)` | `bool` | 카테고리 버튼 활성화/비활성화 |

#### 사용 예시

```python
from gui.easy_panel import EasyPanel
from common.schemas import EasySummaryResponse

panel = EasyPanel()

# 요약 결과 표시
response = EasySummaryResponse(
    decision="국회에서는 ...",
    reason="이유는 ...",
    change="변화는 ...",
    glossary=[
        {"term": "용어1", "definition": "정의1"},
        {"term": "용어2", "definition": "정의2"}
    ]
)
panel.display_summary(response)

# 신호 연결
panel.search_requested.connect(handle_search)
```

---

### GlossaryWidget (gui/glossary_widget.py)

#### 신호
없음 (UI 표시 전용)

#### 주요 메서드

| 메서드 | 입력 | 역할 |
|-------|------|------|
| `init_ui()` | - | UI 초기화 |
| `display_glossary(items)` | `list[dict]` | 용어 목록 표시 및 캐시 |
| `get_cached_definition(term)` | `str` | 캐시에서 용어 정의 조회 |
| `clear()` | - | 용어 목록 초기화 |
| `get_cache_stats()` | - | 캐시 통계 반환 |

#### 캐시 기능

용어 풀이는 세션 중 자동으로 캐시되어 반복 조회 성능을 최적화합니다.

```python
glossary = GlossaryWidget()

# 용어 표시 (캐시에 자동 저장)
glossary.display_glossary([
    {"term": "저출생", "definition": "..."},
    {"term": "수당", "definition": "..."}
])

# 캐시 조회
definition = glossary.get_cached_definition("저출생")

# 캐시 통계
stats = glossary.get_cache_stats()
# {'cached_terms': 2, 'displayed_items': 2, 'cache': {...}}
```

#### GlossaryManager (선택사항)

애플리케이션 전역 용어 캐시 관리:

```python
from gui.glossary_widget import GlossaryManager

manager = GlossaryManager()

# 용어 저장
manager.cache_glossary("저출생", "태어나는 아이 수가 줄어드는 현상")

# 용어 조회
definition = manager.get_definition("저출생")

# 일괄 저장
manager.bulk_cache([...])

# 통계
info = manager.get_cache_info()
```

---

## 🔌 MainWindow와의 신호 연결

(메인 윈도우에서 구현)

```python
# main_window.py
from gui.easy_panel import EasyPanel
from services.retrieval import RetrievalService
from services.generation import GenerationService

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.easy_panel = EasyPanel()
        
        # 신호 연결
        self.easy_panel.search_requested.connect(self._handle_easy_search)
    
    def _handle_easy_search(self, request: SearchRequest):
        """쉬운모드 검색 요청 처리"""
        # 1. 검색 실행 (RetrievalService)
        search_result = self.retrieval_service.search(request)
        
        # 2. 근거 없음 판정
        if not search_result.found:
            self.easy_panel.display_no_evidence()
            return
        
        # 3. 요약 생성 (GenerationService)
        gen_request = GenerationRequest(
            session_id=request.session_id,
            query=request.query,
            mode=Mode.EASY,
            retrieved_chunks=search_result.chunks
        )
        response = self.generation_service.generate(gen_request)
        
        # 4. 화면에 표시
        self.easy_panel.display_summary(response)
```

---

## 🧪 테스트 및 실행

### 스탠드얼론 테스트 (demo)

`test_easy_panel.py` 파일을 PyCharm에서 직접 실행:

```bash
python test_easy_panel.py
```

또는 PyCharm에서:
1. 우측 마우스 → `Run`
2. F5 또는 `Shift+F10`

#### 테스트 화면
- 4개 카테고리 버튼 표시 확인
- 버튼 클릭 시 더미 요약 데이터 표시
- 용어 풀이 카드 렌더링 확인
- 고령자 친화 글씨 크기/굵기 확인

---

## 📝 코드 컨벤션

### 클린코드 원칙 (프로젝트 요구)

1. **함수명/변수명**: 영문 lowercase, snake_case
   ```python
   def display_summary(self, response):  # O
   def displaySummary(self, response):   # X
   ```

2. **상수**: UPPERCASE_SNAKE_CASE
   ```python
   CATEGORY_MAP = {...}  # O
   category_map = {...}  # X
   ```

3. **클래스명**: CamelCase
   ```python
   class EasyPanel(QWidget):  # O
   class easy_panel(QWidget):  # X
   ```

4. **import 순서**
   ```python
   # 1. 표준 라이브러리
   from dataclasses import dataclass
   from typing import Optional
   
   # 2. 서드파티 (PySide6)
   from PySide6.QtWidgets import QWidget
   from PySide6.QtCore import Signal
   
   # 3. 프로젝트 내부
   from common.schemas import SearchRequest
   from gui.glossary_widget import GlossaryWidget
   ```

5. **주석**: docstring + 인라인 주석
   ```python
   def display_summary(self, response: EasySummaryResponse):
       """요약 결과를 화면에 표시한다.
       
       Args:
           response: 생성 서비스에서 반환한 EasySummaryResponse
       """
       # 결정사항 텍스트 업데이트
       self.decision_text.setText(response.decision)
   ```

---

## 🐛 일반적인 버그 및 해결법

### 1. 카테고리 버튼 클릭 후 검색이 안 됨

**원인**: `search_requested` 신호가 MainWindow와 연결되지 않음

**해결**:
```python
# main_window.py에서
self.easy_panel.search_requested.connect(self._handle_easy_search)
```

### 2. 용어 풀이가 겹쳐서 보임

**원인**: 스크롤 영역의 높이 설정 부족

**해결**: `setMinimumHeight()` 확인
```python
self.glossary_widget.setMinimumHeight(400)  # 충분한 높이 설정
```

### 3. 글씨가 너무 작음 (고령자가 읽기 어려움)

**원인**: 폰트 크기가 설정값보다 작음

**해결**: 기본 시스템 폰트 크기 확인
```python
font = QFont()
font.setPointSize(12)  # 최소 12pt 이상 권장
```

### 4. 색상이 요구사항과 다름

**원인**: 스타일시트 우선순위 문제

**해결**: 구체적인 선택자 사용
```python
# 좋음
btn.setStyleSheet("""
    QPushButton {
        background-color: #0052CC;
        color: white;
    }
    QPushButton:hover {
        background-color: #0040AA;
    }
""")

# 피할 것
self.setStyleSheet("color: blue;")  # 하위 위젯에 영향
```

---

## 📚 참고 문서

| 문서 | 역할 |
|------|------|
| `schedule_and_files.md` | 일정별 담당업무, 산출파일 명시 |
| `파일구조_및_역할분담.md` | ④ 쉬운모드 담당 범위 정의 |
| `인터페이스_정의서_v1.6.md` | EasySummaryResponse 구조, 신호 정의 |
| `common/schemas.py` | 모든 dataclass 정의 |

---

## ✅ 체크리스트 (Day 3 마감)

- [ ] `easy_panel.py` 파일 작성 완료
- [ ] `glossary_widget.py` 파일 작성 완료
- [ ] 카테고리 버튼 4개 구현 및 테스트
- [ ] 3문답 요약 표시 기능 구현
- [ ] 용어 풀이 캐시 기능 구현
- [ ] 고령자 친화 디자인 확인 (글씨 크기, 굵기, 색상)
- [ ] MainWindow와 신호 연결 테스트
- [ ] `test_easy_panel.py`로 스탠드얼론 실행 확인
- [ ] 문서 작성 완료

---

## 📞 질문 및 이슈

문제 발생 시:
1. 오류 메시지 전체 복사
2. 발생 상황 설명
3. 실행 환경 (Python 버전, PySide6 버전 등)
4. 수정 시도 내용 공유

---

**작성**: 신입 프로그램 개발자  
**최종 수정**: 2026-07-31
