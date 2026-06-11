# -*- coding: utf-8 -*-
"""aggregate.py — 무형가치 집계 로직 (3단 구조).

v1의 "가중합 종합점수"를 대체하는 명시적 의사결정 로직:

  1단 (비보상적 제약): 안전·예산·통학시간 상한은 점수가 아니라 자격 요건.
      미달이면 가격 불문 탈락. 탈락 사유를 기록해 투명하게 보여준다.
  2단 (WTP 화폐환산): 편의성처럼 돈과 거래 가능한 무형가치는
      "최고 편의 대비 부족분 × 1점당 지불용의(만원/월)"로 월비용에 가산.
  3단 (Pareto frontier): 그래도 합산 불가한 차원(비용 vs 안전)은
      지배당하는 대안만 제거하고 최종 선택은 사용자에게.

Streamlit에 의존하지 않는 순수 로직 모듈. pandas DataFrame은
v1 build_alternatives()의 결과 형식(대안/유형/월현금지출/월실질비용/
안전/편의도/편도시간 컬럼)을 그대로 받는다.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class ConstraintSet:
    """1단 하드 제약. None이면 해당 제약을 적용하지 않는다."""

    budget_monthly: float | None = None        # 월 현금지출 상한 (만원)
    min_safety: float | None = None            # 안전 최종점수 하한 (0~10)
    max_one_way_minutes: float | None = None   # 편도 통학시간 상한 (분)


# ──────────────────────────────────────────────
# 1단: 제약 평가 (탈락 사유 기록 포함)
# ──────────────────────────────────────────────
def evaluate_constraints(
    df: pd.DataFrame, cons: ConstraintSet, safety_col: str = "안전"
) -> pd.DataFrame:
    """각 대안에 통과 여부(통과)와 탈락 사유(탈락사유)를 붙인 사본을 반환.

    통학(유형=='통학')은 '기준 대안'이므로 안전·시간 제약을 적용하지 않고
    예산 제약만 검사한다 — 본가 통학은 안전 커트라인의 대상이 아니기 때문.
    """
    out = df.copy()
    reasons: list[str] = []
    for _, row in out.iterrows():
        r: list[str] = []
        if cons.budget_monthly is not None and row["월현금지출"] > cons.budget_monthly:
            r.append(f"예산 {row['월현금지출'] - cons.budget_monthly:.0f}만원 초과")
        if row["유형"] != "통학":
            if cons.min_safety is not None and row[safety_col] < cons.min_safety:
                r.append(f"안전 {cons.min_safety - row[safety_col]:.1f}점 미달")
            if (cons.max_one_way_minutes is not None
                    and row["편도시간"] > cons.max_one_way_minutes):
                r.append(f"통학시간 {row['편도시간'] - cons.max_one_way_minutes:.0f}분 초과")
        reasons.append(", ".join(r))
    out["탈락사유"] = reasons
    out["통과"] = out["탈락사유"] == ""
    return out


def relaxation_hints(
    df_evaluated: pd.DataFrame, cons: ConstraintSet, safety_col: str = "안전"
) -> list[str]:
    """통과한 자취 대안이 없을 때, "어떤 제약을 얼마나 완화하면 후보가 생기는지" 제안.

    원리: 정확히 한 가지 제약만 어긴 대안을 찾아, 그 제약의 최소 완화폭을 계산한다.
    (두 가지 이상 어긴 대안은 복합 완화가 필요하므로 제안에서 제외)
    """
    rentals = df_evaluated[df_evaluated["유형"] != "통학"]
    if rentals["통과"].any():
        return []

    hints: list[str] = []

    if cons.budget_monthly is not None:
        only_budget = rentals[
            (rentals["월현금지출"] > cons.budget_monthly)
            & ((cons.min_safety is None) | (rentals[safety_col] >= cons.min_safety))
            & ((cons.max_one_way_minutes is None)
               | (rentals["편도시간"] <= cons.max_one_way_minutes))
        ]
        if not only_budget.empty:
            need = only_budget["월현금지출"].min() - cons.budget_monthly
            who = only_budget.loc[only_budget["월현금지출"].idxmin(), "대안"]
            hints.append(f"월 예산을 +{need:.0f}만원 올리면 '{who}'가 후보에 들어옵니다.")

    if cons.min_safety is not None:
        only_safety = rentals[
            (rentals[safety_col] < cons.min_safety)
            & ((cons.budget_monthly is None)
               | (rentals["월현금지출"] <= cons.budget_monthly))
            & ((cons.max_one_way_minutes is None)
               | (rentals["편도시간"] <= cons.max_one_way_minutes))
        ]
        if not only_safety.empty:
            best = only_safety[safety_col].max()
            who = only_safety.loc[only_safety[safety_col].idxmax(), "대안"]
            hints.append(
                f"안전 커트라인을 {best:.1f}점으로 낮추면 '{who}'가 후보에 들어옵니다."
            )

    if not hints:
        hints.append("두 가지 이상의 제약을 동시에 완화해야 후보가 생깁니다. "
                     "커트라인 What-if 차트에서 조합을 탐색해 보세요.")
    return hints


def cutoff_sweep(
    rentals: pd.DataFrame,
    cutoffs: list[float],
    cost_col: str = "보정월비용",
    safety_col: str = "안전",
) -> pd.DataFrame:
    """안전 커트라인 What-if: 커트라인별 (통과 후보 수, 최저 비용)을 표로.

    제약 방식의 약점인 '절벽 효과'(커트라인 근처 0.1점 차이가 당락을 가름)를
    숨기지 않고 보여주기 위한 기능. 결정 경계와 같은 철학의 what-if다.
    """
    rows = []
    for c in cutoffs:
        passing = rentals[rentals[safety_col] >= c]
        rows.append({
            "커트라인": c,
            "후보수": len(passing),
            "최저비용": passing[cost_col].min() if len(passing) else None,
        })
    return pd.DataFrame(rows)


# ──────────────────────────────────────────────
# 2단: 편의성 WTP 화폐환산
# ──────────────────────────────────────────────
def apply_wtp(
    df: pd.DataFrame,
    wtp_per_point: float,
    conv_col: str = "편의도",
    cost_col: str = "월실질비용",
) -> pd.DataFrame:
    """편의 부족분을 화폐로 환산해 월비용에 가산한 사본을 반환.

    편의환산(만원/월) = (전체 최고 편의점수 − 내 편의점수) × 1점당 WTP
    보정월비용 = 월실질비용 + 편의환산

    해석: "가장 편한 대안 대비 불편함을 돈으로 보상받는다면 월 얼마인가".
    WTP=0이면 보정월비용 == 월실질비용 (편의 무시와 동일).
    """
    out = df.copy()
    ref = out[conv_col].max()
    out["편의환산"] = (ref - out[conv_col]) * wtp_per_point
    out["보정월비용"] = out[cost_col] + out["편의환산"]
    return out


# ──────────────────────────────────────────────
# 3단: Pareto frontier
# ──────────────────────────────────────────────
def pareto_mask(costs: pd.Series, benefits: pd.Series) -> pd.Series:
    """비용은 낮을수록, 편익(안전)은 높을수록 좋을 때 '지배당하지 않는' 대안 표시.

    대안 A가 대안 B를 지배한다 = A가 비용도 같거나 싸고 편익도 같거나 높으며,
    적어도 하나는 엄격히 더 좋다. 지배당한 대안은 어떤 선호를 가진 사람도
    고를 이유가 없으므로 제거 가능하다. 남은 frontier 위의 선택은 사용자 몫.
    """
    n = len(costs)
    cost_arr, ben_arr = costs.to_numpy(), benefits.to_numpy()
    mask = []
    for i in range(n):
        dominated = False
        for j in range(n):
            if i == j:
                continue
            if (cost_arr[j] <= cost_arr[i] and ben_arr[j] >= ben_arr[i]
                    and (cost_arr[j] < cost_arr[i] or ben_arr[j] > ben_arr[i])):
                dominated = True
                break
        mask.append(not dominated)
    return pd.Series(mask, index=costs.index)
