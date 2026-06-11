# -*- coding: utf-8 -*-
"""test_safety.py — 체크리스트 점수 유도 검증.  실행: python test_safety.py"""
import pandas as pd
from safety import MAX_SCORE, RUBRIC, breakdown_table, derived_scores, describe_cutoff, load_checklist


def test_rubric_max_is_ten():
    assert abs(MAX_SCORE - 10.0) < 1e-9
    print(f"[PASS] 채점표 합계 = {MAX_SCORE:g}점 (만점 10)")


def test_derived_matches_csv_safety():
    """유도 점수가 CSV의 기존 safety 숫자와 전 매물에서 일치해야 한다."""
    cl = load_checklist("rentals_dummy.csv")
    assert cl is not None, "체크리스트 컬럼이 CSV에 없음"
    raw = pd.read_csv("rentals_dummy.csv").set_index("name")["safety"]
    diff = (derived_scores(cl) - raw).abs().max()
    assert diff < 1e-9, f"불일치 최대 {diff}"
    print(f"[PASS] 유도 점수 == 기존 safety, 매물 {len(cl)}건 전부 일치")


def test_semantics():
    """반지하 매물은 '1층 아님' 항목이 꺼져 있어야 한다."""
    cl = load_checklist("rentals_dummy.csv")
    semi = [n for n in cl.index if "반지하" in n]
    assert all(cl.loc[n, "not_ground"] == 0 for n in semi)
    print(f"[PASS] 의미 일관성: 반지하 매물({len(semi)}건)의 '1층 아님' = X")


def test_breakdown_and_describe():
    cl = load_checklist("rentals_dummy.csv")
    bt = breakdown_table(cl)
    assert "안전 점수" in bt.columns and len(bt) == len(cl)
    assert "도어락" in describe_cutoff(6.0)
    assert load_checklist("없는파일.csv") is None          # 폴백 동작
    print("[PASS] 내역 표 생성, 커트라인 자연어 번역, 구형 CSV 폴백")


if __name__ == "__main__":
    test_rubric_max_is_ten()
    test_derived_matches_csv_safety()
    test_semantics()
    test_breakdown_and_describe()
    print("\n모든 테스트 통과 — safety.py 검증 완료")
