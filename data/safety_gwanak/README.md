# 관악구 CPTED 안전도 데이터와 점수화 방법론

이 폴더는 관악구 자취방 후보의 **주거환경 안전도**를 계산하기 위한 공개데이터 묶음입니다. 점수는 실제 범죄확률 예측값이 아니라, CPTED 선행연구와 GIS 기반 안전 인프라 접근성을 결합한 **후보 매물 간 상대평가 지표**입니다.

## 데이터 구성

| file | rows | use |
|---|---:|---|
| `processed/gwanak_safe_facilities.csv` | 686 | 안심귀갓길 내 안심벨, CCTV, 보안등, 112 위치신고 안내 등 |
| `processed/gwanak_safe_route_links.csv` | 19 | 관악구 안심귀갓길 노선 |
| `processed/gwanak_safe_services.csv` | 27 | 안심택배함, 지킴이집 등 서비스 시설 |
| `processed/gwanak_streetlights.csv` | 95 | 서울시 가로등 위치정보 중 관악구 경계 내부 포인트 |
| `processed/gwanak_smartpoles.csv` | 7 | 스마트폴 위치와 보안등, CCTV, LED 비상벨 설치 여부 |
| `processed/gwanak_police_facilities.csv` | 10 | 경찰서, 지구대, 파출소 |
| `processed/gwanak_boundary_osm.geojson` | 1 | 좌표만 있는 데이터 필터링에 사용한 관악구 경계 |
| `processed/inventory.csv` | 7 | 처리 결과 목록과 행 수 |

같은 이름의 `.geojson` 파일은 지도 시각화용입니다.

## 안전도 산식

집의 위도/경도만 있을 때는 `공공환경 안전도`를 계산합니다.

```text
공공환경 안전도 =
0.30 * CCTV 접근성
+ 0.25 * 조명 접근성
+ 0.20 * 경찰/치안시설 접근성
+ 0.15 * 안심귀갓길 접근성
+ 0.10 * 비상/지원시설 접근성
```

매물 CSV에 공동현관, 건물 CCTV, 관리인, 층수, 대로변, 가로등 같은 라벨이 있으면 `건물안전 보정점수`를 추가합니다.

```text
최종 안전도 =
0.65 * 공공환경 안전도
+ 0.35 * 건물안전 보정점수
```

건물안전 보정점수는 다음 비중으로 계산합니다.

```text
건물안전 보정점수 =
0.45 * 공동현관/출입통제
+ 0.20 * 건물 CCTV 또는 관리인
+ 0.20 * 1층/지하 회피
+ 0.15 * 대로변 또는 조명 접근성
```

건물 라벨이 없으면 점수를 억지로 낮추지 않고, 좌표 기반 공공환경 안전도만 사용합니다.

## 거리 반영 방식

각 시설은 단순 개수보다 **가장 가까운 시설까지의 거리**를 중심으로 점수화합니다. 핵심반경 안에 있으면 1점, cutoff 밖이면 0점, 그 사이는 선형 감소합니다.

| component | core radius | cutoff | 근거 |
|---|---:|---:|---|
| CCTV | 100m | 300m | 방범용 CCTV 감시범위 100m |
| 조명 | 10m | 50m | 가로등 10m, 보안등 5m 영향권을 보수적으로 통합 |
| 경찰/치안시설 | 50m | 1000m | 치안센터 감시기능 50m, 500m, 1km 단계 |
| 안심귀갓길 | 30m | 150m | 노선 인접성 대리 지표 |
| 비상/지원시설 | 50m | 150m | 안심벨, 112 위치신고, 지킴이집, LED 비상벨 접근성 |

## 계수 정당화

- 박동현·강인준·최현·김상석(2015), 「GIS와 범죄예방환경설계 기반의 범죄취약지도 작성」은 CCTV, 치안센터, 가로등 등 감시요소를 GIS로 구축하고 AHP를 적용했습니다. 해당 연구의 가중치는 CCTV 0.316, 치안센터 0.241, 가로등 0.112이며, 본 프로젝트의 공공환경 안전도에서 CCTV와 치안시설을 높은 비중으로 둔 근거입니다. 또한 CCTV 100m, 가로등 10m, 보안등 5m, 치안센터 50m/500m/1km 영향권을 참고했습니다.  
  Source: https://koreascience.kr/article/JAKO201510534324352.pdf

- 건축공간연구원(AURI)·경찰청 공동연구 보도자료는 조명 설치 시 야간 5대 범죄 약 16% 감소, CCTV 감시범위 100m 내 야간 5대 범죄 약 11% 감소, 공동주택 1층 현관 도어락 설치 시 범죄 약 43% 감소를 보고했습니다. 이에 따라 조명, CCTV, 출입통제를 주요 요인으로 두었습니다. 비상벨·반사경 등은 범죄 자체 감소효과가 뚜렷하지 않았다고 되어 있어 낮은 비중의 비상/지원시설 항목으로만 반영했습니다.  
  Source: https://www.auri.re.kr/board.es?act=view&bid=0013&list_no=1190&mid=a10401030000

- 한국셉테드학회의 CPTED 기준과 국토교통부 범죄예방 건축기준 관련 자료는 다가구·다세대·오피스텔 등 실제 학생 주거 유형에서도 출입통제, 감시, 조명, 접근통제 요소를 고려할 수 있음을 뒷받침합니다.  
  Sources: https://www.cpted.or.kr/kr/business/standard.php, https://www.korea.kr/briefing/policyBriefingView.do?newsId=148863216

## 실행 방법

크롤링된 매물 CSV에 `lat/lng` 또는 `위도/경도`가 있으면 아래 명령으로 안전도 점수를 붙입니다.

```powershell
python score_rental_safety.py --input snu_area_rentals_crawled.csv --output snu_area_rentals_scored.csv
```

생성되는 주요 컬럼:

| column | meaning |
|---|---|
| `safety_score_100` | 0~100 최종 안전도 |
| `safety_score_10`, `safety`, `안전최종`, `안전도` | 앱 호환용 0~10 안전도 |
| `안전등급` | A, A-, B+, B, C, D |
| `안전_백분위` | 입력 후보 매물 내 상대 백분위 |
| `안전_cctv`, `안전_lighting`, `안전_police`, `안전_safe_route`, `안전_emergency` | 컴포넌트별 0~10 점수 |
| `가까운_cctv_m` 등 | 가장 가까운 해당 시설까지의 거리 |

`app.py`는 안전도 점수가 부여된 `snu_area_rentals_scored.csv`를 매물 데이터로 사용합니다.

## 데이터 재생성

원천 파일이 `raw/`와 `extracted/`에 있는 상태에서 아래 명령으로 관악구 필터링 데이터를 다시 만들 수 있습니다.

```powershell
python scripts/build_gwanak_safety_data.py
```

## 한계

- 이 점수는 범죄 발생의 직접 예측값이 아닙니다. 공공 안전 인프라 접근성을 CPTED 관점에서 정량화한 의사결정 보조 지표입니다.
- 생활안전지도 범죄주의구간 WMS, 실제 112 신고, 유동인구, 업종밀도, 야간 조도 실측값이 추가되면 보정력이 올라갑니다.
- 공동현관 비밀번호, 관리인 상주, 1층/지하 여부 등 건물 내부 요인은 공공데이터에서 자동 수집하기 어렵기 때문에 매물 크롤링 라벨 또는 수기 라벨로 보완해야 합니다.
