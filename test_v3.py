# -*- coding: utf-8 -*-
"""test_v3.py — aggregate.py / simulate.py 검증.  실행: python test_v3.py"""
from __future__ import annotations

import numpy as np
import pandas as pd

from aggregate import (
    ConstraintSet, apply_wtp, cutoff_sweep, evaluate_constraints,
    pareto_mask, relaxation_hints,
)
from model import Params, Rental, aec_commute, aec_rental
from simulate import MCInputs, run_mc, tornado


def _mini_df():
    return pd.DataFrame([
        {"대안": "통학", "유형": "통학", "월현금지출": 16, "월실질비용": 52,
         "안전": 8, "편의도": 4, "편도시간": 48},
        {"대안": "A", "유형": "자취", "월현금지출": 120, "월실질비용": 135,
         "안전": 9, "편의도": 8, "편도시간": 10},
        {"대안": "B", "유형": "자취", "월현금지출": 95, "월실질비용": 110,
         "안전": 5, "편의도": 6, "편도시간": 15},
        {"대안": "C", "유형": "자취", "월현금지출": 100, "월실질비용": 118,
         "안전": 7, "편의도": 5, "편도시간": 20},
    ])


def test_constraints_and_reasons():
    df = evaluate_constraints(_mini_df(), ConstraintSet(budget_monthly=100, min_safety=6))
    by = df.set_index("대안")
    assert bool(by.loc["통학", "통과"])                      # 통학은 예산만 검사
    assert not by.loc["A", "통과"] and "예산" in by.loc["A", "탈락사유"]
    assert not by.loc["B", "통과"] and "안전" in by.loc["B", "탈락사유"]
    assert bool(by.loc["C", "통과"])
    print("[PASS] 제약 평가: 통과/탈락 및 탈락 사유 정확")


def test_relaxation():
    df = evaluate_constraints(_mini_df(), ConstraintSet(budget_monthly=90, min_safety=8))
    hints = relaxation_hints(df, ConstraintSet(budget_monthly=90, min_safety=8))
    assert hints and any("예산" in h or "안전" in h for h in hints)
    # 후보가 존재하면 힌트는 비어야 함
    df2 = evaluate_constraints(_mini_df(), ConstraintSet(budget_monthly=100, min_safety=6))
    assert relaxation_hints(df2, ConstraintSet(budget_monthly=100, min_safety=6)) == []
    print("[PASS] 완화 제안: infeasible일 때만 생성, 단일 제약 완화폭 제시")


def test_wtp_and_cutoff():
    df = apply_wtp(_mini_df(), wtp_per_point=2.0)
    by = df.set_index("대안")
    assert by.loc["A", "편의환산"] == 0.0                    # 최고 편의 = 기준점
    assert by.loc["통학", "편의환산"] == (8 - 4) * 2.0
    assert np.isclose(by.loc["B", "보정월비용"], 110 + 4.0)
    sweep = cutoff_sweep(df[df["유형"] != "통학"], [0, 6, 8, 9.5], "보정월비용", "안전")
    assert list(sweep["후보수"]) == [3, 2, 1, 0]             # 커트라인↑ → 후보 단조감소
    print("[PASS] WTP 환산 및 커트라인 sweep: 기준점·단조성 성립")


def test_pareto():
    df = _mini_df()[lambda d: d["유형"] != "통학"]
    mask = pareto_mask(df["월실질비용"], df["안전"])
    by = dict(zip(df["대안"], mask))
    assert by["A"] and by["B"] and by["C"]                  # 셋 다 비지배 (비용↑↔안전↑)
    df2 = pd.concat([df, pd.DataFrame([{"대안": "D", "유형": "자취", "월현금지출": 130,
        "월실질비용": 140, "안전": 5, "편의도": 5, "편도시간": 30}])], ignore_index=True)
    mask2 = pareto_mask(df2["월실질비용"], df2["안전"])
    assert not mask2.iloc[-1]                                # D는 B에 지배당함
    print("[PASS] Pareto: 지배 판정 정확")


def test_mc_degenerate_matches_closed_form():
    """모든 범위를 한 점으로 좁히면 MC는 닫힌 해와 정확히 일치해야 한다."""
    p = Params()
    rt = Rental("T", deposit=500, monthly_rent=52, fixed_monthly=57, one_way_minutes=19)
    mc = MCInputs(commute_tri=(48, 48, 48), wage_range=(10320, 10320),
                  days_range=(22, 22), rate_range=(0.05, 0.05), n=2000)
    res = run_mc(rt, mc, p)
    exact = aec_commute(48, p) - aec_rental(rt, p)
    assert abs(res["mean"] - exact) < 1e-9
    assert res["p_rental_better"] in (0.0, 1.0)
    assert abs(res["evpi"]) < 1e-9                          # 불확실성 0 → 정보가치 0
    print(f"[PASS] MC 퇴화 케이스: 닫힌 해와 일치 (절약액 {exact:.1f}만원/년)")


def test_mc_information_value_ordering():
    p = Params()
    rt = Rental("T", deposit=500, monthly_rent=52, fixed_monthly=57, one_way_minutes=19)
    mc = MCInputs(commute_tri=(100, 130, 200), wage_range=(10320, 25000),
                  days_range=(18, 24), rate_range=(0.03, 0.08), n=20000)
    res = run_mc(rt, mc, p)
    assert res["evpi"] >= -1e-9
    assert -1e-6 <= res["evppi_commute"] <= res["evpi"] + 0.5   # 0 ≤ EVPPI ≤ EVPI
    assert -1e-6 <= res["evppi_wage"] <= res["evpi"] + 0.5
    assert 0.0 < res["p_rental_better"] < 1.0               # 경계 근처라 확률이 갈림
    print(f"[PASS] 정보가치: EVPPI 통학시간 {res['evppi_commute']:.1f} / "
          f"시간가치 {res['evppi_wage']:.1f} ≤ EVPI {res['evpi']:.1f} 만원/년, "
          f"P(자취)={res['p_rental_better']:.0%}")


def test_tornado_consistency():
    p = Params()
    rt = Rental("T", deposit=500, monthly_rent=52, fixed_monthly=57, one_way_minutes=19)
    mc = MCInputs(commute_tri=(40, 48, 75), wage_range=(10320, 16000),
                  days_range=(19, 23), rate_range=(0.05, 0.05))
    rows = tornado(rt, mc, p)
    assert all(r["save_lo"] <= r["base"] + 1e-9 or r["save_lo"] <= r["save_hi"]
               for r in rows)
    assert all(rows[i]["폭"] >= rows[i + 1]["폭"] for i in range(len(rows) - 1))
    rate_row = next(r for r in rows if "금리" in r["입력"])
    assert rate_row["폭"] < 1e-9                            # 금리 범위 0 → 폭 0
    print("[PASS] 토네이도: 폭 내림차순 정렬, 고정 입력의 폭 0")


if __name__ == "__main__":
    test_constraints_and_reasons()
    test_relaxation()
    test_wtp_and_cutoff()
    test_pareto()
    test_mc_degenerate_matches_closed_form()
    test_mc_information_value_ordering()
    test_tornado_consistency()
    print("\n모든 테스트 통과 — aggregate.py / simulate.py 검증 완료")
