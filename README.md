# 자취 vs 통학 경제성공학 의사결정 프로토타입

산업공학과 학생의 `자취 vs 통학` 선택을 경제성공학 관점에서 비교하는 Streamlit 프로토타입입니다.  
현 거주지, 월 예산, 개인 의사결정 성향을 입력하면 통학과 자취 매물 후보를 `NPV`, `AEC`, `시간손실비용`, `AHP 종합점수`로 비교합니다.

## 주요 기능

- 현 거주지 주소 검색 및 지도 위치 확인
- 자취 매물 CSV 기반 후보 비교
- 통학 시간의 기회비용 환산
  - `편도시간 × 2 × 월 등교일수 × 최저시급 ÷ 60`
- 4년 기준 NPV, AEC 비교
- 월 현금지출, 월 시간손실비용, 월 실질비용 산출
- 비용/시간/편의성/안전 가중치 입력
- 월세, 금리, 시간가치 변화에 대한 민감도 분석
- 자취 매물별 손익분기 월세 계산

## 폴더 구성

```text
.
├─ app.py
├─ rentals_dummy.csv
├─ requirements.txt
├─ run_app.bat
├─ build_gtfs_cache.py
├─ .gitignore
├─ .streamlit/
│  └─ secrets.toml.example
└─ 자취_vs_통학_경제성공학_프로젝트_제안서_실행화면포함.pptx
```

## 실행 방법

### 1. 패키지 설치

```bash
pip install -r requirements.txt
```

### 2. 카카오 REST API 키 설정

`.streamlit` 폴더에 `secrets.toml` 파일을 만들고 아래처럼 입력합니다.

```toml
KAKAO_API_KEY = "본인의_KAKAO_REST_API_KEY"
```

예시 파일은 `.streamlit/secrets.toml.example`에 있습니다.

### 3. 앱 실행

```bash
streamlit run app.py
```

또는 Windows에서는 `run_app.bat`를 실행해도 됩니다.

## 매물 CSV 형식

`rentals_dummy.csv`를 같은 컬럼 구조로 교체하면 실제 크롤링 매물 데이터로 분석할 수 있습니다.

| 컬럼명 | 설명 |
|---|---|
| `name` | 매물명 |
| `address` | 주소 |
| `lat` | 위도 |
| `lng` | 경도 |
| `deposit` | 보증금, 만원 |
| `monthly_rent` | 월세, 만원 |
| `maintenance_fee` | 관리비, 만원 |
| `monthly_transport` | 월 교통비, 만원 |
| `convenience` | 편의성 점수, 1-10 |
| `safety` | 안전 점수, 1-10 |

## 선택 기능: GTFS 대중교통 네트워크 캐시

대중교통 네트워크 기반 최단시간을 사용하려면 작년 해커톤 GTFS 데이터가 있는 환경에서 아래 명령을 한 번 실행합니다.

```bash
python build_gtfs_cache.py
```

생성되는 `gtfs_seoul_cache.pkl`은 용량이 커질 수 있으므로 GitHub에는 올리지 않습니다.

## 공유 시 주의사항

- `app.py`에는 API 키를 직접 넣지 않습니다.
- `.streamlit/secrets.toml`은 개인 키가 들어가므로 GitHub에 올리지 않습니다.
- `gtfs_seoul_cache.pkl`, 원본 GTFS txt 파일, `__pycache__`는 공유 대상에서 제외합니다.
