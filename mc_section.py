# -*- coding: utf-8 -*-
"""mc_section.py — Monte Carlo 불확실성 분석 섹션 (app.py에 두 줄로 부착).

app.py 통합:
    import mc_section
    mc_section.render(result, ASSUMPTIONS)
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from model import Params, rental_from_v1_row
from simulate import MCInputs, run_mc, tornado

_BLUE, _ORANGE, _PURPLE = "#2e86de", "#eb6e4b", "#8d6bd6"


def _params(assumptions: dict) -> Params:
    return Params(
        analysis_years=assumptions["analysis_years"],
        annual_interest_rate=assumptions["annual_interest_rate"],
        school_days_per_month=assumptions["school_days_per_month"],
        hourly_time_value_won=assumptions["hourly_time_value_won"],
        moving_cost=assumptions["moving_cost"],
        commute_fixed_monthly=(assumptions["commute_base_transport"]
                               + assumptions["commute_food_extra"]),
    )


def render(result: pd.DataFrame, assumptions: dict) -> None:
    st.subheader("불확실성 분석 — 답 대신 확률을")
    st.caption(
        "통학시간·시간가치 같은 입력은 하나의 숫자가 아니라 범위입니다. "
        "범위를 입력하면 1만 개의 가상 시나리오를 만들어 "
        "'자취가 유리할 확률'과 절약액의 분포를 계산합니다."
    )

    p = _params(assumptions)
    commute_row = result[result["유형"] == "통학"].iloc[0]
    m_mode = float(commute_row["편도시간"])
    rentals = result[result["유형"] != "통학"].sort_values("AEC")
    if rentals.empty:
        st.info("자취 매물이 없어 시뮬레이션을 수행할 수 없습니다.")
        return

    chosen = st.selectbox("비교할 자취 매물 ", rentals["대안"].tolist(), index=0)
    rental = rental_from_v1_row(rentals[rentals["대안"] == chosen].iloc[0])

    st.markdown("**입력 범위** — 점이 아니라 구간으로")
    c1, c2, c3 = st.columns(3)
    m_lo = c1.number_input("통학시간 최소 (편도분)", 5.0, 300.0, max(5.0, m_mode * 0.85), 1.0)
    m_md = c2.number_input("통학시간 보통 (편도분)", 5.0, 300.0, m_mode, 1.0)
    m_hi = c3.number_input("통학시간 최악 (편도분)", 5.0, 400.0, m_mode * 1.5, 1.0,
                           help="환승 실패, 연착 등을 포함한 현실적 최악값. "
                                "최악 꼬리가 길수록 통학의 변동성 비용이 커집니다.")
    c4, c5, c6 = st.columns(3)
    w0 = float(assumptions["hourly_time_value_won"])
    w_lo = c4.number_input("시간가치 하한 (원/시간)", 1000.0, 100000.0, w0, 500.0)
    w_hi = c5.number_input("시간가치 상한 (원/시간)", 1000.0, 200000.0, w0 * 1.6, 500.0,
                           help="최저시급(기회비용 하한)부터 본인 과외 시급 등 "
                                "실제 대안 임금까지의 범위")
    d_mid = float(assumptions["school_days_per_month"])
    d_rng = c6.slider("월 등교일수 범위", 10.0, 26.0, (d_mid - 3, d_mid + 1), 1.0)

    if m_lo > m_md or m_md > m_hi or w_lo > w_hi:
        st.error("범위가 올바르지 않습니다: 최소 ≤ 보통 ≤ 최악, 하한 ≤ 상한이어야 합니다.")
        return

    mc = MCInputs(
        commute_tri=(m_lo, m_md, m_hi),
        wage_range=(w_lo, w_hi),
        days_range=d_rng,
        rate_range=(p.annual_interest_rate, p.annual_interest_rate),
    )
    res = run_mc(rental, mc, p)

    a, b, c = st.columns(3)
    a.metric("자취가 유리할 확률", f"{res['p_rental_better']*100:.0f}%")
    b.metric("절약액 중앙값", f"{res['q50']:+.0f}만원/년",
             help="양수 = 자취 선택 시 절약, 음수 = 통학이 그만큼 유리")
    c.metric("90% 신뢰구간", f"[{res['q05']:+.0f}, {res['q95']:+.0f}]만원/년")

    # ── 절약액 분포 히스토그램
    fig = go.Figure()
    save = res["save"]
    fig.add_trace(go.Histogram(
        x=save[save <= 0], nbinsx=40, name="통학 유리 시나리오",
        marker_color=_ORANGE, opacity=0.75))
    fig.add_trace(go.Histogram(
        x=save[save > 0], nbinsx=40, name="자취 유리 시나리오",
        marker_color=_BLUE, opacity=0.75))
    fig.add_vline(x=0, line_color=_PURPLE, line_width=2)
    fig.add_vline(x=res["q50"], line_dash="dot", line_color="#555",
                  annotation_text="중앙값")
    fig.update_layout(
        barmode="overlay",
        title=dict(text=f"자취 선택 시 연간 절약액 분포 — 1만 시나리오 ({rental.name})",
                   font=dict(size=15)),
        xaxis=dict(title="절약액 (만원/년) · 0 왼쪽 = 통학 유리, 오른쪽 = 자취 유리"),
        yaxis=dict(title="시나리오 수"),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        margin=dict(l=10, r=10, t=70, b=10), height=380,
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── 토네이도: 어떤 입력이 결론을 가장 흔드는가
    rows = tornado(rental, mc, p)
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(
        y=[r["입력"] for r in rows],
        x=[r["save_hi"] - r["save_lo"] for r in rows],
        base=[r["save_lo"] for r in rows],
        orientation="h", marker_color=_BLUE, opacity=0.7,
        hovertemplate="%{base:.0f} ~ %{x:.0f} 만원/년<extra></extra>",
    ))
    fig2.add_vline(x=rows[0]["base"], line_dash="dot", line_color="#555",
                   annotation_text="대표값 기준")
    fig2.add_vline(x=0, line_color=_PURPLE, line_width=2)
    fig2.update_layout(
        title=dict(text="토네이도 차트 — 입력 하나씩 흔들었을 때 절약액의 변동 폭",
                   font=dict(size=15)),
        xaxis=dict(title="절약액 (만원/년)"),
        yaxis=dict(autorange="reversed"),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=70, b=10), height=320, showlegend=False,
    )
    st.plotly_chart(fig2, use_container_width=True)
    st.caption("막대가 보라색 0선을 가로지르는 입력은 그 하나만으로 결론을 "
               "뒤집을 수 있다는 뜻입니다. 가로지르지 않으면 결론은 그 입력에 견고합니다.")

    # ── 정보의 가치
    d, e, f = st.columns(3)
    d.metric("EVPI — 완전정보의 가치", f"{res['evpi']:.1f}만원/년",
             help="결정 전에 모든 불확실성이 해소된다면 기대할 수 있는 추가 절감. "
                  "어떤 조사·정보 수집도 이 값 이상의 가치를 가질 수 없는 상한선.")
    e.metric("통학시간 실측의 가치", f"{res['evppi_commute']:.1f}만원/년",
             help="결정 전에 한 달간 통학시간만 실제로 재 보는 행위의 기대 가치(EVPPI). "
                  "이 값이 실측에 드는 수고보다 크면 실측이 합리적입니다.")
    f.metric("시간가치 성찰의 가치", f"{res['evppi_wage']:.1f}만원/년",
             help="'내 1시간이 실제로 얼마인가'를 확정하는 것의 기대 가치(EVPPI). "
                  "통학시간 실측보다 이 값이 크면, 측정보다 자기 기준 정립이 먼저입니다.")
