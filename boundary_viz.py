# -*- coding: utf-8 -*-
"""boundary_viz.py — 결정 경계(What-if) 및 월 등가비용 분해 시각화.

model.py의 닫힌 해를 그림으로 옮기는 순수 plotly 모듈 (Streamlit 비의존).
배경을 투명하게 두어 라이트/다크 테마 모두에서 동작한다.
"""
from __future__ import annotations

import plotly.graph_objects as go

from model import (
    Params,
    Rental,
    aec_breakdown,
    break_even_rent,
    decision_boundary,
    tau,
)

_COL_RENTAL = "rgba(46, 134, 222, 0.18)"   # 자취 유리 영역
_COL_COMMUTE = "rgba(235, 110, 75, 0.18)"  # 통학 유리 영역
_COL_LINE = "#8d6bd6"
_COL_BAND = "rgba(141, 107, 214, 0.22)"
_COL_POINT = "#f5b942"


def build_boundary_figure(
    rental: Rental,
    current_commute_minutes: float,
    p: Params = Params(),
    time_value_multipliers: tuple[float, float] | None = (0.7, 1.3),
    minutes_range: tuple[float, float] | None = None,
) -> go.Figure:
    """(편도 통학시간 × 월세) 평면의 결정 경계 그림.

    - 경계 직선: AEC_자취 = AEC_통학 이 되는 (m_c, r) 조합. 기울기 = τ/12.
    - 음영: 경계 아래 = 자취 유리, 위 = 통학 유리.
    - 별 마커: 사용자의 현재 조건 (현 거주지 통학시간, 선택 매물 월세).
    - 보라색 띠: 시간가치 w 를 ×0.7~×1.3 으로 흔들 때 경계가 움직이는 범위.
      띠는 m_c = (매물 통학시간) 에서 한 점으로 모인다 — 두 대안의 통학시간이
      같으면 시간가치가 결론에 영향을 주지 않기 때문 (모델의 구조적 성질).
    """
    line = decision_boundary(rental, p)

    if minutes_range is None:
        hi = max(90.0, current_commute_minutes * 1.4)
        # 현재 월세에서 결론이 뒤집히는 통학시간(m*)이 양수면 그 지점까지 보여준다
        m_star_auto = line.minutes_at(rental.monthly_rent)
        if 0 < m_star_auto <= 360:
            hi = max(hi, m_star_auto * 1.2)
        minutes_range = (0.0, float(round(hi / 10) * 10))
    m_lo, m_hi = minutes_range

    r_at_lo, r_at_hi = line.rent_at(m_lo), line.rent_at(m_hi)
    r_top = max(rental.monthly_rent * 1.5, r_at_hi * 1.15, 40.0)
    r_top = float(round(r_top / 10) * 10)

    fig = go.Figure()

    # ── 영역 음영 (경계선 기준 위/아래)
    fig.add_trace(go.Scatter(
        x=[m_lo, m_hi, m_hi, m_lo], y=[r_at_lo, r_at_hi, r_top, r_top],
        fill="toself", fillcolor=_COL_COMMUTE, line=dict(width=0),
        hoverinfo="skip", showlegend=False,
    ))
    fig.add_trace(go.Scatter(
        x=[m_lo, m_hi, m_hi, m_lo], y=[r_at_lo, r_at_hi, 0, 0],
        fill="toself", fillcolor=_COL_RENTAL, line=dict(width=0),
        hoverinfo="skip", showlegend=False,
    ))

    # ── 시간가치 불확실성 띠
    if time_value_multipliers is not None:
        lo_mult, hi_mult = time_value_multipliers
        band_lines = []
        for mult in (lo_mult, hi_mult):
            p_w = p.with_(hourly_time_value_won=p.hourly_time_value_won * mult)
            band_lines.append(decision_boundary(rental, p_w))
        ys = [
            [bl.rent_at(m_lo) for bl in band_lines],
            [bl.rent_at(m_hi) for bl in band_lines],
        ]
        fig.add_trace(go.Scatter(
            x=[m_lo, m_hi], y=[min(ys[0]), min(ys[1])],
            line=dict(width=0), hoverinfo="skip", showlegend=False,
        ))
        fig.add_trace(go.Scatter(
            x=[m_lo, m_hi], y=[max(ys[0]), max(ys[1])],
            fill="tonexty", fillcolor=_COL_BAND,
            line=dict(width=0), hoverinfo="skip",
            name=f"시간가치 ×{lo_mult}~×{hi_mult} 변동 시 경계 이동 범위",
            showlegend=True,
        ))

    # ── 경계 직선
    fig.add_trace(go.Scatter(
        x=[m_lo, m_hi], y=[r_at_lo, r_at_hi],
        mode="lines", line=dict(color=_COL_LINE, width=3),
        name="결정 경계 (AEC 동일선)",
        hovertemplate="편도 %{x:.0f}분 ↔ 손익분기 월세 %{y:.1f}만원<extra></extra>",
    ))

    # ── 현재 위치 + 경계까지의 거리 안내선
    r_now = rental.monthly_rent
    m_now = current_commute_minutes
    r_star = break_even_rent(rental, m_now, p)
    m_star = line.minutes_at(r_now)

    fig.add_trace(go.Scatter(
        x=[m_now], y=[r_now], mode="markers+text",
        marker=dict(symbol="star", size=17, color=_COL_POINT,
                    line=dict(width=1, color="#7a5a14")),
        text=["현재 조건"], textposition="top center",
        name="현재 조건 (통학시간, 매물 월세)",
        hovertemplate=("현 거주지 편도 %{x:.0f}분<br>"
                       f"{rental.name} 월세 %{{y:.0f}}만원<extra></extra>"),
    ))
    if 0 <= r_star <= r_top:
        fig.add_trace(go.Scatter(
            x=[m_now, m_now], y=[r_now, r_star], mode="lines",
            line=dict(color=_COL_POINT, width=1.5, dash="dot"),
            hoverinfo="skip", showlegend=False,
        ))
    if m_lo <= m_star <= m_hi:
        fig.add_trace(go.Scatter(
            x=[m_now, m_star], y=[r_now, r_now], mode="lines",
            line=dict(color=_COL_POINT, width=1.5, dash="dot"),
            hoverinfo="skip", showlegend=False,
        ))

    side = "자취 유리" if r_now < r_star else "통학 유리"
    d_rent = r_now - r_star          # +면 월세가 이만큼 내려야 자취 유리
    d_min = m_star - m_now           # +면 통학시간이 이만큼 늘어야 자취 유리
    flip_txt = (
        f"월세 {abs(d_rent):.0f}만원 {'인하' if d_rent > 0 else '인상'} 또는 "
        f"통학시간 {abs(d_min):.0f}분 {'증가' if d_min > 0 else '감소'} 시 결론 반전"
    )

    fig.add_annotation(
        x=m_lo + (m_hi - m_lo) * 0.04, y=r_top * 0.95,
        text="<b>통학 유리</b>", showarrow=False,
        font=dict(color="#c0593a", size=14), xanchor="left",
    )
    fig.add_annotation(
        x=m_hi - (m_hi - m_lo) * 0.04, y=r_top * 0.06,
        text="<b>자취 유리</b>", showarrow=False,
        font=dict(color="#2868a8", size=14), xanchor="right",
    )

    fig.update_layout(
        title=dict(
            text=(f"결정 경계: {rental.name} vs 통학 — 현재 <b>{side}</b><br>"
                  f"<span style='font-size:12px'>{flip_txt} · "
                  f"교환비: 편도 1분 ↔ 월세 {tau(p)/12:.2f}만원</span>"),
            font=dict(size=16),
        ),
        xaxis=dict(title="현 거주지 → 학교 편도 통학시간 (분)",
                   range=[m_lo, m_hi], zeroline=False),
        yaxis=dict(title=f"{rental.name} 월세 (만원)",
                   range=[0, r_top], zeroline=False),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        margin=dict(l=10, r=10, t=110, b=10),
        height=520,
    )
    return fig


def build_breakdown_figure(
    rental: Rental,
    current_commute_minutes: float,
    p: Params = Params(),
) -> go.Figure:
    """통학 vs 자취의 '월 등가비용' 분해 누적 막대 — AEC÷12 가 어디서 오는지 한눈에."""
    rb = aec_breakdown(rental, p)
    t12 = tau(p) / 12.0

    commute_parts = {
        "고정월비용(교통+추가식비)": p.commute_fixed_monthly,
        "시간비용(τ/12×편도분)": t12 * current_commute_minutes,
    }

    cats = [f"통학 (편도 {current_commute_minutes:.0f}분)",
            f"{rental.name} (편도 {rental.one_way_minutes:.0f}분)"]
    palette = ["#2e86de", "#54a0ff", "#7ea8c4", "#b3c6d4", "#eb6e4b"]
    keys = ["월세", "고정월비용(관리비+생활비+교통비)", "보증금 이자(d×i÷12)",
            "이사비 연환산(M×CRF÷12)", "시간비용(τ/12×편도분)"]
    commute_map = {
        "고정월비용(관리비+생활비+교통비)": commute_parts["고정월비용(교통+추가식비)"],
        "시간비용(τ/12×편도분)": commute_parts["시간비용(τ/12×편도분)"],
    }

    fig = go.Figure()
    for color, key in zip(palette, keys):
        fig.add_trace(go.Bar(
            x=cats,
            y=[commute_map.get(key, 0.0), rb[key]],
            name=key, marker_color=color,
            hovertemplate="%{y:.1f}만원/월<extra>" + key + "</extra>",
        ))

    total_c = sum(commute_map.values())
    total_r = sum(rb.values())
    fig.add_annotation(x=cats[0], y=total_c, yshift=12, showarrow=False,
                       text=f"<b>{total_c:.1f}만원/월</b>")
    fig.add_annotation(x=cats[1], y=total_r, yshift=12, showarrow=False,
                       text=f"<b>{total_r:.1f}만원/월</b>")

    fig.update_layout(
        barmode="stack",
        title=dict(text="월 등가비용 분해 (AEC ÷ 12) — 모든 비용을 '월세 환산 만원'으로",
                   font=dict(size=16)),
        yaxis=dict(title="만원/월", zeroline=False),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0,
                    font=dict(size=10)),
        margin=dict(l=10, r=10, t=90, b=10),
        height=460,
    )
    return fig
