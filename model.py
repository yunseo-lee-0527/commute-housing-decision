# -*- coding: utf-8 -*-
"""model.py — 자취 vs 통학 의사결정 모델의 닫힌 해(closed-form) 코어.

v1의 NPV 합산 + 45회 이분탐색을 대수적으로 동치인 닫힌 해로 대체한다.
이 모듈은 Streamlit/네트워크에 의존하지 않는 순수 계산 모듈이며,
What-if 그리드 스윕, Monte Carlo, EVPI 계산의 공통 기반이 된다.

────────────────────────────────────────────────────────────────────
유도 요약 (단위: 만원, 연 단위 현금흐름, n년 분석)

  NPV = C0 + A·(P/A, i, n) − S·(P/F, i, n),   AEC = NPV·(A/P, i, n)

  항등식 1:  (P/A, i, n)·(A/P, i, n) = 1
  항등식 2:  (A/P, i, n) = (A/F, i, n) + i        (자본회수 = 감채기금 + 금리)

  ⇒  AEC_자취 = M·CRF + d·i + 12·(r + F) + τ·m
     AEC_통학 = 12·F_c + τ·m_c

  여기서
    M  = 이사비,  d = 보증금(잔존가치로 전액 회수),  i = 연 금리
    r  = 월세,    F = 월세 외 고정 월비용(관리비+생활비+교통비)
    m  = 편도 통학시간(분),  τ = (2·D·12/60)·(w/10⁴)  [만원/년·편도분]
    D  = 월 등교일수,  w = 시간가치(원/시간)

  핵심 해석:
    · 보증금의 연간 기회비용은 정확히 d×i (근사가 아닌 항등식)
    · 편도 1분의 월 비용 = τ/12 만원 → 시간과 월세가 같은 화폐로 환산됨
    · (통학시간 × 월세) 평면에서 결정 경계는 기울기 τ/12 의 직선
────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Mapping


# ──────────────────────────────────────────────
# 파라미터
# ──────────────────────────────────────────────
@dataclass(frozen=True)
class Params:
    """모델 전역 가정. v1의 ASSUMPTIONS와 1:1 대응 (금액 단위: 만원)."""

    analysis_years: int = 4
    annual_interest_rate: float = 0.05
    school_days_per_month: float = 22.0
    hourly_time_value_won: float = 10_320.0
    moving_cost: float = 60.0          # 자취 초기 이사비
    commute_fixed_monthly: float = 16.0  # 통학 고정 월비용 = 교통 8 + 추가 식비 8

    def with_(self, **kwargs) -> "Params":
        """일부 가정만 바꾼 사본 (What-if 스윕용). 예: p.with_(annual_interest_rate=0.07)"""
        return replace(self, **kwargs)


@dataclass(frozen=True)
class Rental:
    """자취 대안 1건의 비용 프로필."""

    name: str
    deposit: float            # 보증금 (만원)
    monthly_rent: float       # 월세 (만원)
    fixed_monthly: float      # 월세 외 고정 월비용 = 관리비 + 생활비 + 교통비 (만원)
    one_way_minutes: float    # 매물 → 학교 편도시간 (분)


# ──────────────────────────────────────────────
# 경제성공학 기본 계수
# ──────────────────────────────────────────────
def crf(rate: float, years: int) -> float:
    """자본회수계수 (A/P, i, n)."""
    if rate == 0:
        return 1.0 / years
    return rate * (1 + rate) ** years / ((1 + rate) ** years - 1)


def tau(p: Params) -> float:
    """편도 통학시간 1분의 '연간' 시간비용 (만원/년).

    τ = 편도 1분 × 2(왕복) × D일 × 12개월 ÷ 60 × w ÷ 10⁴
    기본 가정(D=22, w=10,320)에서 τ ≈ 9.082 만원/년, τ/12 ≈ 0.757 만원/월.
    """
    return (2.0 * p.school_days_per_month * 12.0 / 60.0) * p.hourly_time_value_won / 1e4


# ──────────────────────────────────────────────
# AEC (닫힌 해)
# ──────────────────────────────────────────────
def aec_rental(rental: Rental, p: Params) -> float:
    """자취 대안의 연간등가비용. v1 economic_metrics(...)['AEC']와 수치적으로 동일."""
    return (
        p.moving_cost * crf(p.annual_interest_rate, p.analysis_years)
        + rental.deposit * p.annual_interest_rate
        + 12.0 * (rental.monthly_rent + rental.fixed_monthly)
        + tau(p) * rental.one_way_minutes
    )


def aec_commute(commute_one_way_minutes: float, p: Params) -> float:
    """통학 대안의 연간등가비용 (초기비용·잔존가치 없음)."""
    return 12.0 * p.commute_fixed_monthly + tau(p) * commute_one_way_minutes


def aec_breakdown(rental: Rental, p: Params) -> Mapping[str, float]:
    """자취 AEC의 '월 등가' 분해 — 발표/UI에서 메커니즘을 그대로 보여주는 용도.

    합계 × 12 = aec_rental 과 일치한다.
    """
    k = crf(p.annual_interest_rate, p.analysis_years)
    return {
        "월세": rental.monthly_rent,
        "고정월비용(관리비+생활비+교통비)": rental.fixed_monthly,
        "보증금 이자(d×i÷12)": rental.deposit * p.annual_interest_rate / 12.0,
        "이사비 연환산(M×CRF÷12)": p.moving_cost * k / 12.0,
        "시간비용(τ/12×편도분)": tau(p) / 12.0 * rental.one_way_minutes,
    }


# ──────────────────────────────────────────────
# 손익분기 월세 & 결정 경계
# ──────────────────────────────────────────────
def break_even_rent(
    rental: Rental, commute_one_way_minutes: float, p: Params
) -> float:
    """통학과 AEC가 같아지는 임계 월세 r* (닫힌 해, 만원).

    r* = [AEC_통학 − M·CRF − d·i − 12F − τ·m_r] / 12

    음수이면 '월세 0원이어도 통학보다 불리'를 뜻한다 (v1의 None 케이스).
    v1과 달리 [0, 300] 범위 제한이 없으므로 r* > 300 도 정확히 계산된다.
    """
    k = crf(p.annual_interest_rate, p.analysis_years)
    return (
        aec_commute(commute_one_way_minutes, p)
        - p.moving_cost * k
        - rental.deposit * p.annual_interest_rate
        - 12.0 * rental.fixed_monthly
        - tau(p) * rental.one_way_minutes
    ) / 12.0


@dataclass(frozen=True)
class BoundaryLine:
    """(편도 통학시간 m_c) × (월세 r) 평면 위의 결정 경계 직선.

    r*(m_c) = slope · m_c + intercept
    경계 아래(r < r*) → 자취 유리, 경계 위(r > r*) → 통학 유리.
    slope = τ/12 : '편도 1분 ↔ 월세 τ/12 만원'의 교환비.
    """

    slope: float
    intercept: float

    def rent_at(self, commute_minutes: float) -> float:
        return self.slope * commute_minutes + self.intercept

    def minutes_at(self, rent: float) -> float:
        """월세 r일 때 결론이 뒤집히는 통학시간 (분)."""
        return (rent - self.intercept) / self.slope


def decision_boundary(rental: Rental, p: Params) -> BoundaryLine:
    """주어진 자취 매물에 대해 결정 경계 직선을 반환."""
    k = crf(p.annual_interest_rate, p.analysis_years)
    t = tau(p)
    intercept = (
        p.commute_fixed_monthly
        - (p.moving_cost * k + rental.deposit * p.annual_interest_rate) / 12.0
        - rental.fixed_monthly
        - (t / 12.0) * rental.one_way_minutes
    )
    return BoundaryLine(slope=t / 12.0, intercept=intercept)


# ──────────────────────────────────────────────
# 해석 상수 (발표 멘트 / UI 캡션 자동 생성용)
# ──────────────────────────────────────────────
def equivalences(p: Params) -> Mapping[str, float]:
    """모델 전체를 설명하는 교환비들."""
    k = crf(p.annual_interest_rate, p.analysis_years)
    t = tau(p)
    return {
        "편도10분의_월세등가_만원": t / 12.0 * 10.0,
        "보증금1000만원의_월비용_만원": 1000.0 * p.annual_interest_rate / 12.0,
        "이사비의_월비용_만원": p.moving_cost * k / 12.0,
        "월세1만원의_통학시간등가_분": 12.0 / t,
        "tau_만원_per_년_편도분": t,
        "CRF": k,
    }


# ──────────────────────────────────────────────
# v1 어댑터 — 기존 app.py의 DataFrame 행에서 바로 변환
# ──────────────────────────────────────────────
def rental_from_v1_row(row: Mapping) -> Rental:
    """v1 build_alternatives()가 만든 자취 행(Series/dict) → Rental.

    사용 예:
        best = result[result["유형"] == "자취"].sort_values("AEC").iloc[0]
        rental = rental_from_v1_row(best)
    """
    return Rental(
        name=str(row["대안"]),
        deposit=float(row["보증금"]),
        monthly_rent=float(row["월세"]),
        fixed_monthly=float(row["월총비용"]) - float(row["월세"]),
        one_way_minutes=float(row["편도시간"]),
    )
