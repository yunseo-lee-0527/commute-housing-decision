# -*- coding: utf-8 -*-
"""v2_section.py — 기존 app.py에 두 줄로 붙는 결정 경계(What-if) 섹션.

app.py 통합 방법 (민감도 분석 st.subheader 위쪽 등 원하는 위치에):

    import v2_section
    v2_section.render(result, ASSUMPTIONS)

`result`는 기존 build_alternatives()의 반환 DataFrame을 그대로 받는다.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from boundary_viz import build_boundary_figure, build_breakdown_figure
from model import Params, break_even_rent, equivalences, rental_from_v1_row


def _params_from_assumptions(assumptions: dict) -> Params:
    return Params(
        analysis_years=assumptions["analysis_years"],
        annual_interest_rate=assumptions["annual_interest_rate"],
        school_days_per_month=assumptions["school_days_per_month"],
        hourly_time_value_won=assumptions["hourly_time_value_won"],
        moving_cost=assumptions["moving_cost"],
        commute_fixed_monthly=(
            assumptions["commute_base_transport"] + assumptions["commute_food_extra"]
        ),
    )


def render(result: pd.DataFrame, assumptions: dict) -> None:
    """결정 경계 + 월 등가비용 분해 섹션을 렌더링한다."""
    p = _params_from_assumptions(assumptions)

    commute_row = result[result["유형"] == "통학"].iloc[0]
    m_now = float(commute_row["편도시간"])
    rentals = result[result["유형"] == "자취"].sort_values("AEC")
    if rentals.empty:
        st.info("자취 매물이 없어 결정 경계를 그릴 수 없습니다.")
        return

    st.subheader("손익분기점 — 어떤 조건에서 결론이 뒤집히는가")

    names = rentals["대안"].tolist()
    chosen = st.selectbox("비교할 자취 매물", names, index=0,
                          help="기본값은 AEC가 가장 낮은 매물입니다.")
    rental = rental_from_v1_row(rentals[rentals["대안"] == chosen].iloc[0])

    r_star = break_even_rent(rental, m_now, p)
    c1, c2, c3 = st.columns(3)
    c1.metric("손익분기 월세 (닫힌 해)",
              "월세 0원도 불리" if r_star < 0 else f"{r_star:.0f}만원")
    c2.metric("현재 월세와의 차이",
              "-" if r_star < 0 else f"{rental.monthly_rent - r_star:+.0f}만원")
    eq = equivalences(p)
    c3.metric("교환비", f"편도 1분 ↔ {eq['tau_만원_per_년_편도분']/12:.2f}만원/월")

    st.plotly_chart(
        build_boundary_figure(rental, m_now, p),
        width="stretch",
        theme=None,
    )
    st.plotly_chart(
        build_breakdown_figure(rental, m_now, p),
        width="stretch",
        theme=None,
    )

    st.caption(
        f"메커니즘: 보증금 1,000만원의 실질 비용은 정확히 보증금×금리 = "
        f"월 {eq['보증금1000만원의_월비용_만원']:.2f}만원, "
        f"이사비 {assumptions['moving_cost']:.0f}만원은 월 {eq['이사비의_월비용_만원']:.2f}만원, "
        f"편도 10분은 월세 {eq['편도10분의_월세등가_만원']:.1f}만원과 등가입니다. "
        f"경계 직선의 기울기(τ/12)가 곧 시간↔월세 교환비이며, "
        f"보라색 띠는 시간가치를 ±30% 흔들었을 때 경계가 움직이는 범위입니다."
    )
