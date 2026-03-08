# AIOps 기능 구현 계획서

> 이 문서만 보면 작업을 바로 시작할 수 있도록 모든 컨텍스트를 담는다.

---

## 프로젝트 구조 요약

```
skala-aiops-yolo-rag/
├── pest-detection-fasstapi/         ← FastAPI 백엔드
│   └── app/
│       ├── main.py                  ← 앱 진입점, lifespan에서 DB 초기화
│       ├── config.py                ← Settings 클래스 (upload_dir, model_path 등)
│       ├── schemas.py               ← Pydantic 모델
│       ├── routers/
│       │   └── analyze.py           ← POST /api/analyze (현재 유일한 라우터)
│       ├── services/
│       │   ├── classifier_service.py ← YOLO 추론 (conf=0.4 하드코딩)
│       │   ├── rag.py               ← RAG + pgvector + GPT-4o + STT/TTS 파이프라인
│       │   └── audio_processing.py  ← Whisper STT, ffmpeg 변환, OpenAI TTS
│       └── repositories/
│           └── detection_log.py     ← 현재: JSONL 파일에만 저장 (DB 미연동)
├── SKALA_DEMO_LIM/vue-app/          ← Nuxt3 + Vue3 프론트엔드
│   ├── pages/
│   │   ├── index.vue                ← 메인 카메라 화면
│   │   └── new-window.vue           ← 관리자 페이지 (검수 탭 + 파인튜닝 탭 UI 존재)
│   ├── components/
│   │   ├── ImageCard.vue            ← 검수 카드 컴포넌트 (카테고리 드롭다운 포함)
│   │   ├── SkeletonCard.vue         ← 로딩 스켈레톤
│   │   └── ThemeDropdown.vue        ← 다크/라이트 테마 전환
│   └── utils/tokens.js              ← 테마 토큰 (색상 시스템)
└── AIOPS_TASK.md                    ← 이 파일
```

---

## 병해충 클래스 정보 (무화과 한정)

> `dataset_info.md` 참고. 모델 출력 클래스명은 소분류코드에서 앞자리 0 제거한 숫자 문자열.

무화과(010) 관련 실제 발생 가능 병해충:

| 모델 클래스명 (pest_code) | 병해충명     |
| ------------------------- | ------------ |
| `1`                       | 갈색반점병   |
| `3`                       | 검은점무늬병 |
| `7`                       | 그을음병     |
| `11`                      | 잎마름병     |
| `12`                      | 잎말이나방   |
| `13`                      | 줄기썩음병   |
| `15`                      | 총채벌레     |
| `16`                      | 탄저병       |
| `17`                      | 흰가루병     |
| `20`                      | 점무늬병     |
| `999`                     | 정상         |

> 프론트 드롭다운의 "Class A~E" 하드코딩을 위 매핑으로 교체해야 함.
> 백엔드 `/api/manager/classes` API로 동적으로 받아오는 방식 권장.

---

## 현재 문제점 (작업 전 상태)

1. **저신뢰도 이미지 버려짐**: `conf=0.4` 미만 탐지 결과는 그냥 사라짐. DB 저장 없음.
2. **성공 탐지도 JSONL에만 저장**: `detection_log.py`가 PostgreSQL이 아닌 파일에 기록.
3. **관리자 API 없음**: 프론트가 호출하는 `/api/manager/images`, `/api/manager/update`가 백엔드에 구현 안 됨.
4. **보고서 탭 없음**: 프론트에 UI 없음.
5. **임계값 하드코딩**: `config.py`에 `CONFIDENCE_THRESHOLD=0.6`이 있지만 실제로 `classifier_service.py`에서 `conf=0.4`로 무시됨.
6. **카테고리 하드코딩**: `ImageCard.vue`의 `CATEGORIES = ["Class A"..."Class E"]` → 실제 병해충명으로 교체 필요.

---

## 구현 범위 (합의된 내용)

### 구현 O

- 저신뢰도(conf < threshold) 이미지 DB 저장 + 이미지 파일 보관
- 관리자 검수 큐 API (이미지 목록 조회, 라벨 업데이트)
- 파인튜닝 데이터셋 JSONL export API
- AI 운영 보고서 생성 (GPT-4o, 주간/월간)
- 임계값 동적 조회/변경 API + 프론트 설정 탭
- 프론트 보고서 탭 추가
- 실제 병해충 카테고리로 드롭다운 교체

### 구현 X (버튼만 존재, 실제 동작 없음)

- 파인튜닝 실행 (현재 `startFinetune()`의 가짜 progress bar 유지)
- 모델 배포

---

## 작업 목록 (순서대로 실행)

### [TASK 1] 백엔드 - DB 스키마 추가

**파일**: `pest-detection-fasstapi/app/services/rag.py`
**위치**: `initialize_db()` 메서드 내 기존 `CREATE TABLE` 블록 뒤에 추가

추가할 테이블 3개:

```sql
-- 1. 탐지 이벤트 (성공 + 저신뢰도 전부)
CREATE TABLE IF NOT EXISTS detection_events (
    id          SERIAL PRIMARY KEY,
    uuid        TEXT NOT NULL UNIQUE,
    image_path  TEXT,               -- 보관된 이미지 절대경로
    pest_code   TEXT,               -- YOLO 예측 클래스 (없으면 NULL)
    confidence  FLOAT,              -- YOLO 예측 신뢰도 (없으면 NULL)
    is_low_conf BOOLEAN DEFAULT FALSE,  -- conf < threshold 여부
    review_status TEXT DEFAULT 'pending',  -- 'pending' / 'approved' / 'relabeled'
    human_label TEXT,               -- 관리자가 수정한 병해충명
    created_at  TIMESTAMP DEFAULT NOW(),
    reviewed_at TIMESTAMP
);

-- 2. AI 운영 보고서
CREATE TABLE IF NOT EXISTS aiops_reports (
    id           SERIAL PRIMARY KEY,
    period_type  TEXT NOT NULL,     -- 'weekly' / 'monthly'
    period_start TIMESTAMP NOT NULL,
    period_end   TIMESTAMP NOT NULL,
    content      TEXT NOT NULL,     -- GPT-4o 생성 마크다운 보고서
    created_at   TIMESTAMP DEFAULT NOW()
);

-- 3. 모델 운영 설정 (키-값 저장소)
CREATE TABLE IF NOT EXISTS model_config (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- 기본 임계값 삽입 (없을 때만)
INSERT INTO model_config (key, value)
VALUES ('conf_threshold', '0.4')
ON CONFLICT (key) DO NOTHING;
```

---

### [TASK 2] 백엔드 - 이미지 저장 로직 변경

**파일**: `pest-detection-fasstapi/app/services/classifier_service.py`

변경 내용:

- `conf=0.4` 하드코딩 → `conf=0.0`으로 변경 (전체 탐지 후 직접 필터링)
- `predict()` 메서드가 저신뢰도 결과도 반환하도록 수정:

```python
# 변경 전
def predict(self, img_path: str) -> dict | None:
    results = self.model(img_path, conf=0.4, verbose=False)
    boxes = results[0].boxes
    if not boxes:
        return None
    best = max(boxes, key=lambda b: float(b.conf))
    pest_code = self.model.names[int(best.cls)]
    return {"pest_code": pest_code, "confidence": round(float(best.conf), 3)}

# 변경 후
def predict(self, img_path: str, threshold: float = 0.4) -> dict | None:
    results = self.model(img_path, conf=0.0, verbose=False)
    boxes = results[0].boxes
    if not boxes:
        return None
    best = max(boxes, key=lambda b: float(b.conf))
    pest_code = self.model.names[int(best.cls)]
    conf = round(float(best.conf), 3)
    return {
        "pest_code": pest_code,
        "confidence": conf,
        "is_low_conf": conf < threshold,  # 추가
    }
```

---

### [TASK 3] 백엔드 - analyze.py 라우터 수정

**파일**: `pest-detection-fasstapi/app/routers/analyze.py`

변경 내용:

- 탐지 결과를 DB(`detection_events`)에 저장 (JSONL 대체)
- 저신뢰도(`is_low_conf=True`)인 경우 이미지 파일 삭제하지 않고 `agent_storage/review/`에 보관
- 고신뢰도인 경우 기존대로 RAG 파이프라인 진행

현재 흐름:

```
이미지 있음 → predict() → None이면 에러 반환 → save_detection_log(JSONL)
```

변경 후 흐름:

```
이미지 있음
    → predict(threshold=DB에서 읽은 threshold)
    → None이면: detected=False 반환 (이미지 저장 안 함)
    → is_low_conf=True이면:
        이미지를 agent_storage/review/{uuid}.jpg 로 복사 보관
        detection_events에 review_status='pending' 으로 INSERT
        {"detected": False, "message": "저화질 이미지입니다. 관리자 검수 후 반영됩니다."} 반환
    → is_low_conf=False이면:
        detection_events에 review_status='approved' 로 INSERT
        기존 RAG 파이프라인 진행
```

> `config.py`의 `Settings`에 `review_dir: Path` 추가 필요 (`agent_storage/review/`)

임계값은 매 요청마다 DB에서 읽지 말고, 앱 시작 시 `app.state.conf_threshold`에 로드. 변경 API 호출 시 갱신.

---

### [TASK 4] 백엔드 - 관리자 라우터 신규 생성

**파일 신규 생성**: `pest-detection-fasstapi/app/routers/manager.py`

```
GET  /api/manager/images
     → detection_events WHERE review_status='pending' ORDER BY created_at DESC
     → Response: { images: [{ uuid, imageUrl, confidenceScore, pest_code, created_at }] }
     imageUrl은 /api/manager/image/{uuid} 경로로 제공

GET  /api/manager/image/{uuid}
     → agent_storage/review/{uuid}.jpg 파일 반환 (FileResponse)

POST /api/manager/update
     → Body: { updates: [{ uuid, category }] }
     → detection_events SET human_label=category, review_status='relabeled', reviewed_at=NOW()
     → Response: { updatedCount }

GET  /api/manager/export
     → review_status IN ('relabeled') 인 레코드를 JSONL로 export
     → 파인튜닝용 포맷: { "image_path": ..., "label": human_label, "confidence": ..., "created_at": ... }
     → FileResponse (content-type: application/jsonl)

GET  /api/manager/classes
     → 현재 서비스 중인 병해충 클래스 목록 반환
     → app.state.classifier.class_names (YOLO 모델에서 읽음)
     → PEST_NAME_MAP 딕셔너리로 한글명 매핑해서 반환
     → Response: { classes: [{ code: "20", name: "점무늬병" }, ...] }

GET  /api/manager/report?type=weekly|monthly
     → aiops_reports에서 가장 최근 해당 기간 보고서 조회
     → 없으면 generate_report() 호출해서 생성 후 반환
     → Response: { content, period_start, period_end, created_at }

POST /api/manager/report/generate
     → 강제로 새 보고서 생성 (관리자가 버튼 클릭)
     → type: 'weekly' | 'monthly' body로 받음

GET  /api/manager/config
     → model_config 테이블에서 conf_threshold 조회
     → Response: { conf_threshold: 0.4 }

POST /api/manager/config
     → Body: { conf_threshold: 0.55 }
     → model_config UPDATE
     → app.state.conf_threshold 갱신
     → Response: { updated: true }
```

> `main.py`에서 `app.include_router(manager.router)` 추가 필요

---

### [TASK 5] 백엔드 - 보고서 생성 서비스 신규 생성

**파일 신규 생성**: `pest-detection-fasstapi/app/services/report_service.py`

GPT-4o에게 넘길 통계 데이터:

```
- 기간 내 전체 탐지 건수
- 병해충별 탐지 건수 (pest_code 기준)
- 저신뢰도 비율 (is_low_conf=True 비율)
- 관리자 검수 완료 건수 / 재라벨링 건수
- 재라벨링 시 원래 pest_code → human_label 변경 패턴 (모델이 자주 틀리는 케이스)
- 현재 conf_threshold 값
```

GPT-4o 프롬프트 방향:

- 시스템: "당신은 스마트팜 AI 운영 관리자입니다. 아래 통계를 바탕으로 농장주가 이해하기 쉬운 운영 보고서를 한국어 마크다운으로 작성하세요."
- 포함 항목: 요약, 병해충 발생 현황, 모델 성능 분석, 권장 조치사항 (임계값 조정 제안 포함)

---

### [TASK 6] 백엔드 - 병해충 한글명 매핑 딕셔너리

**파일**: `pest-detection-fasstapi/app/routers/manager.py` 내부 또는 별도 `app/constants.py`

```python
PEST_NAME_MAP = {
    "1":   "갈색반점병",
    "3":   "검은점무늬병",
    "5":   "과실반점병",
    "6":   "과실썩음병",
    "7":   "그을음병",
    "8":   "노린재",
    "10":  "반엽병",
    "11":  "잎마름병",
    "12":  "잎말이나방",
    "13":  "줄기썩음병",
    "15":  "총채벌레",
    "16":  "탄저병",
    "17":  "흰가루병",
    "20":  "점무늬병",
    "21":  "바구미",
    "999": "정상",
}
```

> `classifier_service.py`의 `pest_code`는 이 딕셔너리의 key와 동일한 문자열임.
> `dataset_info.md` 참고: 모델 클래스명 = 소분류코드 앞자리 0 제거한 숫자 문자열

---

### [TASK 7] 프론트 - ImageCard.vue 카테고리 교체

**파일**: `SKALA_DEMO_LIM/vue-app/components/ImageCard.vue`

변경 내용:

- `const CATEGORIES = ["Class A", ...]` 하드코딩 제거
- `categories` prop 추가 (부모인 `new-window.vue`에서 `/api/manager/classes` 결과 내려받음)
- 드롭다운에 `{ code, name }` 형태로 표시: "점무늬병 (20)" 형식 또는 "점무늬병"만

```vue
// 변경 전 const CATEGORIES = ["Class A", "Class B", "Class C", "Class D",
"Class E"]; // 변경 후 const props = defineProps({ record: Object, selected:
String, isDirty: Boolean, t: Object, categories: Array, // [{ code: "20", name:
"점무늬병" }, ...] ← 추가 });
```

---

### [TASK 8] 프론트 - new-window.vue 수정

**파일**: `SKALA_DEMO_LIM/vue-app/pages/new-window.vue`

변경 내용:

#### 8-1. 탭바에 "보고서", "설정" 탭 추가

현재:

```js
[
  { id: "inspect", label: "검수" },
  { id: "finetune", label: "파인튜닝" },
];
```

변경 후:

```js
[
  { id: "inspect", label: "검수" },
  { id: "finetune", label: "파인튜닝" },
  { id: "report", label: "보고서" },
  { id: "settings", label: "설정" },
];
```

#### 8-2. 앱 마운트 시 클래스 목록 fetch

```js
const pestClasses = ref([]); // [{ code, name }]

onMounted(async () => {
  // ... 기존 테마 감지 코드 ...

  // 클래스 목록 로드
  try {
    const res = await fetch(`${backendUrl}/api/manager/classes`);
    const data = await res.json();
    pestClasses.value = data.classes ?? [];
  } catch {
    // testing 모드면 하드코딩 fallback
    pestClasses.value = [
      { code: "1", name: "갈색반점병" },
      { code: "3", name: "검은점무늬병" },
      { code: "7", name: "그을음병" },
      { code: "11", name: "잎마름병" },
      { code: "12", name: "잎말이나방" },
      { code: "13", name: "줄기썩음병" },
      { code: "15", name: "총채벌레" },
      { code: "16", name: "탄저병" },
      { code: "17", name: "흰가루병" },
      { code: "20", name: "점무늬병" },
      { code: "999", name: "정상" },
    ];
  }
});
```

#### 8-3. ImageCard에 categories prop 전달

```vue
<ImageCard
  v-for="rec in images"
  :key="rec.uuid"
  :record="rec"
  :selected="selections[rec.uuid] ?? ''"
  :is-dirty="rec.uuid in selections"
  :t="t"
  :categories="pestClasses"
  ←
  추가
  @change="handleSelection"
/>
```

#### 8-4. 보고서 탭 (report) UI 추가

```
상태:
- reportType: ref('weekly')    // 'weekly' | 'monthly'
- reportContent: ref('')       // 마크다운 문자열
- reportMeta: ref(null)        // { period_start, period_end, created_at }
- isLoadingReport: ref(false)
- isGeneratingReport: ref(false)

UI 구성:
- 상단: "주간" / "월간" 세그먼트 버튼
- 보고서 카드: 마크다운 렌더링 (v-html or 라이브러리)
  - 없으면: "아직 보고서가 없습니다. 생성 버튼을 눌러주세요." 안내
- 하단 floating 버튼: "보고서 생성" → POST /api/manager/report/generate
  - 생성 중 로딩 스피너
  - 완료 후 내용 갱신
```

#### 8-5. 설정 탭 (settings) UI 추가

```
상태:
- currentThreshold: ref(0.4)
- editingThreshold: ref(0.4)
- isSavingThreshold: ref(false)

UI 구성:
- 현재 임계값 표시 카드
- 슬라이더 (0.1 ~ 0.9, step 0.05) 또는 숫자 입력
- "적용" 버튼 → POST /api/manager/config { conf_threshold }
  - 성공 시 toast 표시
- 설명 텍스트: "임계값 이하의 탐지 결과는 관리자 검수 대기열로 이동됩니다."
```

---

### [TASK 9] 백엔드 - main.py 수정

**파일**: `pest-detection-fasstapi/app/main.py`

변경 내용:

```python
from app.routers import analyze, manager  # manager 추가

# lifespan에서 DB에서 threshold 로드
async with lifespan(app):
    ...
    # DB에서 conf_threshold 읽어서 app.state에 저장
    threshold = await get_conf_threshold(session)  # model_config 테이블
    app.state.conf_threshold = threshold

app.include_router(analyze.router)
app.include_router(manager.router)  # 추가
```

---

### [TASK 10] 백엔드 - config.py 수정

**파일**: `pest-detection-fasstapi/app/config.py`

변경 내용:

```python
class Settings:
    upload_dir: Path = Path(os.getenv("UPLOAD_DIR", "./agent_storage"))
    review_dir: Path = Path(os.getenv("REVIEW_DIR", "./agent_storage/review"))  # 추가
    model_path: str = ...
    # confidence_threshold 제거 (DB에서 동적으로 관리)

settings = Settings()
settings.upload_dir.mkdir(exist_ok=True)
settings.review_dir.mkdir(exist_ok=True)  # 추가
```

---

## 파일 변경 요약표

| 파일                                 | 작업                                                    | TASK |
| ------------------------------------ | ------------------------------------------------------- | ---- |
| `app/services/rag.py`                | `initialize_db()`에 테이블 3개 추가                     | 1    |
| `app/services/classifier_service.py` | `conf=0.0`, threshold 파라미터 추가, `is_low_conf` 반환 | 2    |
| `app/routers/analyze.py`             | DB 저장 로직, 저신뢰도 분기, 이미지 보관                | 3    |
| `app/routers/manager.py`             | **신규 생성** - 관리자 API 8개                          | 4    |
| `app/services/report_service.py`     | **신규 생성** - GPT 보고서 생성                         | 5    |
| `app/constants.py`                   | **신규 생성** - PEST_NAME_MAP                           | 6    |
| `app/main.py`                        | manager 라우터 등록, threshold 앱 상태 로드             | 9    |
| `app/config.py`                      | `review_dir` 추가, `confidence_threshold` 제거          | 10   |
| `vue-app/components/ImageCard.vue`   | `categories` prop 추가, 드롭다운 교체                   | 7    |
| `vue-app/pages/new-window.vue`       | 탭 추가, 클래스 fetch, 보고서/설정 탭 UI                | 8    |

---

## 주의사항

- **파인튜닝 실행 버튼**: 현재 `startFinetune()`의 가짜 progress bar 그대로 유지. 실제 학습 구현 X.
- **모델 배포 버튼**: 기존 toast만 띄우는 동작 유지. 실제 배포 구현 X.
- **이미지 URL**: 프론트에서 `/api/manager/image/{uuid}` 경로로 이미지를 직접 서빙. CORS 주의.
- **보고서 마크다운 렌더링**: `v-html` 사용 시 XSS 위험. GPT 출력만 넣으므로 허용 가능하나, marked.js 같은 라이브러리 사용 권장.
- **DB 연결**: `rag.py`의 `SessionLocal`을 manager 라우터에서 재사용. 별도 DB 연결 생성 X.
- **테스트 모드**: 프론트의 `testing.value`가 true일 때는 기존 FAKE_IMAGES 유지. 실제 API 호출은 `testing=false`일 때만.
