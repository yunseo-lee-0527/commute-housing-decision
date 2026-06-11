# 자취 vs 통학 의사결정 추천 시스템

산업공학과 학생의 `자취 vs 통학` 선택을 경제성공학과 의사결정 방법론으로 비교하는 Streamlit 프로토타입입니다. 현 거주지, 월 예산, 의사결정 성향을 입력하면 통학 대안과 자취 매물을 NPV, AEC, 시간손실비용, 안전도, 편의성 기준으로 비교합니다.

## 주요 기능

- 현 거주지 주소 검색 및 지도 위치 확인
- 통학 시간의 기회비용 반영
- 4년 기준 NPV, AEC 비교
- 월세, 금리, 시간가치 변화에 따른 What-if 분석
- 비용/시간/편의성/안전 가중치 기반 종합점수
- 관악구 CPTED/GIS 안전도 점수 자동 산정
- 크롤링 매물 CSV를 앱 호환 최종 CSV로 변환

## 실행

```bash
pip install -r requirements.txt
streamlit run app.py
```

Windows에서는 `run_app.bat`를 실행해도 됩니다.

## Kakao REST API 키

`.streamlit/secrets.toml` 파일을 만들고 아래처럼 입력합니다.

```toml
KAKAO_API_KEY = "본인_KAKAO_REST_API_KEY"
```

예시 파일은 `.streamlit/secrets.toml.example`에 있습니다.

## 매물 데이터 흐름

1. 매물 후보 CSV 생성 (서울대입구역·낙성대역·대학동 녹두거리)

```bash
python generate_rentals.py --per-area 30 --output snu_area_rentals_crawled.csv
```

네이버 부동산은 요청 제한(429), KB부동산은 비공개 한글 파라미터 API로 라이브 크롤이
막혀 있어, 실제 좌표 클러스터와 관악구 시세대를 모사한 합성 매물 데이터를 사용합니다.
(라이브 크롤이 가능한 환경에서는 `python crawl_naver_rentals.py`로 같은 스키마의 CSV를
만들 수 있습니다.)

2. 관악구 안전도 점수 부여

```bash
python score_rental_safety.py --input snu_area_rentals_crawled.csv --output snu_area_rentals_scored.csv
```

3. 앱 실행

`app.py`는 안전도 점수가 부여된 `snu_area_rentals_scored.csv`를 사용합니다. 이 파일이
없으면 위 1~2단계를 먼저 실행하라는 안내가 표시됩니다.

## 안전도 산정

안전도는 실제 범죄확률이 아니라 CPTED 선행연구와 관악구 공개 GIS 데이터를 결합한 상대평가 지표입니다.

```text
공공환경 안전도 =
0.30 * CCTV 접근성
+ 0.25 * 조명 접근성
+ 0.20 * 경찰/치안시설 접근성
+ 0.15 * 안심귀갓길 접근성
+ 0.10 * 비상/지원시설 접근성
```

매물 CSV에 공동현관, 건물 CCTV, 관리인, 층수, 대로변 등의 라벨이 있으면 건물안전 보정점수를 추가합니다.

자세한 방법론과 출처는 [data/safety_gwanak/README.md](data/safety_gwanak/README.md)를 참고하세요.

## 주요 파일

| file | role |
|---|---|
| `app.py` | Streamlit 앱 |
| `model.py` | 경제성공학 계산 로직 |
| `safety.py` | CPTED/GIS 안전도 산정 엔진 |
| `score_rental_safety.py` | 매물 CSV 안전도 부여 CLI |
| `generate_rentals.py` | 3개 권역 매물 후보 합성 생성기 (시세·좌표 모사) |
| `crawl_naver_rentals.py` | 매물 크롤링 스크립트 (라이브 크롤 가능 시) |
| `data/safety_gwanak/` | 관악구 안전도 산정용 공개데이터 |

## 테스트

```bash
python test_safety.py
python test_model.py
python test_v3.py
```

## 주의

- `.streamlit/secrets.toml`은 개인 API 키가 들어가므로 GitHub에 올리지 않습니다.
- `gtfs_seoul_cache.pkl`, 원본 GTFS txt, `__pycache__`는 공유 대상에서 제외합니다.
- 안전도 점수는 의사결정 보조 지표이며, 실제 안전을 보장하는 값은 아닙니다.
