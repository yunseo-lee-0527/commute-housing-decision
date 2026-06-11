# CLAUDE.md — 프로젝트 컨텍스트 (Claude Code 인수인계용)

## 사용자 컨텍스트 (중요)

- 사용자(재원)는 SNU 산업공학과 **학부 저학년**. 전공 용어(AEC, NPV, 레포 등)
  사용 시 **반드시 짧은 부연설명**을 붙일 것.
- **Git 초보**. 행동 지시는 복붙 가능한 명령어로 명확하게. 에러 발생 시
  메시지 해석부터. 작업 사이클: `git pull` → 수정 → 테스트 → `git add` →
  `git commit -m "한국어 설명형 메시지"` → `git push`.
- 환경: Windows ARM, MSYS2/Git Bash (CLANGARM64), Python 3.10
  (`C:\Python project\Python310`), VS Code. GitHub 계정 `yoonjw220-web`
  (collaborator). 레포: `github.com/yunseo-lee-0527/commute-housing-decision`
  (소유자 = 팀원 yunseo).
- 협업 규칙: 팀원과 같은 파일 동시 수정 금지. `app.py`, `rentals_dummy.csv`,
  `build_gtfs_cache.py`는 팀원(yunseo) 소유 — 수정 시 최소 diff + 사전 협의.
  `.streamlit/secrets.toml`(카카오 API 키)과 `.pptx`는 절대 커밋 금지.

## 프로젝트 개요

산업공학의 이해 텀프로젝트: **자취 vs 통학 의사결정 지원 도구** (Streamlit 웹앱).
4년 기준 NPV/AEC로 현 거주지 통학과 학교 근처 자취를 비교.

교수님 피드백 4개가 v2 개발의 동기이자 평가 기준:
1. What-if — 정답 대신 "결론이 갈리는 조건"을 보여줄 것
2. 입력 불확실성 반영
3. 무형가치(안전·편의)의 반영 방식을 explicit하게
4. 경제성공학 외 IE 영역 적용

설계 철학: **"정답 기계 → 답의 지도"**. v1(가중합 종합점수)을 갈아엎지 않고
새 모듈을 옆에 꽂는 플러그인 방식. v1 한계 진단 → v2 재설계가 발표 서사.

## 파일 구조

v1 (팀원 작성, 보존):
- `app.py` (~930줄): 주소검색(카카오)→통학시간(GTFS 다익스트라/카카오 보정/
  haversine)→AEC 계산→가중합 종합점수→민감도 그리드. v2 섹션 render 호출
  몇 줄과 버그 수정만 추가됨.
- `rentals_dummy.csv`: 더미 매물 8건. 안전 체크리스트 컬럼 6개
  (door_lock, not_ground, main_road, cctv, manager, street_light) 추가됨.
- `build_gtfs_cache.py`, `.streamlit/`

v2 (이 작업에서 추가, 모두 순수 로직 + Streamlit 섹션 분리 구조):
- `model.py`: 닫힌 해 코어. `Params`, `Rental` dataclass,
  `aec_rental/aec_commute/break_even_rent/decision_boundary/aec_breakdown/
  equivalences/rental_from_v1_row`
- `boundary_viz.py`: 결정 경계 plotly (월세×통학시간 평면, 시간가치 ±30% 띠,
  현재 위치 별, x축이 경계 교차점 자동 포함)
- `v2_section.py`: app.py 연결 — `v2_section.render(result, ASSUMPTIONS)`
- `simulate.py`: MC (`MCInputs` 삼각/균등, n=10000, seed=42), `run_mc` 반환:
  save 배열, p_rental_better, q05/q50/q95, evpi, evppi_commute, evppi_wage.
  `tornado` (OAT). EVPPI는 50분위 binning 방식.
- `mc_section.py`: `mc_section.render(result, ASSUMPTIONS)`. 통학시간
  min/mode/max + 시간가치/등교일수 범위 입력. number_input 상한 999분.
- `aggregate.py`: 무형가치 3단 — `ConstraintSet`, `evaluate_constraints`
  (탈락사유 문자열), `relaxation_hints` (전멸 시 완화 제안), `cutoff_sweep`,
  `apply_wtp` (편의환산 = (최고편의−편의)×WTP), `pareto_mask`
- `aggregate_section.py`: `aggregate_section.render(result)`. 예산/안전
  커트라인/WTP 입력, 슬라이더 실시간 피드백(통과 수, 0.5 낮추면 +N곳),
  체크리스트 O/X 표, 주관 보정 data_editor(±3), 탈락 회색 표시, 커트라인
  what-if 차트, Pareto frontier, **무형가치 반영 최종 추천**(통과 대안 중
  보정월비용 최저, 통학 포함)
- `safety.py`: 체크리스트 채점표 RUBRIC (도어락2/비1층1.5/큰길1.5/CCTV1/
  관리인2/가로등2 = 만점10), `derived_scores`, `breakdown_table`,
  `describe_cutoff` (커트라인→자연어), `load_checklist` (구형 CSV 폴백→None)
- 테스트 3개 (총 16검사): `test_model.py`(5), `test_v3.py`(7),
  `test_safety.py`(4). 실행: `python test_모듈.py`. 코드 수정 후 필수 실행.
- `requirements.txt`: streamlit pandas numpy folium streamlit-folium
  requests **plotly**

## 핵심 수학 (검증 완료, v1 대비 오차 ~1e-12)

- AEC_자취 = M·CRF + d·i + 12(r+F) + τ·m  /  AEC_통학 = 12·F_c + τ·m_c
  (M=이사비60, d=보증금, F_c=16, τ = 0.4·D·w/10⁴ 만원/년·편도분)
- 항등식: (A/P)−(A/F)=i → **보증금 연비용 = 보증금×금리** (정확)
- 손익분기 월세 닫힌 해: r* = [AEC_통학 − M·CRF − d·i − 12F − τm_r]/12
  (v1 이분탐색 [0,300] 포화 버그를 닫힌 해가 해결 — test_v1_cap_bug_fixed)
- 결정 경계 = (월세×통학시간) 평면의 직선, 기울기 τ/12
  (기본 가정: 편도10분 ≈ 월세 7.57만원, 보증금1000만원 ≈ 월 4.17만원)
- 금리는 결론에 둔감 (비선형 항이 M·CRF뿐) — 토네이도에서 수식으로 예언됨

## 수정된 버그 (발표 소재)

1. v1 시간 이중계산 (AEC에 시간비용 포함 + 별도 시간점수 22%)
2. min-max 상대 정규화의 rank reversal
3. 예산 패널티(-0.25)가 보상 가능 → 하드 제약으로 승격
4. 이분탐색 300만원 포화
5. **추천 모순**: 종합점수 기준 추천 vs AEC 기준 비교가 분열 → 상단 추천을
   "예산 내 AEC 최저"로 통일 + 예산 때문에 더 싼 자취 탈락 시 "예산 +N만원
   완화하면 연 X만원 경제적" caption. 무형가치 섹션 끝의 최종 추천이 결론.
6. 버튼 후 슬라이더 조작 시 화면 소실 → `st.session_state.analysis_done`
   플래그로 수정 (주소 변경 시 기존 리셋 로직과 연동)
7. 원거리 좌표 선택 시 number_input max 초과 크래시 → 상한 999

## 개념적 합의 사항

- 무형가치 3단: 안전·예산=비보상적 제약 / 편의=WTP 화폐환산 / 잔여=Pareto.
  기준이 보정월비용 하나로 수렴 → 추천 모순 구조적 불가능.
- 안전 점수 = 객관 체크리스트 유도 + 주관 보정(±3) 분리 표시. 반지하 매물은
  not_ground=0 (test_safety가 검증).
- EVPI/EVPPI: 단일 변수 EVPPI가 작아도 EVPI가 클 수 있음 — 시간비용이 w×m
  곱이라 결론이 조합으로 뒤집힘. "정보는 선택을 바꿀 때만 가치" 프레임.
- MC 한계 (Q&A 대비): 입력 독립 가정, EVPPI 수치는 입력 범위 의존.
- 예산은 현금(월총비용) 기준이라 시간비용 큰 통학도 통과 — 의도된 설계
  (예산=유동성 제약, 시간=기회비용, AEC에는 둘 다 포함).

## 다음 작업 (우선순위순)

1. **기말발표 자료 제작** (메인 목표). 서사: v1 한계 진단 → "답의 지도"
   철학 → 닫힌 해 유도 → 결정 경계 → MC 확률 → 무형가치 3단 → EVPI.
   적용 영역 카운트: 경제성공학+의사결정분석+시뮬레이션+MCDM(+아래 2개).
2. **Newsvendor 출발 버퍼 모듈** (합의됨, 미구현): 출발 시각 결정 = 임계비율
   β=Cu/(Cu+Co) 분위수. MC의 통학시간 삼각분포 재사용. 미결: Cu(지각 비용)
   설정 방식 — 객관 환산(등록금÷수업횟수) vs 사용자 입력. 사용자 답변 대기.
3. **DOE 2^k 요인설계** (합의됨, 미구현): 4입력 2수준 16조합으로 주효과/
   교호작용 분리, w×m 교호작용 > 주효과 입증. 토네이도(OAT)의 한계 보완.
4. MC 히스토그램 binning 결함: 음수/양수 trace의 bin 폭 불일치 → 양쪽에
   동일 `xbins=dict(size=...)` 지정 (한 줄).
5. `convenience.py` (설계만 됨): 편의 3분해 — A 시간환원(도보분×빈도×τ),
   B 화폐환원(빌트인×CRF), C 잔여 WTP. CSV 컬럼 확장 필요, 팀 협의.
6. 향후과제 (보고서용): 실데이터 크롤링, 매물 통학시간 경로 기반 정밀화,
   v1 가중합 정리 여부(팀 결정 대기), 월세 상승률(증가연금), 혼잡 가중
   시간가치, 상관 샘플링, 헤도닉 가격모형, DP 이사시점, Streamlit 배포.

## 작업 시 주의

- 모든 신규 로직은 (순수 모듈 + _section UI) 분리 패턴 유지, 테스트 동반.
- app.py 수정은 최소 diff. CSV 스키마 변경 시 safety.load_checklist처럼
  구형 폴백 제공 (팀원 환경 보호).
- plotly 배경 투명 (다크/라이트 겸용), 한국어 라벨.
- 참고 문서: 레포의 `수정사항.md` (팀원용 설명), INTEGRATION 가이드 2개는
  로컬에만 있을 수 있음.
