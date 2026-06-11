import math
import html
import os
import pickle
import sys
from datetime import datetime, timedelta
from pathlib import Path

import folium
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from streamlit.runtime.scriptrunner import get_script_run_ctx
from streamlit_folium import st_folium


if get_script_run_ctx() is None:
    print("이 파일은 python app.py가 아니라 Streamlit으로 실행해야 합니다.")
    print("실행 명령:")
    print(r"cd C:\Users\iy579\Desktop\2026-1_산공이_termproject")
    print("streamlit run app.py")
    sys.exit(0)

st.set_page_config(page_title="등교 방식 추천", page_icon="🏫", layout="wide")


def inject_global_styles() -> None:
    st.markdown(
        """
        <style>
            :root {
                --bg: #f4f7fb;
                --surface: #ffffff;
                --surface-soft: #f8fafc;
                --surface-tint: #eef6ff;
                --line: #d8e2ee;
                --line-strong: #b7c8dc;
                --text: #18212f;
                --muted: #637083;
                --primary: #ff4d1f;
                --primary-hover: #e64016;
                --accent: #16a34a;
                --accent-soft: #e8f8ef;
                --primary-soft: #fff0e8;
                --info-soft: #f2f7ff;
                --orange: #ff4d1f;
                --orange-2: #ff7a2f;
                --gold: #ffbd59;
                --green: #22c55e;
                --purple: #8b5cf6;
                --blue: #1495ef;
                --commute: #ff4d1f;
                --rental: #8b5cf6;
                --warning: #8a5a00;
                --warning-soft: #fff6d8;
                --danger: #c2413a;
                --danger-soft: #fde8e6;
            }

            .stApp {
                background:
                    linear-gradient(180deg, #fff3ec 0, #f4f7fb 245px),
                    var(--bg);
                color: var(--text);
            }

            .stApp,
            [data-testid="stAppViewContainer"],
            [data-testid="stHeader"],
            [data-testid="stToolbar"],
            [data-testid="stDecoration"] {
                color-scheme: light;
            }

            [data-testid="stAppViewContainer"] .main .block-container {
                max-width: 1180px;
                padding-top: 2rem;
                padding-bottom: 4rem;
            }

            h1, h2, h3 {
                letter-spacing: 0;
                color: var(--text);
            }

            p, label, span,
            [data-testid="stMarkdownContainer"],
            [data-testid="stWidgetLabel"],
            [data-testid="stWidgetLabel"] p {
                color: var(--text);
            }

            [data-testid="stCaptionContainer"],
            [data-testid="stCaptionContainer"] p,
            .stCaption,
            .stCaption p {
                color: var(--muted) !important;
            }

            h1 {
                font-size: 2.05rem;
                line-height: 1.18;
                margin-bottom: .45rem;
            }

            h2, h3 {
                margin-top: 1.2rem;
            }

            .app-hero {
                padding: 1.4rem 1.55rem;
                border: 1px solid var(--line);
                border-radius: 8px;
                background: rgba(255,255,255,.86);
                box-shadow: 0 14px 38px rgba(25, 43, 70, .08);
                margin-bottom: 1rem;
            }

            .hero-eyebrow {
                color: var(--accent);
                font-size: .78rem;
                font-weight: 760;
                margin-bottom: .28rem;
            }

            .hero-title {
                font-size: 2rem;
                font-weight: 820;
                line-height: 1.18;
                margin: 0;
            }

            .hero-copy {
                color: var(--muted);
                margin-top: .45rem;
                max-width: 760px;
                line-height: 1.55;
            }

            .panel-title {
                font-size: .95rem;
                font-weight: 760;
                color: var(--text);
                margin: .35rem 0 .65rem;
            }

            .weight-row {
                display: flex;
                flex-wrap: wrap;
                gap: .45rem;
                margin: .65rem 0 .1rem;
            }

            .weight-chip {
                border: 1px solid var(--line);
                border-radius: 999px;
                background: var(--surface-tint);
                color: #243449;
                padding: .28rem .58rem;
                font-size: .78rem;
                font-weight: 650;
            }

            .note-card {
                border-left: 4px solid var(--accent);
                border-radius: 8px;
                background: var(--accent-soft);
                padding: .85rem 1rem;
                color: #17443f;
                margin: .8rem 0;
            }

            .decision-callout {
                border: 1px solid var(--line);
                border-left-width: 5px;
                border-radius: 8px;
                padding: .95rem 1.05rem;
                margin: .85rem 0;
                background: var(--surface);
                box-shadow: 0 8px 24px rgba(25, 43, 70, .045);
            }

            .decision-callout__title {
                font-weight: 780;
                color: var(--text);
                margin-bottom: .18rem;
            }

            .decision-callout__body {
                color: var(--text);
                line-height: 1.55;
            }

            .decision-callout--success {
                border-left-color: var(--accent);
                background: var(--accent-soft);
            }

            .decision-callout--info {
                border-left-color: var(--primary);
                background: var(--info-soft);
            }

            .decision-callout--warning {
                border-left-color: var(--warning);
                background: var(--warning-soft);
            }

            .decision-callout--danger {
                border-left-color: var(--danger);
                background: var(--danger-soft);
            }

            .verdict-panel {
                display: grid;
                grid-template-columns: minmax(0, 1fr) auto;
                gap: 1rem;
                align-items: end;
                border: 1px solid var(--line);
                border-left: 6px solid var(--primary);
                border-radius: 8px;
                background: linear-gradient(135deg, #ffffff 0%, #eef6ff 100%);
                padding: 1.2rem 1.25rem;
                margin: .45rem 0 1rem;
                box-shadow: 0 12px 30px rgba(25, 43, 70, .07);
            }

            .verdict-panel--commute {
                border-left-color: var(--commute);
                background: linear-gradient(135deg, #ffffff 0%, #fff3ed 100%);
            }

            .verdict-panel--rental {
                border-left-color: var(--rental);
                background: linear-gradient(135deg, #ffffff 0%, #eef6ff 100%);
            }

            .verdict-kicker {
                color: var(--muted);
                font-size: .78rem;
                font-weight: 760;
                margin-bottom: .25rem;
            }

            .verdict-title {
                color: var(--text);
                font-size: 1.45rem;
                font-weight: 840;
                line-height: 1.25;
            }

            .verdict-meta {
                color: var(--muted);
                margin-top: .35rem;
                line-height: 1.45;
            }

            .verdict-cost {
                color: var(--text);
                text-align: right;
                font-weight: 820;
                font-size: 1.18rem;
                white-space: nowrap;
            }

            .analysis-section {
                margin-top: 1.2rem;
            }

            .analysis-section__eyebrow {
                color: var(--accent);
                font-size: .78rem;
                font-weight: 780;
                margin-bottom: .2rem;
            }

            .analysis-section__title {
                color: var(--text);
                font-size: 1.55rem;
                font-weight: 840;
                line-height: 1.25;
                margin-bottom: .25rem;
            }

            .analysis-section__copy {
                color: var(--muted);
                line-height: 1.5;
                margin-bottom: .8rem;
            }

            .analysis-card-head {
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                gap: .8rem;
                padding: 0 0 .32rem;
            }

            .analysis-eyebrow {
                color: var(--muted);
                font-size: .72rem;
                font-weight: 760;
                letter-spacing: .02em;
                text-transform: uppercase;
                margin-bottom: .16rem;
            }

            .analysis-title {
                color: var(--text);
                font-size: 1rem;
                font-weight: 820;
                line-height: 1.25;
                word-break: keep-all;
            }

            .analysis-chip {
                border: 1px solid #ffd7c4;
                border-radius: 999px;
                background: var(--primary-soft);
                color: #a33b15;
                padding: .14rem .42rem;
                font-size: .72rem;
                font-weight: 720;
                white-space: nowrap;
            }

            .analysis-metric {
                color: var(--text);
                font-size: 1.08rem;
                line-height: 1.2;
                font-weight: 840;
                margin-bottom: .1rem;
                word-break: keep-all;
            }

            .analysis-caption {
                color: var(--muted);
                font-size: .76rem;
                line-height: 1.35;
                min-height: 1.9rem;
                margin-bottom: .15rem;
            }

            div[data-testid="stVerticalBlockBorderWrapper"] {
                border-color: var(--line) !important;
                border-radius: 8px !important;
                background: rgba(255,255,255,.98) !important;
                box-shadow: 0 12px 30px rgba(25, 43, 70, .065);
                transition: border-color .16s ease, box-shadow .16s ease, transform .16s ease;
            }

            div[data-testid="stVerticalBlockBorderWrapper"]:hover {
                border-color: #a7c7ed !important;
                box-shadow: 0 16px 36px rgba(25, 43, 70, .1);
                transform: translateY(-1px);
            }

            .stButton > button {
                min-height: 2.55rem;
                border-radius: 7px;
                border: 1px solid var(--line-strong);
                font-weight: 720;
            }

            .stButton > button[kind="primary"], .stButton > button:hover {
                border-color: var(--primary);
            }

            .stButton > button,
            [data-testid="stBaseButton-secondary"] {
                color: var(--text) !important;
                background: #ffffff !important;
            }

            .stButton > button[kind="primary"],
            [data-testid="stBaseButton-primary"] {
                color: #ffffff !important;
                background: var(--primary) !important;
                border-color: var(--primary) !important;
            }

            .stButton > button[kind="primary"]:hover,
            [data-testid="stBaseButton-primary"]:hover {
                background: var(--primary-hover) !important;
                border-color: var(--primary-hover) !important;
            }

            .stButton > button[kind="primary"] *,
            [data-testid="stBaseButton-primary"] *,
            .stButton > button[kind="primary"] p,
            [data-testid="stBaseButton-primary"] p {
                color: #ffffff !important;
            }

            [data-baseweb="select"] > div {
                background-color: #ffffff !important;
                border-color: var(--line-strong) !important;
                color: var(--text) !important;
            }

            [data-baseweb="select"] *,
            [data-baseweb="popover"] *,
            [role="listbox"] *,
            [role="option"] * {
                color: var(--text) !important;
            }

            [data-baseweb="popover"],
            [role="listbox"],
            [role="option"] {
                background-color: #ffffff !important;
            }

            .stNumberInput input,
            .stTextInput input,
            textarea {
                background-color: #ffffff !important;
                color: var(--text) !important;
                border-color: var(--line-strong) !important;
            }

            .stSlider label,
            .stSlider label p,
            .stSlider [data-testid="stTickBar"],
            .stSlider [data-testid="stThumbValue"],
            .stSlider [data-testid="stThumbValue"] * {
                color: var(--text) !important;
            }

            .stSlider [data-baseweb="slider"] div {
                color: var(--text);
            }

            [data-testid="stMetric"] {
                background: var(--surface);
                border: 1px solid var(--line);
                border-top: 3px solid var(--primary);
                border-radius: 8px;
                padding: .85rem .9rem;
                box-shadow: 0 8px 24px rgba(25, 43, 70, .055);
                min-height: 112px;
            }

            [data-testid="stMetricLabel"] {
                color: var(--muted);
                font-weight: 720;
            }

            [data-testid="stMetricValue"] {
                color: var(--text);
                font-size: 1.35rem;
                line-height: 1.22;
                word-break: keep-all;
            }

            [data-testid="stDataFrame"], [data-testid="stTable"] {
                border: 1px solid var(--line);
                border-radius: 8px;
                overflow: hidden;
                background: var(--surface);
            }

            div[data-testid="stExpander"] {
                border: 1px solid var(--line);
                border-radius: 8px;
                background: var(--surface);
                box-shadow: none;
            }

            [data-testid="stTabs"] button {
                font-weight: 720;
            }

            [data-testid="stTabs"] button p {
                color: var(--muted) !important;
                font-weight: 720;
            }

            [data-testid="stTabs"] button[aria-selected="true"] p {
                color: var(--primary) !important;
            }

            iframe {
                border-radius: 8px;
                border: 1px solid var(--line) !important;
            }

            .stAlert {
                border-radius: 8px;
                border: 1px solid var(--line);
            }

            [data-testid="stAlert"] {
                color: var(--text) !important;
            }

            [data-testid="stAlert"] *,
            [data-testid="stAlert"] p,
            [data-testid="stAlert"] div {
                color: var(--text) !important;
            }

            div[data-testid="stExpander"] details,
            div[data-testid="stExpander"] summary,
            div[data-testid="stExpander"] summary *,
            div[data-testid="stExpander"] [data-testid="stMarkdownContainer"] * {
                color: var(--text) !important;
            }

            [data-testid="stDataFrame"] *,
            [data-testid="stTable"] * {
                color: var(--text);
            }

            @media (max-width: 760px) {
                [data-testid="stAppViewContainer"] .main .block-container {
                    padding-left: 1rem;
                    padding-right: 1rem;
                }

                .app-hero {
                    padding: 1.1rem;
                }

                .hero-title {
                    font-size: 1.55rem;
                }

                .verdict-panel {
                    grid-template-columns: 1fr;
                }

                .verdict-cost {
                    text-align: left;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_callout(kind: str, title: str, body: str) -> None:
    safe_title = html.escape(title)
    safe_body = html.escape(body).replace("\n", "<br>")
    st.markdown(
        f"""
        <div class="decision-callout decision-callout--{kind}">
            <div class="decision-callout__title">{safe_title}</div>
            <div class="decision-callout__body">{safe_body}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_verdict(best: pd.Series) -> None:
    choice_type = str(best["유형"])
    variant = "commute" if choice_type == "통학" else "rental"
    title = (
        "AEC·종합점수 기준으로 통학이 가장 경제적입니다."
        if choice_type == "통학"
        else f"AEC·종합점수 기준으로 {best['대안']} 자취가 가장 경제적입니다."
    )
    meta = (
        f"편도 {best['편도시간']:.0f}분, 월 시간손실 {best['월시간손실비용']:.0f}만원을 포함한 비교입니다."
    )
    st.markdown(
        f"""
        <div class="verdict-panel verdict-panel--{variant}">
            <div>
                <div class="verdict-kicker">추천 결론</div>
                <div class="verdict-title">{html.escape(title)}</div>
                <div class="verdict-meta">{html.escape(meta)}</div>
            </div>
            <div class="verdict-cost">
                월 실질비용<br>{best['월실질비용']:.0f}만원
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def build_cost_comparison_chart(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    chart_df = df.sort_values("월실질비용", ascending=True)
    traces = [
        ("월 현금지출", "월현금지출", "#ff4d1f"),
        ("월 시간손실", "월시간손실비용", "#8b5cf6"),
        ("월 실질비용", "월실질비용", "#22c55e"),
    ]
    for label, column, color in traces:
        fig.add_trace(
            go.Bar(
                x=chart_df["대안"],
                y=chart_df[column],
                name=label,
                marker_color=color,
                hovertemplate="%{x}<br>" + label + " %{y:.0f}만원<extra></extra>",
            )
        )
    fig.update_layout(
        template="plotly_white",
        barmode="group",
        height=420,
        margin=dict(l=10, r=10, t=46, b=80),
        title=dict(text="월 비용 구조", font=dict(size=15, color="#18212f")),
        font=dict(color="#18212f"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
    )
    fig.update_xaxes(tickangle=-18, tickfont=dict(color="#637083"), gridcolor="#d8e2ee")
    fig.update_yaxes(title="만원/월", tickfont=dict(color="#637083"), gridcolor="#d8e2ee")
    return fig


CHART_ORANGE = "#ff4d1f"
CHART_ORANGE_2 = "#ff7a2f"
CHART_GOLD = "#ffbd59"
CHART_GREEN = "#22c55e"
CHART_PURPLE = "#8b5cf6"
CHART_BLUE = "#1495ef"
CHART_GRID = "#edf1f5"
CHART_TEXT = "#18212f"
CHART_MUTED = "#637083"


def _apply_card_chart_layout(fig: go.Figure, height: int = 130, showlegend: bool = False) -> go.Figure:
    fig.update_layout(
        template="plotly_white",
        height=height,
        margin=dict(l=2, r=2, t=4, b=18),
        font=dict(color=CHART_TEXT, size=10),
        showlegend=showlegend,
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        bargap=0.28,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            x=0,
            font=dict(size=9, color=CHART_MUTED),
        ),
    )
    fig.update_xaxes(
        color=CHART_MUTED,
        fixedrange=True,
        tickfont=dict(color=CHART_MUTED, size=9),
        title_font=dict(color=CHART_TEXT, size=9),
        gridcolor=CHART_GRID,
        linecolor="#d8e2ee",
        zerolinecolor="#d8e2ee",
    )
    fig.update_yaxes(
        color=CHART_MUTED,
        fixedrange=True,
        tickfont=dict(color=CHART_MUTED, size=9),
        title_font=dict(color=CHART_TEXT, size=9),
        gridcolor=CHART_GRID,
        linecolor="#d8e2ee",
        zerolinecolor="#d8e2ee",
    )
    return fig


def render_analysis_card(
    eyebrow: str,
    title: str,
    chip: str,
    metric: str,
    caption: str,
    fig: go.Figure,
    key: str,
) -> bool:
    with st.container(border=True):
        st.markdown(
            f"""
            <div class="analysis-card-head">
                <div>
                    <div class="analysis-eyebrow">{html.escape(eyebrow)}</div>
                    <div class="analysis-title">{html.escape(title)}</div>
                </div>
                <div class="analysis-chip">{html.escape(chip)}</div>
            </div>
            <div class="analysis-metric">{html.escape(metric)}</div>
            <div class="analysis-caption">{html.escape(caption)}</div>
            """,
            unsafe_allow_html=True,
        )
        st.plotly_chart(
            fig,
            width="stretch",
            theme=None,
            key=f"{key}_chart",
            config={"displayModeBar": False},
        )
        return st.button("자세히 보기", width="stretch", key=f"{key}_button")


def build_econ_mini_chart(commute_row: pd.Series, best_economic_rental: pd.Series) -> go.Figure:
    labels = ["통학", "최저 자취"]
    values = [float(commute_row["AEC"]), float(best_economic_rental["AEC"])]
    colors = [CHART_ORANGE, CHART_PURPLE]
    fig = go.Figure(
        go.Bar(
            x=labels,
            y=values,
            marker_color=colors,
            marker_line=dict(color="#ffffff", width=1),
            text=[f"{value:.0f}" for value in values],
            textposition="auto",
            textfont=dict(color=CHART_TEXT, size=10),
            hovertemplate="%{x}<br>AEC %{y:.0f}만원/년<extra></extra>",
        )
    )
    fig.update_yaxes(title="", rangemode="tozero")
    fig.update_xaxes(title="")
    return _apply_card_chart_layout(fig)


def build_table_mini_chart(df: pd.DataFrame) -> go.Figure:
    chart_df = df.sort_values("월실질비용").head(5).reset_index(drop=True)
    chart_df = chart_df.iloc[::-1]
    palette = [CHART_BLUE, CHART_PURPLE, CHART_GOLD, CHART_ORANGE_2, CHART_ORANGE]
    labels = chart_df["대안"].astype(str).str.slice(0, 9)
    fig = go.Figure(
        go.Bar(
            x=chart_df["월실질비용"],
            y=labels,
            orientation="h",
            marker_color=palette[: len(chart_df)],
            marker_line=dict(color="#ffffff", width=1),
            text=[f"{value:.0f}" for value in chart_df["월실질비용"]],
            textposition="outside",
            textfont=dict(color=CHART_TEXT, size=9),
            customdata=chart_df["대안"],
            hovertemplate="%{customdata}<br>월 실질비용 %{x:.0f}만원<extra></extra>",
        )
    )
    fig.update_xaxes(title="", rangemode="tozero", showticklabels=False)
    fig.update_yaxes(title="")
    return _apply_card_chart_layout(fig)


def _params_from_assumptions_for_card(assumptions: dict):
    from model import Params

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


def build_boundary_mini_chart(
    commute_row: pd.Series,
    best_economic_rental: pd.Series,
    assumptions: dict,
) -> go.Figure:
    from model import decision_boundary, rental_from_v1_row

    p = _params_from_assumptions_for_card(assumptions)
    rental = rental_from_v1_row(best_economic_rental)
    line = decision_boundary(rental, p)
    m_now = float(commute_row["편도시간"])
    m_hi = max(90.0, m_now * 1.45)
    x = [0.0, m_hi]
    y = [max(0.0, line.rent_at(x[0])), max(0.0, line.rent_at(x[1]))]
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=x,
            y=y,
            mode="lines",
            line=dict(color=CHART_ORANGE, width=4),
            name="결정 경계",
            hovertemplate="편도 %{x:.0f}분<br>손익분기 월세 %{y:.0f}만원<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[m_now],
            y=[float(best_economic_rental["월세"])],
            mode="markers",
            marker=dict(size=14, color=CHART_GOLD, line=dict(width=2, color="#7a4b00")),
            name="현재 조건",
            hovertemplate="현재 통학 %{x:.0f}분<br>월세 %{y:.0f}만원<extra></extra>",
        )
    )
    fig.update_xaxes(title="", showticklabels=True)
    fig.update_yaxes(title="", rangemode="tozero")
    return _apply_card_chart_layout(fig, showlegend=False)


def build_value_mini_chart(df: pd.DataFrame, best: pd.Series) -> go.Figure:
    chart_df = df.copy()
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=chart_df["월실질비용"],
            y=chart_df["안전"],
            mode="markers",
            marker=dict(
                size=(chart_df["편의도"] * 3.8 + 10),
                color=chart_df["편의도"],
                colorscale=[[0, CHART_ORANGE], [0.48, CHART_GOLD], [1, CHART_GREEN]],
                line=dict(width=1, color="#ffffff"),
                showscale=False,
            ),
            text=chart_df["대안"],
            hovertemplate="%{text}<br>월 실질비용 %{x:.0f}만원<br>안전 %{y:.1f}<extra></extra>",
            name="대안",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[float(best["월실질비용"])],
            y=[float(best["안전"])],
            mode="markers",
            marker=dict(size=18, color=CHART_PURPLE, symbol="star", line=dict(width=1, color="#ffffff")),
            text=[str(best["대안"])],
            hovertemplate="추천: %{text}<br>월 실질비용 %{x:.0f}만원<br>안전 %{y:.1f}<extra></extra>",
            name="추천",
        )
    )
    fig.update_xaxes(title="", rangemode="tozero")
    fig.update_yaxes(title="", range=[0, 10.5])
    return _apply_card_chart_layout(fig, showlegend=False)


def estimate_mc_snapshot(
    commute_row: pd.Series,
    best_economic_rental: pd.Series,
    assumptions: dict,
) -> dict:
    from model import rental_from_v1_row
    from simulate import MCInputs, run_mc

    p = _params_from_assumptions_for_card(assumptions)
    rental = rental_from_v1_row(best_economic_rental)
    m_mode = float(commute_row["편도시간"])
    days = float(assumptions["school_days_per_month"])
    wage = float(assumptions["hourly_time_value_won"])
    mc = MCInputs(
        commute_tri=(max(5.0, m_mode * 0.85), m_mode, min(999.0, m_mode * 1.5)),
        wage_range=(wage, wage * 1.6),
        days_range=(max(10.0, days - 3), min(26.0, days + 1)),
        rate_range=(p.annual_interest_rate, p.annual_interest_rate),
        n=2500,
        seed=17,
    )
    return run_mc(rental, mc, p)


def build_mc_mini_chart(snapshot: dict) -> go.Figure:
    save = snapshot["save"]
    fig = go.Figure()
    fig.add_trace(
        go.Histogram(
            x=save[save <= 0],
            nbinsx=24,
            name="통학 유리",
            marker_color=CHART_ORANGE,
            opacity=0.75,
        )
    )
    fig.add_trace(
        go.Histogram(
            x=save[save > 0],
            nbinsx=24,
            name="자취 유리",
            marker_color=CHART_PURPLE,
            opacity=0.75,
        )
    )
    fig.add_vline(x=0, line_color=CHART_TEXT, line_width=1)
    fig.update_xaxes(title="", showticklabels=False)
    fig.update_yaxes(title="", showticklabels=False)
    return _apply_card_chart_layout(fig, showlegend=True)


def render_economic_detail(
    commute_row: pd.Series,
    best_economic_rental: pd.Series,
) -> None:
    st.subheader("경제성 공학 비교")
    econ1, econ2, econ3 = st.columns(3)
    econ1.metric("통학 AEC", f"{commute_row['AEC']:.0f}만원/년")
    econ2.metric("최저 자취 AEC", f"{best_economic_rental['AEC']:.0f}만원/년")
    econ3.metric("AEC 차이", f"{best_economic_rental['AEC'] - commute_row['AEC']:.0f}만원/년")

    st.caption(
        f"시간손실비용 = 편도시간 x 2(왕복) x 월 {ASSUMPTIONS['school_days_per_month']}일 "
        f"x 시간가치 {ASSUMPTIONS['hourly_time_value_won']:,}원 / 60. "
        "NPV/AEC에도 이 시간손실비용을 포함합니다."
    )
    st.plotly_chart(build_econ_mini_chart(commute_row, best_economic_rental), width="stretch", theme=None)

    break_even = best_economic_rental["손익분기월세"]
    if pd.isna(break_even):
        render_callout(
            "warning",
            "손익분기 미도달",
            f"{best_economic_rental['대안']}은 월세가 0만원이어도 통학보다 경제적으로 불리합니다.",
        )
    elif best_economic_rental["월세"] <= break_even:
        render_callout(
            "info",
            "손익분기 월세",
            f"{best_economic_rental['대안']}의 월세는 {best_economic_rental['월세']:.0f}만원이고, "
            f"통학과 같아지는 손익분기 월세는 약 {break_even:.0f}만원입니다. 현재 월세에서는 자취가 경제적으로 유리합니다.",
        )
    else:
        render_callout(
            "info",
            "손익분기 월세",
            f"{best_economic_rental['대안']}의 월세는 {best_economic_rental['월세']:.0f}만원이고, "
            f"통학과 같아지는 손익분기 월세는 약 {break_even:.0f}만원입니다. 월세가 이 이하일 때 자취가 경제적으로 유리합니다.",
        )


def render_table_detail(result: pd.DataFrame, best: pd.Series) -> None:
    summary_cols = [
        "대안",
        "유형",
        "경제성판정",
        "월현금지출",
        "월시간손실비용",
        "월실질비용",
        "편도시간",
        "AEC",
        "종합점수",
    ]
    display_cols = [
        "대안",
        "유형",
        "경제성판정",
        "월현금지출",
        "월시간손실비용",
        "월실질비용",
        "편도시간",
        "시간출처",
        "보증금",
        "월세",
        "손익분기월세",
        "관리비",
        "기타생활비",
        "월교통비",
        "택시비참고",
        "연간시간비용",
        "4년NPV",
        "AEC",
        "통학대비AEC차이",
        "경제성점수",
        "시간점수",
        "편의점수",
        "안전점수",
        "종합점수",
    ]
    number_formats = {
        "월현금지출": "{:.0f}",
        "월시간손실비용": "{:.0f}",
        "월실질비용": "{:.0f}",
        "편도시간": "{:.0f}",
        "보증금": "{:.0f}",
        "월세": "{:.0f}",
        "손익분기월세": lambda value: "-" if pd.isna(value) else f"{value:.0f}",
        "관리비": "{:.0f}",
        "기타생활비": "{:.0f}",
        "월교통비": "{:.0f}",
        "택시비참고": lambda value: "-" if pd.isna(value) else f"{value:,.0f}원",
        "연간시간비용": "{:.0f}",
        "4년NPV": "{:.0f}",
        "AEC": "{:.0f}",
        "통학대비AEC차이": "{:.0f}",
        "경제성점수": "{:.3f}",
        "시간점수": "{:.3f}",
        "편의점수": "{:.3f}",
        "안전점수": "{:.3f}",
        "종합점수": "{:.3f}",
    }

    def highlight_best(row):
        if row["대안"] == best["대안"]:
            return ["background-color: #eef6ff; font-weight: 700"] * len(row)
        return [""] * len(row)

    st.subheader("대안별 비용 비교")
    st.plotly_chart(build_cost_comparison_chart(result), width="stretch", theme=None)
    st.dataframe(
        result[summary_cols].style.apply(highlight_best, axis=1).format(number_formats),
        width="stretch",
        hide_index=True,
    )
    with st.expander("상세 계산 항목 보기"):
        st.dataframe(
            result[display_cols].style.apply(highlight_best, axis=1).format(number_formats),
            width="stretch",
            hide_index=True,
        )


BASE_DIR = Path(__file__).parent
RENTAL_CSV = BASE_DIR / "rentals_dummy.csv"
GTFS_CACHE = BASE_DIR / "gtfs_seoul_cache.pkl"
DEFAULT_KAKAO_REST_API_KEY = ""

SCHOOL = {
    "name": "서울대학교 산업공학과",
    "lat": 37.459992,
    "lng": 126.953181,
}

# 금액 단위: 만원
ASSUMPTIONS = {
    "analysis_years": 4,
    "annual_interest_rate": 0.05,
    "school_days_per_month": 22,
    "hourly_time_value_won": 25000,
    "moving_cost": 60,
    "commute_base_transport": 8,
    "living_food": 32,
    "commute_food_extra": 8,
    "living_utility_extra": 8,
    "living_internet": 3,
    "living_supply": 5,
}

AHP_PRESETS = {
    "비용 중시형": {"economic": 0.65, "time": 0.18, "convenience": 0.10, "safety": 0.07},
    "균형형": {"economic": 0.40, "time": 0.25, "convenience": 0.22, "safety": 0.13},
    "편의 중시형": {"economic": 0.25, "time": 0.22, "convenience": 0.38, "safety": 0.15},
    "시간 중시형": {"economic": 0.30, "time": 0.45, "convenience": 0.15, "safety": 0.10},
    "안전 중시형": {"economic": 0.30, "time": 0.20, "convenience": 0.15, "safety": 0.35},
}


def init_state() -> None:
    defaults = {
        "search_results": [],
        "selected_home": None,
        "last_query": "",
        "analysis_done": False,
        "page": "input",
        "decision_weights": None,
        "results_nav_tab": "Overview",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def get_kakao_key() -> str | None:
    try:
        return st.secrets["KAKAO_API_KEY"]
    except Exception:
        return os.getenv("KAKAO_API_KEY") or DEFAULT_KAKAO_REST_API_KEY


def query_variants(query: str) -> list[str]:
    stripped = " ".join(query.strip().split())
    variants = [stripped, stripped.replace(" ", "")]
    if not stripped.endswith("아파트"):
        variants.append(f"{stripped} 아파트")
    if not stripped.startswith("서울"):
        variants.append(f"서울 {stripped}")
    deduped = []
    for variant in variants:
        if variant and variant not in deduped:
            deduped.append(variant)
    return deduped


def kakao_get(url: str, params: dict) -> dict:
    api_key = get_kakao_key()
    if not api_key:
        return {}
    headers = {"Authorization": f"KakaoAK {api_key}"}
    try:
        response = requests.get(url, headers=headers, params=params, timeout=8)
        if response.status_code == 200:
            return response.json()
    except requests.RequestException:
        return {}
    return {}


@st.cache_data(ttl=3600, show_spinner=False)
def cached_search_places(query: str) -> list[dict]:
    return search_places(query)


def search_places(query: str) -> list[dict]:
    places = []
    address_url = "https://dapi.kakao.com/v2/local/search/address.json"
    keyword_url = "https://dapi.kakao.com/v2/local/search/keyword.json"

    for variant in query_variants(query):
        address_data = kakao_get(address_url, {"query": variant, "size": 10})
        for item in address_data.get("documents", []):
            road = item.get("road_address") or {}
            places.append(
                {
                    "name": road.get("building_name") or item.get("address_name") or variant,
                    "address": item.get("address_name") or road.get("address_name") or variant,
                    "lat": float(item["y"]),
                    "lng": float(item["x"]),
                    "source": "주소",
                    "query": variant,
                }
            )

        keyword_data = kakao_get(keyword_url, {"query": variant, "size": 10})
        for item in keyword_data.get("documents", []):
            places.append(
                {
                    "name": item.get("place_name") or variant,
                    "address": item.get("road_address_name") or item.get("address_name") or variant,
                    "lat": float(item["y"]),
                    "lng": float(item["x"]),
                    "source": "장소",
                    "query": variant,
                }
            )

    deduped = []
    seen = set()
    for place in places:
        key = (round(place["lat"], 6), round(place["lng"], 6))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(place)
    return deduped


def reverse_geocode(lat: float, lng: float) -> dict:
    url = "https://dapi.kakao.com/v2/local/geo/coord2address.json"
    data = kakao_get(url, {"x": lng, "y": lat})
    documents = data.get("documents", [])
    if not documents:
        return {
            "name": f"지도 선택 위치 ({lat:.5f}, {lng:.5f})",
            "address": f"{lat:.5f}, {lng:.5f}",
            "lat": lat,
            "lng": lng,
            "source": "지도",
            "query": "map_click",
        }
    item = documents[0]
    road = item.get("road_address") or {}
    address = item.get("address") or {}
    address_name = road.get("address_name") or address.get("address_name") or f"{lat:.5f}, {lng:.5f}"
    return {
        "name": road.get("building_name") or address_name,
        "address": address_name,
        "lat": lat,
        "lng": lng,
        "source": "지도",
        "query": "map_click",
    }


def next_monday_0930() -> str:
    now = datetime.now()
    days_until_monday = (7 - now.weekday()) % 7
    target = (now + timedelta(days=days_until_monday)).replace(
        hour=9, minute=30, second=0, microsecond=0
    )
    if target <= now:
        target += timedelta(days=7)
    return target.strftime("%Y%m%d%H%M")


def kakao_driving_route(origin: dict, destination: dict) -> dict | None:
    origin_param = f"{origin['lng']},{origin['lat']},name={origin['name']}"
    destination_param = f"{destination['lng']},{destination['lat']},name={destination['name']}"

    future_url = "https://apis-navi.kakaomobility.com/affiliate/v1/future/directions"
    future_data = kakao_get(
        future_url,
        {
            "origin": origin_param,
            "destination": destination_param,
            "departure_time": next_monday_0930(),
            "priority": "RECOMMEND",
            "summary": "true",
        },
    )
    future_route = parse_kakao_route(future_data, "카카오 미래 자동차 길찾기")
    if future_route:
        return future_route

    current_url = "https://apis-navi.kakaomobility.com/v1/directions"
    current_data = kakao_get(
        current_url,
        {
            "origin": origin_param,
            "destination": destination_param,
            "priority": "RECOMMEND",
            "summary": "true",
        },
    )
    return parse_kakao_route(current_data, "카카오 현재 자동차 길찾기")


def parse_kakao_route(data: dict, source: str) -> dict | None:
    routes = data.get("routes") or []
    if not routes:
        return None
    summary = routes[0].get("summary") or {}
    if "duration" not in summary:
        return None
    fare = summary.get("fare") or {}
    drive_minutes = max(1, round(summary["duration"] / 60))
    distance_km = summary.get("distance", 0) / 1000
    return {
        "source": source,
        "drive_minutes": drive_minutes,
        "distance_km": distance_km,
        "taxi_fare_won": fare.get("taxi"),
        "toll_won": fare.get("toll"),
    }


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlng / 2) ** 2
    )
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


@st.cache_resource(show_spinner=False)
def load_gtfs_cache() -> dict | None:
    if not GTFS_CACHE.exists():
        return None
    with GTFS_CACHE.open("rb") as file:
        return pickle.load(file)


def nearest_stops(cache: dict, lat: float, lng: float, limit: int = 8, radius_km: float = 1.2) -> list[dict]:
    candidates = []
    for stop in cache["stops"]:
        distance = haversine_km(lat, lng, stop["stop_lat"], stop["stop_lon"])
        if distance <= radius_km:
            candidates.append({**stop, "walk_km": distance})
    return sorted(candidates, key=lambda item: item["walk_km"])[:limit]


def gtfs_transit_route(origin: dict, destination: dict) -> dict | None:
    cache = load_gtfs_cache()
    if not cache:
        return None

    origin_stops = nearest_stops(cache, origin["lat"], origin["lng"])
    dest_stops = nearest_stops(cache, destination["lat"], destination["lng"])
    if not origin_stops or not dest_stops:
        return None

    graph = cache["graph"]
    walk_speed_mps = cache.get("walk_speed_mps", 1.2)
    transfer_penalty_s = cache.get("transfer_penalty_s", 300)
    dest_ids = {stop["stop_id"] for stop in dest_stops}
    dest_lookup = {stop["stop_id"]: stop for stop in dest_stops}

    import heapq

    heap = []
    best = {}
    previous = {}
    start_marker = "__origin__"

    for stop in origin_stops:
        walk_s = stop["walk_km"] * 1000 / walk_speed_mps
        heapq.heappush(heap, (walk_s, stop["stop_id"]))
        best[stop["stop_id"]] = walk_s
        previous[stop["stop_id"]] = (start_marker, f"도보 {stop['walk_km']:.2f}km")

    found_id = None
    while heap:
        current_cost, node = heapq.heappop(heap)
        if current_cost > best.get(node, float("inf")):
            continue
        if node in dest_ids:
            found_id = node
            break
        for nxt, ride_s in graph.get(node, {}).items():
            new_cost = current_cost + ride_s + transfer_penalty_s
            if new_cost < best.get(nxt, float("inf")):
                best[nxt] = new_cost
                previous[nxt] = (node, "대중교통")
                heapq.heappush(heap, (new_cost, nxt))

    if found_id is None:
        return None

    dest_stop = dest_lookup[found_id]
    final_walk_s = dest_stop["walk_km"] * 1000 / walk_speed_mps
    total_s = best[found_id] + final_walk_s

    stop_names = {stop["stop_id"]: stop["stop_name"] for stop in cache["stops"]}
    path = []
    cursor = found_id
    while cursor in previous:
        path.append(stop_names.get(cursor, cursor))
        prev, _ = previous[cursor]
        if prev == start_marker:
            break
        cursor = prev
    path.reverse()

    return {
        "source": "GTFS 대중교통 네트워크 최단시간",
        "minutes": max(1, round(total_s / 60)),
        "access_stop": origin_stops[0]["stop_name"],
        "egress_stop": dest_stop["stop_name"],
        "path_preview": " -> ".join(path[:8]),
    }


def estimate_commute_minutes(distance_km: float, mode: str = "transit") -> int:
    if mode == "walk":
        return max(8, round(distance_km / 4.5 * 60))
    if mode == "bus":
        return max(12, round(distance_km / 16 * 60 + 12))
    return max(20, round(distance_km / 22 * 60 + 18))


def annual_time_cost(one_way_minutes: float, hourly_time_value_won: float) -> float:
    annual_hours = (
        one_way_minutes
        * 2
        * ASSUMPTIONS["school_days_per_month"]
        * 12
        / 60
    )
    return annual_hours * hourly_time_value_won / 10000


def monthly_time_cost(one_way_minutes: float, hourly_time_value_won: float) -> float:
    monthly_hours = one_way_minutes * 2 * ASSUMPTIONS["school_days_per_month"] / 60
    return monthly_hours * hourly_time_value_won / 10000


def present_value_factor(rate: float, year: int) -> float:
    return 1 / ((1 + rate) ** year)


def capital_recovery_factor(rate: float, years: int) -> float:
    if rate == 0:
        return 1 / years
    return rate * (1 + rate) ** years / ((1 + rate) ** years - 1)


def economic_metrics(
    deposit: float,
    initial_extra: float,
    monthly_cost: float,
    one_way_minutes: float,
    rate: float,
    hourly_time_value_won: float,
) -> dict:
    years = ASSUMPTIONS["analysis_years"]
    initial_cost = deposit + initial_extra
    annual_operating = monthly_cost * 12
    annual_opportunity = annual_time_cost(one_way_minutes, hourly_time_value_won)
    monthly_opportunity = annual_opportunity / 12
    annual_total = annual_operating + annual_opportunity
    pv_annual_cost = sum(
        annual_total * present_value_factor(rate, year)
        for year in range(1, years + 1)
    )
    pv_residual = deposit * present_value_factor(rate, years)
    npv = initial_cost + pv_annual_cost - pv_residual
    aec = npv * capital_recovery_factor(rate, years)
    return {
        "초기비용": initial_cost,
        "월비용": monthly_cost,
        "월시간손실비용": monthly_opportunity,
        "월실질비용": monthly_cost + monthly_opportunity,
        "연간시간비용": annual_opportunity,
        "4년NPV": npv,
        "AEC": aec,
    }


def break_even_rent(
    commute_aec: float,
    deposit: float,
    fixed_monthly_without_rent: float,
    one_way_minutes: float,
    rate: float,
    hourly_time_value_won: float,
) -> float | None:
    zero_rent_aec = economic_metrics(
        deposit,
        ASSUMPTIONS["moving_cost"],
        fixed_monthly_without_rent,
        one_way_minutes,
        rate,
        hourly_time_value_won,
    )["AEC"]
    if zero_rent_aec > commute_aec:
        return None

    low, high = 0.0, 300.0
    for _ in range(45):
        mid = (low + high) / 2
        mid_aec = economic_metrics(
            deposit,
            ASSUMPTIONS["moving_cost"],
            fixed_monthly_without_rent + mid,
            one_way_minutes,
            rate,
            hourly_time_value_won,
        )["AEC"]
        if mid_aec <= commute_aec:
            low = mid
        else:
            high = mid
    return low


def score_lower_is_better(value: float, low: float, high: float) -> float:
    if high == low:
        return 0.5
    return max(0, min(1, 1 - (value - low) / (high - low)))


def score_higher_is_better(value: float, low: float, high: float) -> float:
    if high == low:
        return 0.5
    return max(0, min(1, (value - low) / (high - low)))


def read_rentals() -> pd.DataFrame:
    if not RENTAL_CSV.exists():
        st.error("rentals_dummy.csv 파일이 없습니다. 같은 폴더에 매물 CSV를 넣어주세요.")
        st.stop()
    return pd.read_csv(RENTAL_CSV)


def normalize_weights(weights: dict) -> dict:
    total = sum(weights.values())
    if total <= 0:
        return AHP_PRESETS["균형형"]
    return {key: value / total for key, value in weights.items()}


def build_alternatives(
    home: dict,
    rate: float,
    hourly_time_value_won: float,
    weights: dict,
    rent_delta: float = 0,
) -> pd.DataFrame:
    rentals = read_rentals()
    transit_route = gtfs_transit_route(home, SCHOOL)
    if transit_route:
        commute_distance = haversine_km(home["lat"], home["lng"], SCHOOL["lat"], SCHOOL["lng"])
        commute_minutes = transit_route["minutes"]
        route_source = transit_route["source"]
        taxi_fare_won = None
    else:
        route = kakao_driving_route(home, SCHOOL)
    if not transit_route and route:
        commute_distance = route["distance_km"]
        # 카카오맵 대중교통 API는 공식 REST로 제공되지 않아 자동차 길찾기를 기준으로
        # 대중교통 환승/대기 시간을 보수적으로 보정한다.
        commute_minutes = round(route["drive_minutes"] * 1.35 + 10)
        route_source = f"{route['source']} 보정"
        taxi_fare_won = route["taxi_fare_won"]
    elif not transit_route:
        commute_distance = haversine_km(home["lat"], home["lng"], SCHOOL["lat"], SCHOOL["lng"])
        commute_minutes = estimate_commute_minutes(commute_distance)
        route_source = "거리 기반 추정"
        taxi_fare_won = None
    commute_monthly = ASSUMPTIONS["commute_base_transport"] + ASSUMPTIONS["commute_food_extra"]

    rows = [
        {
            "대안": f"{home['name']} 통학",
            "유형": "통학",
            "보증금": 0,
            "월세": 0,
            "관리비": 0,
            "기타생활비": ASSUMPTIONS["commute_food_extra"],
            "월교통비": ASSUMPTIONS["commute_base_transport"],
            "월총비용": commute_monthly,
            "편도시간": commute_minutes,
            "거리km": commute_distance,
            "시간출처": route_source,
            "택시비참고": taxi_fare_won,
            "편의도": 4,
            "안전": 8,
            **economic_metrics(0, 0, commute_monthly, commute_minutes, rate, hourly_time_value_won),
        }
    ]

    for _, rental in rentals.iterrows():
        distance = haversine_km(
            float(rental["lat"]),
            float(rental["lng"]),
            SCHOOL["lat"],
            SCHOOL["lng"],
        )
        mode = "walk" if distance <= 1.5 else "bus"
        minutes = estimate_commute_minutes(distance, mode=mode)
        monthly_rent = max(0, float(rental["monthly_rent"]) + rent_delta)
        transport = float(rental["monthly_transport"])
        other_living = (
            ASSUMPTIONS["living_food"]
            + ASSUMPTIONS["living_utility_extra"]
            + ASSUMPTIONS["living_internet"]
            + ASSUMPTIONS["living_supply"]
        )
        monthly_cost = monthly_rent + float(rental["maintenance_fee"]) + other_living + transport
        rows.append(
            {
                "대안": rental["name"],
                "유형": "자취",
                "보증금": float(rental["deposit"]),
                "월세": monthly_rent,
                "관리비": float(rental["maintenance_fee"]),
                "기타생활비": other_living,
                "월교통비": transport,
                "월총비용": monthly_cost,
                "편도시간": minutes,
                "거리km": distance,
                "시간출처": "학교까지 거리 기반 추정",
                "택시비참고": None,
                "편의도": float(rental["convenience"]),
                "안전": float(rental["safety"]),
                **economic_metrics(
                    float(rental["deposit"]),
                    ASSUMPTIONS["moving_cost"],
                    monthly_cost,
                    minutes,
                    rate,
                    hourly_time_value_won,
                ),
            }
        )

    df = pd.DataFrame(rows)
    df["월현금지출"] = df["월총비용"]
    commute_aec = float(df.loc[df["유형"] == "통학", "AEC"].iloc[0])
    df["통학대비AEC차이"] = df["AEC"] - commute_aec
    df["경제성판정"] = df["통학대비AEC차이"].apply(
        lambda value: "통학보다 유리" if value < 0 else "통학보다 불리"
    )
    df.loc[df["유형"] == "통학", "경제성판정"] = "기준 대안"

    df["손익분기월세"] = None
    for idx, row in df[df["유형"] == "자취"].iterrows():
        fixed_monthly = float(row["월총비용"] - row["월세"])
        df.at[idx, "손익분기월세"] = break_even_rent(
            commute_aec,
            float(row["보증금"]),
            fixed_monthly,
            float(row["편도시간"]),
            rate,
            hourly_time_value_won,
        )

    min_aec, max_aec = df["AEC"].min(), df["AEC"].max()
    min_time, max_time = df["편도시간"].min(), df["편도시간"].max()
    min_conv, max_conv = df["편의도"].min(), df["편의도"].max()
    min_safe, max_safe = df["안전"].min(), df["안전"].max()

    df["경제성점수"] = df["AEC"].apply(lambda value: score_lower_is_better(value, min_aec, max_aec))
    df["시간점수"] = df["편도시간"].apply(lambda value: score_lower_is_better(value, min_time, max_time))
    df["편의점수"] = df["편의도"].apply(lambda value: score_higher_is_better(value, min_conv, max_conv))
    df["안전점수"] = df["안전"].apply(lambda value: score_higher_is_better(value, min_safe, max_safe))
    weights = normalize_weights(weights)
    df["종합점수"] = (
        df["경제성점수"] * weights["economic"]
        + df["시간점수"] * weights["time"]
        + df["편의점수"] * weights["convenience"]
        + df["안전점수"] * weights["safety"]
    )
    return df.sort_values("종합점수", ascending=False)


def render_location_map(home: dict | None) -> None:
    center = [home["lat"], home["lng"]] if home else [SCHOOL["lat"], SCHOOL["lng"]]
    zoom = 15 if home else 13
    m = folium.Map(location=center, zoom_start=zoom)
    folium.Marker(
        [SCHOOL["lat"], SCHOOL["lng"]],
        popup=SCHOOL["name"],
        tooltip=SCHOOL["name"],
        icon=folium.Icon(color="red", icon="graduation-cap", prefix="fa"),
    ).add_to(m)
    if home:
        folium.Marker(
            [home["lat"], home["lng"]],
            popup=f"{home['name']}<br>{home['address']}",
            tooltip="선택한 현 거주지",
            icon=folium.Icon(color="blue", icon="home", prefix="fa"),
        ).add_to(m)
    clicked = st_folium(m, width=900, height=420, returned_objects=["last_clicked"])
    if clicked and clicked.get("last_clicked"):
        lat = clicked["last_clicked"]["lat"]
        lng = clicked["last_clicked"]["lng"]
        st.session_state.selected_home = reverse_geocode(lat, lng)
        st.session_state.analysis_done = False
        st.rerun()


# 민감도 분석 함수 — 비활성화됨; 아래 주석을 해제하면 복구
# def sensitivity_analysis(home: dict, weights: dict) -> pd.DataFrame:
#     rows = []
#     for rent_delta in [-20, -10, 0, 10, 20]:
#         for rate_pct in [3, 5, 7, 9]:
#             for time_multiplier in [0.7, 1.0, 1.3, 1.6]:
#                 df = build_alternatives(
#                     home,
#                     rate_pct / 100,
#                     ASSUMPTIONS["hourly_time_value_won"] * time_multiplier,
#                     weights,
#                     rent_delta=rent_delta,
#                 )
#                 best = df.iloc[0]
#                 rows.append(
#                     {
#                         "월세변화": rent_delta,
#                         "금리(%)": rate_pct,
#                         "시간가치배율": time_multiplier,
#                         "추천유형": best["유형"],
#                         "추천대안": best["대안"],
#                         "추천AEC": best["AEC"],
#                     }
#                 )
#     return pd.DataFrame(rows)


init_state()
inject_global_styles()

# ── 입력 페이지 ───────────────────────────────────────────────────────────────
if st.session_state.page == "input":
    st.markdown(
        """
        <div class="app-hero">
            <div class="hero-eyebrow">경제성공학 기반 의사결정</div>
            <div class="hero-title">통학과 자취, 같은 기준으로 비교하기</div>
            <div class="hero-copy">
                현재 거주지를 기준으로 AEC, NPV, 시간 기회비용, 편의성, 안전성을 한 번에 비교합니다.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    control_col, map_col = st.columns([0.95, 1.35], gap="large")

    with control_col:
        st.markdown('<div class="panel-title">1. 현재 거주지</div>', unsafe_allow_html=True)
        query = st.text_input(
            "주소 또는 장소명",
            placeholder="예: 대치현대 아파트, 안양역, 경기도 안양시 동안구 관양동",
        )

        if query.strip() and query != st.session_state.last_query:
            st.session_state.search_results = cached_search_places(query)
            st.session_state.last_query = query
            if st.session_state.search_results:
                st.session_state.selected_home = st.session_state.search_results[0]

        search_col, clear_col = st.columns([3, 1])
        with search_col:
            if st.button("주소 검색", width="stretch", type="primary"):
                st.session_state.search_results = cached_search_places(query)
                st.session_state.last_query = query
                if st.session_state.search_results:
                    st.session_state.selected_home = st.session_state.search_results[0]
        with clear_col:
            if st.button("초기화", width="stretch"):
                st.session_state.search_results = []
                st.session_state.selected_home = None
                st.rerun()

        if st.session_state.search_results:
            labels = [
                f"[{place['source']}] {place['name']} - {place['address']}"
                for place in st.session_state.search_results
            ]
            current = st.session_state.selected_home or st.session_state.search_results[0]
            current_key = (round(current["lat"], 6), round(current["lng"], 6))
            index = 0
            for i, place in enumerate(st.session_state.search_results):
                if (round(place["lat"], 6), round(place["lng"], 6)) == current_key:
                    index = i
                    break
            selected_label = st.selectbox("검색 결과", labels, index=index)
            st.session_state.selected_home = st.session_state.search_results[labels.index(selected_label)]
        elif st.session_state.last_query:
            render_callout(
                "warning",
                "검색 결과가 없습니다",
                f"'{st.session_state.last_query}' 검색 결과가 없습니다. REST API 키를 확인하거나 지도에서 직접 위치를 클릭해 선택하세요.",
            )

        selected_home = st.session_state.selected_home
        if selected_home:
            render_callout(
                "success",
                "선택 위치",
                f"{selected_home['name']} / {selected_home['address']}",
            )

        with st.expander("검색 상태"):
            st.write(
                {
                    "마지막 검색어": st.session_state.last_query,
                    "검색 결과 수": len(st.session_state.search_results),
                    "API 키 감지": bool(get_kakao_key()),
                    "GTFS 대중교통 캐시": "있음" if GTFS_CACHE.exists() else "없음",
                }
            )
            if not GTFS_CACHE.exists():
                st.caption("대중교통 네트워크 최단시간을 쓰려면 터미널에서 `python build_gtfs_cache.py`를 한 번 실행하세요.")

        st.markdown('<div class="panel-title">2. 평가 기준</div>', unsafe_allow_html=True)
        preference_preset = st.selectbox("성향 프리셋", list(AHP_PRESETS.keys()), index=1)
        preset = AHP_PRESETS[preference_preset]

        w1, w2 = st.columns(2)
        with w1:
            economic_weight = st.slider("비용", 1, 9, max(1, round(preset["economic"] * 10)))
            convenience_weight = st.slider("편의성", 1, 9, max(1, round(preset["convenience"] * 10)))
        with w2:
            time_weight = st.slider("시간", 1, 9, max(1, round(preset["time"] * 10)))
            safety_weight = st.slider("안전", 1, 9, max(1, round(preset["safety"] * 10)))

        decision_weights = normalize_weights(
            {
                "economic": economic_weight,
                "time": time_weight,
                "convenience": convenience_weight,
                "safety": safety_weight,
            }
        )
        st.markdown(
            '<div class="weight-row">'
            f'<span class="weight-chip">비용 {decision_weights["economic"]:.0%}</span>'
            f'<span class="weight-chip">시간 {decision_weights["time"]:.0%}</span>'
            f'<span class="weight-chip">편의 {decision_weights["convenience"]:.0%}</span>'
            f'<span class="weight-chip">안전 {decision_weights["safety"]:.0%}</span>'
            '</div>',
            unsafe_allow_html=True,
        )

    with map_col:
        st.markdown('<div class="panel-title">3. 지도 확인</div>', unsafe_allow_html=True)
        render_location_map(st.session_state.selected_home)

    selected_home = st.session_state.selected_home
    if not selected_home:
        render_callout(
            "info",
            "위치 선택 필요",
            "먼저 주소를 검색하거나 지도에서 현 거주지를 클릭하세요.",
        )
        st.stop()

    if st.button("분석 시작", width="stretch", type="primary"):
        st.session_state.decision_weights = decision_weights
        st.session_state.page = "results"
        st.rerun()

# ── 결과 페이지 ───────────────────────────────────────────────────────────────
elif st.session_state.page == "results":
    selected_home = st.session_state.selected_home
    if not selected_home:
        st.session_state.page = "input"
        st.rerun()

    decision_weights = st.session_state.decision_weights or AHP_PRESETS["균형형"]
    import v2_section
    import aggregate_section, mc_section

    # ── 데이터 계산 ───────────────────────────────────────────────────────────
    rate = ASSUMPTIONS["annual_interest_rate"]
    time_value = ASSUMPTIONS["hourly_time_value_won"]
    result = build_alternatives(selected_home, rate, time_value, decision_weights)
    best = result.iloc[0]
    commute_row = result[result["유형"] == "통학"].iloc[0]
    best_economic_rental = result[result["유형"] == "자취"].sort_values("AEC").iloc[0]

    aec_gap = float(best_economic_rental["AEC"] - commute_row["AEC"])
    break_even_value = best_economic_rental["손익분기월세"]
    break_even_metric = "미도달" if pd.isna(break_even_value) else f"{float(break_even_value):.0f}만원"
    mc_snapshot = estimate_mc_snapshot(commute_row, best_economic_rental, ASSUMPTIONS)
    mc_pct = mc_snapshot["p_rental_better"] * 100

    # ── 결과 페이지 추가 CSS ──────────────────────────────────────────────────
    st.markdown(
        """
        <style>
        /* 상단 nav bar */
        .ov-nav {
            display: flex; align-items: center; gap: .5rem;
            background: #fff; border: 1px solid #d8e2ee; border-radius: 10px;
            padding: .55rem 1.1rem; margin-bottom: 1.1rem;
            box-shadow: 0 2px 8px rgba(25,43,70,.05);
        }
        .ov-nav-logo {
            font-size: 1.05rem; font-weight: 840; color: #18212f;
            margin-right: .6rem; white-space: nowrap;
        }
        .ov-nav-logo em { color: #ff4d1f; font-style: normal; }
        .ov-nav-divider {
            width: 1px; height: 1.4rem; background: #d8e2ee; margin: 0 .3rem;
        }
        /* KPI strip */
        .kpi-strip {
            display: grid; grid-template-columns: repeat(4, 1fr);
            border: 1px solid #d8e2ee; border-radius: 10px; overflow: hidden;
            background: #fff; margin-bottom: 1.1rem;
            box-shadow: 0 4px 14px rgba(25,43,70,.055);
        }
        .kpi-cell { padding: 1rem 1.3rem; border-right: 1px solid #d8e2ee; }
        .kpi-cell:last-child { border-right: none; }
        .kpi-lbl { font-size: .75rem; color: #637083; margin-bottom: .18rem; }
        .kpi-val { font-size: 1.55rem; font-weight: 840; color: #18212f; line-height: 1.2; }
        .kpi-unit { font-size: .88rem; font-weight: 500; color: #637083; }
        .kpi-sub { font-size: .78rem; margin-top: .22rem; }
        .kpi-up   { color: #16a34a; } .kpi-down { color: #c2413a; } .kpi-gray { color: #637083; }
        /* Overview chart cards */
        .ov-card-head {
            display: flex; justify-content: space-between; align-items: flex-start;
            margin-bottom: .3rem;
        }
        .ov-card-title { font-size: .95rem; font-weight: 760; color: #18212f; }
        .ov-card-badge {
            font-size: .7rem; font-weight: 720; padding: .18rem .55rem;
            border-radius: 999px; background: #fff0e8; color: #c2370a;
            white-space: nowrap;
        }
        .ov-card-metric { font-size: 1.45rem; font-weight: 840; color: #18212f; margin: .15rem 0 .1rem; }
        .ov-card-sub { font-size: .78rem; color: #637083; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # ── Nav bar ───────────────────────────────────────────────────────────────
    NAV_TABS = ["Overview", "경제성", "대안표", "손익분기", "안전·편의", "확률"]

    nav_logo_col, nav_tab_col, nav_back_col = st.columns([0.18, 0.64, 0.18])
    with nav_logo_col:
        st.markdown(
            '<div class="ov-nav-logo">통학 · 자취 <em>비교</em></div>',
            unsafe_allow_html=True,
        )
    with nav_tab_col:
        if hasattr(st, "pills"):
            active_tab = st.pills(
                "nav", NAV_TABS, default="Overview",
                key="results_nav_pill", label_visibility="collapsed",
            )
            if active_tab:
                st.session_state.results_nav_tab = active_tab
        else:
            active_tab = st.radio(
                "nav", NAV_TABS, horizontal=True,
                index=NAV_TABS.index(st.session_state.get("results_nav_tab", "Overview")),
                label_visibility="collapsed",
            )
            st.session_state.results_nav_tab = active_tab
    with nav_back_col:
        if st.button("← 다시 입력하기", key="back_to_input"):
            st.session_state.results_nav_tab = "Overview"
            st.session_state.page = "input"
            st.rerun()

    active_tab = st.session_state.get("results_nav_tab", "Overview")

    # ── KPI strip (항상 표시) ─────────────────────────────────────────────────
    rec_type = str(best["유형"])
    rec_label = html.escape("통학" if rec_type == "통학" else str(best["대안"]))
    aec_lbl = "자취가 더 비쌈" if aec_gap > 0 else "자취가 더 유리"
    aec_cls = "kpi-down" if aec_gap > 0 else "kpi-up"
    mc_lbl = "자취 우세" if mc_pct > 50 else "통학 우세"
    mc_cls = "kpi-up" if mc_pct > 50 else "kpi-down"

    st.markdown(
        f"""
        <div class="kpi-strip">
          <div class="kpi-cell">
            <div class="kpi-lbl">추천 대안</div>
            <div class="kpi-val" style="font-size:1.2rem">{rec_label}</div>
            <div class="kpi-sub kpi-gray">{rec_type}</div>
          </div>
          <div class="kpi-cell">
            <div class="kpi-lbl">AEC 차이 (자취 − 통학)</div>
            <div class="kpi-val">{aec_gap:+.0f}<span class="kpi-unit"> 만원/년</span></div>
            <div class="kpi-sub {aec_cls}">{aec_lbl}</div>
          </div>
          <div class="kpi-cell">
            <div class="kpi-lbl">통학 편도시간</div>
            <div class="kpi-val">{commute_row['편도시간']:.0f}<span class="kpi-unit"> 분</span></div>
            <div class="kpi-sub kpi-gray">월 시간손실 {commute_row['월시간손실비용']:.0f}만원</div>
          </div>
          <div class="kpi-cell">
            <div class="kpi-lbl">자취 유리 확률</div>
            <div class="kpi-val">{mc_pct:.0f}<span class="kpi-unit"> %</span></div>
            <div class="kpi-sub {mc_cls}">{mc_lbl}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── 탭별 콘텐츠 ───────────────────────────────────────────────────────────
    def _chart_card(title: str, badge: str, metric: str, sub: str,
                    fig: go.Figure, height: int, key: str) -> None:
        with st.container(border=True):
            st.markdown(
                f'<div class="ov-card-head">'
                f'  <div>'
                f'    <div class="ov-card-title">{html.escape(title)}</div>'
                f'    <div class="ov-card-metric">{html.escape(metric)}</div>'
                f'    <div class="ov-card-sub">{html.escape(sub)}</div>'
                f'  </div>'
                f'  <div class="ov-card-badge">{html.escape(badge)}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            fig.update_layout(height=height)
            st.plotly_chart(fig, width="stretch", theme=None,
                            key=key, config={"displayModeBar": False})

    if active_tab == "Overview":
        # 상단 2열: 경제성 + 대안표
        ov1, ov2 = st.columns(2, gap="small")
        with ov1:
            _chart_card(
                "경제성 비교", "AEC / NPV",
                f"AEC 차이 {aec_gap:+.0f}만원/년",
                "통학 vs 최저 자취 연간등가비용",
                build_econ_mini_chart(commute_row, best_economic_rental), 210, "ov_econ",
            )
        with ov2:
            _chart_card(
                "전체 대안표", f"{len(result)}개 대안",
                f"1순위 {str(best['대안'])[:14]}",
                "월 실질비용 기준 상위 5개",
                build_table_mini_chart(result), 210, "ov_table",
            )
        # 하단 3열: 손익분기 + 안전편의 + 확률
        ob1, ob2, ob3 = st.columns(3, gap="small")
        with ob1:
            _chart_card(
                "손익분기점", "Break-even",
                break_even_metric,
                "손익분기 월세",
                build_boundary_mini_chart(commute_row, best_economic_rental, ASSUMPTIONS), 170, "ov_bnd",
            )
        with ob2:
            _chart_card(
                "안전·편의 반영", "무형가치",
                f"안전 {best['안전']:.1f}  편의 {best['편의도']:.1f}",
                "추천 대안 기준 점수",
                build_value_mini_chart(result, best), 170, "ov_val",
            )
        with ob3:
            _chart_card(
                "확률 분석", "시나리오",
                f"자취 유리 {mc_pct:.0f}%",
                "불확실성 1만 시나리오",
                build_mc_mini_chart(mc_snapshot), 170, "ov_mc",
            )

    elif active_tab == "경제성":
        render_economic_detail(commute_row, best_economic_rental)
    elif active_tab == "대안표":
        render_table_detail(result, best)
    elif active_tab == "손익분기":
        v2_section.render(result, ASSUMPTIONS)
    elif active_tab == "안전·편의":
        aggregate_section.render(result)
    elif active_tab == "확률":
        mc_section.render(result, ASSUMPTIONS)

# 민감도 탭 내용 — 비활성화됨; 아래 주석을 해제하면 복구
# with tab_sensitivity:
#     st.subheader("민감도 분석")
#     sensitivity = sensitivity_analysis(selected_home, decision_weights)
#     summary = (
#         sensitivity.groupby(["추천유형", "추천대안"])
#         .size()
#         .reset_index(name="선택횟수")
#         .sort_values("선택횟수", ascending=False)
#     )
#     st.write("월세, 금리, 통학시간 가치가 바뀔 때 추천 대안이 얼마나 자주 유지되는지 확인합니다.")
#     st.dataframe(summary, width="stretch", hide_index=True)
#     st.dataframe(
#         sensitivity.style.format({"추천AEC": "{:.0f}", "시간가치배율": "{:.1f}"}),
#         width="stretch",
#         hide_index=True,
#     )
#     with st.expander("자동 적용 기본값"):
#         st.write(
#             pd.DataFrame(
#                 [
#                     ["분석기간", f"{ASSUMPTIONS['analysis_years']}년"],
#                     ["금리", f"{ASSUMPTIONS['annual_interest_rate'] * 100:.1f}%"],
#                     ["시간가치", f"{ASSUMPTIONS['hourly_time_value_won']:,}원/시간"],
#                     ["월 등교일수", f"{ASSUMPTIONS['school_days_per_month']}일"],
#                     ["자취 식비", f"{ASSUMPTIONS['living_food']}만원/월"],
#                     ["자취 공과금", f"{ASSUMPTIONS['living_utility_extra']}만원/월"],
#                     ["인터넷", f"{ASSUMPTIONS['living_internet']}만원/월"],
#                     ["생필품", f"{ASSUMPTIONS['living_supply']}만원/월"],
#                     ["통학 교통비", f"{ASSUMPTIONS['commute_base_transport']}만원/월"],
#                     ["통학 추가 식비", f"{ASSUMPTIONS['commute_food_extra']}만원/월"],
#                     ["이사비", f"{ASSUMPTIONS['moving_cost']}만원"],
#                 ],
#                 columns=["항목", "값"],
#             )
#         )
