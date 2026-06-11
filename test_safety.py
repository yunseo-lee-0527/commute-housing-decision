# -*- coding: utf-8 -*-
"""safety.py 검증. 실행: python test_safety.py"""
import pandas as pd

from safety import (
    MAX_SCORE,
    SafetyScorer,
    breakdown_table,
    derived_scores,
    describe_cutoff,
    load_checklist,
    score_dataframe,
    score_home_safety,
)


def test_rubric_max_is_ten():
    assert abs(MAX_SCORE - 10.0) < 1e-9
    print(f"[PASS] 체크리스트 만점 = {MAX_SCORE:g}점")


def _sample_checklist() -> pd.DataFrame:
    """RUBRIC 영문 O/X 컬럼을 가진 인메모리 체크리스트 (더미 CSV 대체)."""
    return pd.DataFrame(
        {
            "door_lock": [1, 0],
            "not_ground": [1, 1],
            "main_road": [0, 1],
            "cctv": [1, 0],
            "manager": [0, 0],
            "street_light": [1, 1],
        },
        index=pd.Index(["A원룸", "B원룸"], name="name"),
    )


def test_derived_scores_sum_rubric():
    cl = _sample_checklist()
    scores = derived_scores(cl)
    # A원룸 = door_lock 2 + not_ground 1.5 + cctv 1 + street_light 2 = 6.5
    assert abs(scores["A원룸"] - 6.5) < 1e-9, scores.to_dict()
    print(f"[PASS] 체크리스트 가중합 점수 산출 ({len(cl)}건)")


def test_breakdown_and_describe():
    cl = _sample_checklist()
    bt = breakdown_table(cl)
    assert "안전 점수" in bt.columns and len(bt) == len(cl)
    assert "도어락" in describe_cutoff(6.0)
    assert load_checklist("없는파일.csv") is None
    print("[PASS] 체크리스트 상세표와 커트라인 설명 생성")


def test_public_safety_score_location():
    scorer = SafetyScorer()
    result = scorer.score_location(37.481217, 126.952713)
    assert 0 <= result["safety_score_100"] <= 100
    assert set(result["components"]) == {"cctv", "lighting", "police", "safe_route", "emergency"}
    assert result["components"]["cctv"]["nearest_m"] is None or result["components"]["cctv"]["nearest_m"] >= 0
    print(f"[PASS] 좌표 기반 안전도 산정: {result['safety_score_100']}점 / {result['grade']}")


def test_score_dataframe_adds_app_columns():
    df = pd.DataFrame(
        [
            {
                "매물명": "테스트 원룸",
                "주소": "서울특별시 관악구 봉천동",
                "위도": 37.481217,
                "경도": 126.952713,
                "보증금_만원": 1000,
                "월세_만원": 60,
                "관리비_만원": 8,
                "공동현관_비밀번호": "Y",
                "CCTV": "Y",
                "층정보": "3층",
            }
        ]
    )
    scored = score_dataframe(df)
    for col in ["safety", "안전최종", "안전_cctv", "가까운_cctv_m", "name", "lat", "lng"]:
        assert col in scored.columns
    assert 0 <= float(scored.loc[0, "safety"]) <= 10
    print("[PASS] 매물 CSV 안전도 컬럼 및 앱 호환 컬럼 생성")


def test_score_home_safety_wrapper():
    result = score_home_safety(37.470821, 126.936928)
    assert "public_environment_score_100" in result
    print("[PASS] score_home_safety 래퍼 동작")


if __name__ == "__main__":
    test_rubric_max_is_ten()
    test_derived_scores_sum_rubric()
    test_breakdown_and_describe()
    test_public_safety_score_location()
    test_score_dataframe_adds_app_columns()
    test_score_home_safety_wrapper()
    print("\n모든 safety.py 테스트 통과")
