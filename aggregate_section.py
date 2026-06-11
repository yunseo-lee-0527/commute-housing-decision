# -*- coding: utf-8 -*-
"""aggregate_section.py — 무형가치 3단 집계 섹션 (app.py에 두 줄로 부착).

app.py 통합:
    import aggregate_section
    aggregate_section.render(result)
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from aggregate import (
    ConstraintSet,
    apply_wtp,
    cutoff_sweep,
    evaluate_constraints,
    pareto_mask,
    relaxation_hints,
)

_BLUE, _ORANGE, _PURPLE, _GRAY = "#2e86de", "#eb6e4b", "#8d6bd6", "#9aa3ad"


def render(result: pd.DataFrame) -> None:
    st.subheader("무형가치 처리 — 제약·환산·프런티어 3단 로직")
    st.caption(
        "안전은 돈으로 거래되지 않으므로 점수(가중치)가 아닌 자격 요건(제약)으로, "
        "편의는 거래 가능하므로 지불용의(WTP)로 화폐 환산해 비용에 합산합니다."
    )

    c1, c2, c3 = st.columns(3)
    budget = c1.number_input("월 예산 상한 (만원, 현금지출 기준)", 30, 300, 90, 5)
    min_safety = c2.slider("안전 커트라인 (이 점수 미만은 탈락)", 0.0, 10.0, 6.0, 0.5)
    wtp = c3.number_input("편의 1점당 지불용의 WTP (만원/월)", 0.0, 20.0, 2.0, 0.5,
                          help="예: '가장 편한 집 대비 편의가 1점 낮은 불편을 "
                               "월 몇 만원으로 보상받겠는가'에 대한 본인의 답")

    # ── 주관 보정: 객관 점수와 분리해 투명하게 표시
    rentals = result[result["유형"] != "통학"].copy()
    with st.expander("안전 점수 주관 보정 (직접 둘러본 체감 반영, ±3점)"):
        edit = st.data_editor(
            rentals[["대안", "안전"]].assign(주관보정=0.0),
            column_config={
                "대안": st.column_config.TextColumn(disabled=True),
                "안전": st.column_config.NumberColumn("안전(객관)", disabled=True),
                "주관보정": st.column_config.NumberColumn(min_value=-3.0, max_value=3.0,
                                                      step=0.5),
            },
            hide_index=True, use_container_width=True,
        )
    adj = dict(zip(edit["대안"], edit["주관보정"]))
    work = result.copy()
    work["안전최종"] = work.apply(
        lambda r: r["안전"] + adj.get(r["대안"], 0.0), axis=1
    ).clip(0, 10)

    # ── 2단: WTP 환산 → 1단: 제약 평가
    work = apply_wtp(work, wtp)
    cons = ConstraintSet(budget_monthly=float(budget), min_safety=float(min_safety))
    work = evaluate_constraints(work, cons, safety_col="안전최종")

    show = work[["대안", "유형", "월현금지출", "편의환산", "보정월비용",
                 "안전최종", "통과", "탈락사유"]].sort_values(
        ["통과", "보정월비용"], ascending=[False, True])
    st.dataframe(
        show.style.apply(
            lambda row: ["color: #9aa3ad" if not row["통과"] else ""] * len(row),
            axis=1,
        ),
        use_container_width=True, hide_index=True,
    )
    st.caption("탈락 대안은 지우지 않고 사유와 함께 회색으로 남깁니다 — "
               "모델이 왜 그렇게 판단했는지가 그대로 드러나도록.")

    hints = relaxation_hints(work, cons, safety_col="안전최종")
    if hints:
        st.warning("현재 제약을 모두 만족하는 자취 후보가 없습니다.\n\n" +
                   "\n".join(f"- {h}" for h in hints))

    # ── 커트라인 What-if: 절벽 효과를 숨기지 않고 보여주기
    rentals_w = work[work["유형"] != "통학"]
    cuts = [round(c, 1) for c in np.arange(0, 10.01, 0.5)]
    sweep = cutoff_sweep(rentals_w, cuts, cost_col="보정월비용", safety_col="안전최종")

    fig = go.Figure()
    fig.add_trace(go.Bar(x=sweep["커트라인"], y=sweep["후보수"], name="통과 후보 수",
                         marker_color=_BLUE, opacity=0.55, yaxis="y"))
    fig.add_trace(go.Scatter(x=sweep["커트라인"], y=sweep["최저비용"],
                             name="최저 보정월비용 (만원)", mode="lines+markers",
                             line=dict(color=_ORANGE, width=2.5), yaxis="y2"))
    fig.add_vline(x=min_safety, line_dash="dot", line_color=_PURPLE,
                  annotation_text="현재 커트라인", annotation_font_color=_PURPLE)
    fig.update_layout(
        title=dict(text="커트라인 What-if — 안전 기준을 옮기면 무엇이 달라지는가",
                   font=dict(size=15)),
        xaxis=dict(title="안전 커트라인"),
        yaxis=dict(title="후보 수", rangemode="tozero"),
        yaxis2=dict(title="최저 보정월비용(만원)", overlaying="y", side="right",
                    rangemode="tozero", showgrid=False),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        margin=dict(l=10, r=10, t=70, b=10), height=380,
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── 3단: Pareto frontier (보정월비용 × 안전최종)
    passing = rentals_w[rentals_w["통과"]]
    if len(passing) >= 2:
        front = pareto_mask(passing["보정월비용"], passing["안전최종"])
        fig2 = go.Figure()
        dom = passing[~front]
        fro = passing[front].sort_values("보정월비용")
        if not dom.empty:
            fig2.add_trace(go.Scatter(
                x=dom["보정월비용"], y=dom["안전최종"], mode="markers+text",
                text=dom["대안"], textposition="bottom center",
                marker=dict(color=_GRAY, size=10), name="지배당함 (고를 이유 없음)",
                textfont=dict(color=_GRAY, size=10),
            ))
        fig2.add_trace(go.Scatter(
            x=fro["보정월비용"], y=fro["안전최종"], mode="lines+markers+text",
            text=fro["대안"], textposition="top center",
            marker=dict(color=_BLUE, size=12), line=dict(color=_BLUE, dash="dot"),
            name="Pareto frontier (최종 선택은 사용자)",
            textfont=dict(size=10),
        ))
        fig2.update_layout(
            title=dict(text="비용 × 안전 Pareto frontier — 끝까지 합산하지 않는 선택지",
                       font=dict(size=15)),
            xaxis=dict(title="보정월비용 (만원/월, 편의 WTP 반영)"),
            yaxis=dict(title="안전 최종점수"),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
            margin=dict(l=10, r=10, t=70, b=10), height=400,
        )
        st.plotly_chart(fig2, use_container_width=True)
        st.caption("frontier 위의 대안들끼리는 모델이 우열을 가리지 않습니다 — "
                   "'더 싸지만 덜 안전' vs '더 비싸지만 더 안전'의 선택은 "
                   "정량화할 수 없는 가치판단이므로 사용자에게 돌려줍니다.")
