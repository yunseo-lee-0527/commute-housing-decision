# -*- coding: utf-8 -*-
"""test_model.py — 닫힌 해 모듈이 v1 코드와 수치적으로 동일함을 검증.

실행:  python test_model.py   (pytest로도 실행 가능)

v1의 economic_metrics / break_even_rent를 원본 그대로 복사해 두고,
매물 전수 × 금리 4종 × 시간가치 4종 그리드에서 model.py와 대조한다.
"""
from __future__ import annotations

import csv
import math
from pathlib import Path

from model import (
    Params,
    Rental,
    aec_breakdown,
    aec_commute,
    aec_rental,
    break_even_rent,
    decision_boundary,
)

# ────────────────────────────────────────────
# v1 원본 (app.py에서 그대로 복사 — 비교 기준)
# ────────────────────────────────────────────
V1_ASSUMPTIONS = {
    "analysis_years": 4,
    "school_days_per_month": 22,
    "moving_cost": 60,
}


def _v1_annual_time_cost(m, w):
    return m * 2 * V1_ASSUMPTIONS["school_days_per_month"] * 12 / 60 * w / 10000


def _v1_pvf(rate, year):
    return 1 / ((1 + rate) ** year)


def _v1_crf(rate, years):
    if rate == 0:
        return 1 / years
    return rate * (1 + rate) ** years / ((1 + rate) ** years - 1)


def v1_aec(deposit, initial_extra, monthly_cost, minutes, rate, w):
    years = V1_ASSUMPTIONS["analysis_years"]
    annual_total = monthly_cost * 12 + _v1_annual_time_cost(minutes, w)
    pv = sum(annual_total * _v1_pvf(rate, t) for t in range(1, years + 1))
    npv = deposit + initial_extra + pv - deposit * _v1_pvf(rate, years)
    return npv * _v1_crf(rate, years)


def v1_break_even(commute_aec, deposit, fixed_monthly, minutes, rate, w):
    zero = v1_aec(deposit, V1_ASSUMPTIONS["moving_cost"], fixed_monthly, minutes, rate, w)
    if zero > commute_aec:
        return None
    low, high = 0.0, 300.0
    for _ in range(45):
        mid = (low + high) / 2
        mid_aec = v1_aec(deposit, V1_ASSUMPTIONS["moving_cost"],
                         fixed_monthly + mid, minutes, rate, w)
        if mid_aec <= commute_aec:
            low = mid
        else:
            high = mid
    return low


# ────────────────────────────────────────────
# 테스트 데이터: 레포의 더미 매물 CSV
# ────────────────────────────────────────────
SCHOOL = (37.459992, 126.953181)
OTHER_LIVING = 32 + 8 + 3 + 5  # 식비+공과금+인터넷+생필품 (v1과 동일)


def _haversine_km(lat1, lng1, lat2, lng2):
    R = 6371
    dlat, dlng = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlng / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _minutes(dist):
    if dist <= 1.5:
        return max(8, round(dist / 4.5 * 60))
    return max(12, round(dist / 16 * 60 + 12))


def _load_rentals():
    csv_path = Path(__file__).parent / "snu_area_rentals_scored.csv"
    if not csv_path.exists():  # 점수 미부여 시 크롤/생성 CSV로 폴백
        csv_path = Path(__file__).parent / "snu_area_rentals_crawled.csv"
    out = []
    for r in csv.DictReader(open(csv_path, encoding="utf-8")):
        dist = _haversine_km(float(r["lat"]), float(r["lng"]), *SCHOOL)
        fixed = float(r["maintenance_fee"]) + OTHER_LIVING + float(r["monthly_transport"])
        out.append(Rental(
            name=r["name"], deposit=float(r["deposit"]),
            monthly_rent=float(r["monthly_rent"]), fixed_monthly=fixed,
            one_way_minutes=_minutes(dist),
        ))
    return out


GRID_RATES = [0.03, 0.05, 0.07, 0.09]
GRID_MULTS = [0.7, 1.0, 1.3, 1.6]
M_COMMUTE = 48.0  # 제안서 예시: 대치현대아파트 편도


# ────────────────────────────────────────────
# 테스트
# ────────────────────────────────────────────
def test_aec_matches_v1():
    rentals = _load_rentals()
    worst = 0.0
    for rate in GRID_RATES:
        for mult in GRID_MULTS:
            w = 10320 * mult
            p = Params(annual_interest_rate=rate, hourly_time_value_won=w)
            worst = max(worst, abs(
                v1_aec(0, 0, p.commute_fixed_monthly, M_COMMUTE, rate, w)
                - aec_commute(M_COMMUTE, p)))
            for rt in rentals:
                v1 = v1_aec(rt.deposit, 60, rt.monthly_rent + rt.fixed_monthly,
                            rt.one_way_minutes, rate, w)
                worst = max(worst, abs(v1 - aec_rental(rt, p)))
    assert worst < 1e-9, f"AEC 불일치: {worst:.2e}"
    print(f"[PASS] AEC: v1 대비 최대 오차 {worst:.2e} 만원/년 "
          f"({len(rentals)}매물 x {len(GRID_RATES)}금리 x {len(GRID_MULTS)}시간가치)")


def test_break_even_matches_v1():
    rentals = _load_rentals()
    worst, none_mismatch = 0.0, 0
    for rate in GRID_RATES:
        for mult in GRID_MULTS:
            w = 10320 * mult
            p = Params(annual_interest_rate=rate, hourly_time_value_won=w)
            c_aec = aec_commute(M_COMMUTE, p)
            for rt in rentals:
                be_v1 = v1_break_even(c_aec, rt.deposit, rt.fixed_monthly,
                                      rt.one_way_minutes, rate, w)
                be_cf = break_even_rent(rt, M_COMMUTE, p)
                if be_v1 is None:
                    none_mismatch += int(be_cf >= 0)
                else:
                    worst = max(worst, abs(be_v1 - min(be_cf, 300.0)))
    assert none_mismatch == 0 and worst < 1e-8
    print(f"[PASS] 손익분기 월세: 최대 오차 {worst:.2e} 만원, None 판정 불일치 0건")


def test_boundary_is_consistent():
    """경계선 위의 임의 점에서 AEC_자취 == AEC_통학, minutes_at은 rent_at의 역함수."""
    p = Params()
    rt = _load_rentals()[0]
    line = decision_boundary(rt, p)
    for m_c in [10, 35, 48, 72, 110]:
        r_star = line.rent_at(m_c)
        rt_at_star = Rental(rt.name, rt.deposit, r_star, rt.fixed_monthly,
                            rt.one_way_minutes)
        assert abs(aec_rental(rt_at_star, p) - aec_commute(m_c, p)) < 1e-9
        assert abs(line.minutes_at(r_star) - m_c) < 1e-9
    print("[PASS] 결정 경계: 경계 위에서 AEC 일치, rent_at/minutes_at 역함수 관계 성립")


def test_breakdown_sums_to_aec():
    p = Params()
    for rt in _load_rentals():
        assert abs(sum(aec_breakdown(rt, p).values()) * 12 - aec_rental(rt, p)) < 1e-9
    print("[PASS] 월 등가 분해: 합계 x 12 == AEC")


def test_v1_cap_bug_fixed():
    """v1 이분탐색은 탐색 구간이 [0,300]이라 r* > 300 이면 300으로 잘못 포화된다.
    닫힌 해는 구간 제한이 없다. (극단 조건: 편도 300분, 시간가치 x2)"""
    rate, w = 0.05, 10320 * 2.0
    p = Params(annual_interest_rate=rate, hourly_time_value_won=w)
    rt = _load_rentals()[1]
    c_aec = aec_commute(300.0, p)
    be_v1 = v1_break_even(c_aec, rt.deposit, rt.fixed_monthly,
                          rt.one_way_minutes, rate, w)
    be_cf = break_even_rent(rt, 300.0, p)
    assert be_cf > 300.0 and abs(be_v1 - 300.0) < 1e-6
    print(f"[PASS] v1 300만원 포화 버그 확인: v1={be_v1:.1f} (포화) vs 닫힌 해={be_cf:.1f}만원")


if __name__ == "__main__":
    test_aec_matches_v1()
    test_break_even_matches_v1()
    test_boundary_is_consistent()
    test_breakdown_sums_to_aec()
    test_v1_cap_bug_fixed()
    print("\n모든 테스트 통과 — model.py는 v1과 수치적으로 동일하며 닫힌 해로 일반화됨")
