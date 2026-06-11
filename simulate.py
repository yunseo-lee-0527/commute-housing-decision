# -*- coding: utf-8 -*-
"""simulate.py — 입력 불확실성의 Monte Carlo 시뮬레이션 + 정보가치(EVPI).

점추정("통학시간 48분") 대신 분포("최소 40, 보통 48, 최악 75분")를 받아
수천 개의 가상 시나리오를 만들고, 각 시나리오에서 닫힌 해(model.py)로
자취/통학 비용을 계산한다. 출력은 단일 답이 아니라:

  - 자취가 유리할 확률
  - 연간 절약액(ΔAEC)의 분포 (중앙값, 90% 구간)
  - EVPI: "결정 전에 불확실성을 완전히 해소하는 정보의 가치 (만원/년)"
  - EVPPI(통학시간): "통학시간만 실측해보는 행위의 가치 (만원/년)"

모델이 입력에 선형이라 numpy 벡터 연산으로 1만 회가 즉시 계산된다.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from model import Params, Rental, aec_commute, aec_rental, crf


@dataclass(frozen=True)
class MCInputs:
    """불확실한 입력들의 범위. (lo == hi 로 주면 그 값으로 고정된다)

    commute_tri: 현 거주지 편도 통학시간의 (최소, 보통, 최악) — 삼각분포.
        '보통'이 최빈값이고 최악 쪽 꼬리가 길수록 변동성 비용이 커진다.
    wage_range: 시간가치 (원/시간)의 (lo, hi) — 균등분포.
    days_range: 월 등교일수의 (lo, hi) — 균등분포.
    rate_range: 연 금리의 (lo, hi) — 균등분포.
    """

    commute_tri: tuple[float, float, float]
    wage_range: tuple[float, float] = (10_320.0, 10_320.0)
    days_range: tuple[float, float] = (22.0, 22.0)
    rate_range: tuple[float, float] = (0.05, 0.05)
    n: int = 10_000
    seed: int = 42

    def central(self) -> dict:
        """모든 입력을 대표값(최빈값/중앙)으로 고정한 딕셔너리 — tornado 기준점."""
        return {
            "m": self.commute_tri[1],
            "w": (self.wage_range[0] + self.wage_range[1]) / 2,
            "D": (self.days_range[0] + self.days_range[1]) / 2,
            "i": (self.rate_range[0] + self.rate_range[1]) / 2,
        }


def _tri(rng, lo, mode, hi, n):
    if hi - lo < 1e-12:
        return np.full(n, mode)
    return rng.triangular(lo, mode, hi, n)


def _uni(rng, lo, hi, n):
    if hi - lo < 1e-12:
        return np.full(n, lo)
    return rng.uniform(lo, hi, n)


def _aec_pair(rental: Rental, m_c, w, D, i, p: Params):
    """닫힌 해를 numpy 배열에 그대로 적용 (model.py와 같은 식의 벡터판)."""
    years = p.analysis_years
    crf_v = np.where(
        i == 0, 1.0 / years, i * (1 + i) ** years / ((1 + i) ** years - 1)
    )
    tau_v = (2.0 * D * 12.0 / 60.0) * w / 1e4
    c_commute = 12.0 * p.commute_fixed_monthly + tau_v * m_c
    c_rental = (
        p.moving_cost * crf_v
        + rental.deposit * i
        + 12.0 * (rental.monthly_rent + rental.fixed_monthly)
        + tau_v * rental.one_way_minutes
    )
    return c_commute, c_rental


def run_mc(rental: Rental, mc: MCInputs, p: Params = Params()) -> dict:
    """Monte Carlo 본체. 반환 dict의 'save'는 시나리오별 연간 절약액 배열.

    save = AEC_통학 − AEC_자취 (만원/년).  양수 = 그 시나리오에선 자취가 유리.
    """
    rng = np.random.default_rng(mc.seed)
    m_c = _tri(rng, *mc.commute_tri, mc.n)
    w = _uni(rng, *mc.wage_range, mc.n)
    D = _uni(rng, *mc.days_range, mc.n)
    i = _uni(rng, *mc.rate_range, mc.n)

    c_commute, c_rental = _aec_pair(rental, m_c, w, D, i, p)
    save = c_commute - c_rental

    # EVPI: "모든 불확실성이 결정 전에 해소된다면" 얻는 기대 절감.
    #   정보 없이: 평균 비용이 싼 쪽 하나를 고정 선택 → min(E[자취], E[통학])
    #   완전 정보: 시나리오마다 싼 쪽을 골라탐         → E[min(자취, 통학)]
    #   둘의 차이가 정보의 가치. 정의상 항상 0 이상이다.
    ev_no_info = min(c_rental.mean(), c_commute.mean())
    evpi = ev_no_info - np.minimum(c_rental, c_commute).mean()

    # EVPPI(x): 특정 입력 x'만' 미리 알게 될 때의 가치.
    #   x의 구간(bin)별로 "그 구간이라면 어느 쪽이 평균적으로 싼가"를
    #   골라탈 수 있게 되는 효과를 계산. 항상 0 ≤ EVPPI ≤ EVPI.
    def _evppi(x: np.ndarray) -> float:
        order = np.argsort(x)
        k = max(10, mc.n // 200)
        bins_r = np.array_split(c_rental[order], k)
        bins_c = np.array_split(c_commute[order], k)
        cond = sum(min(br.mean(), bc.mean()) * len(br)
                   for br, bc in zip(bins_r, bins_c))
        return max(0.0, ev_no_info - cond / mc.n)

    evppi_commute = _evppi(m_c)
    evppi_wage = _evppi(w)

    q05, q50, q95 = np.percentile(save, [5, 50, 95])
    return {
        "save": save,
        "p_rental_better": float((save > 0).mean()),
        "mean": float(save.mean()),
        "q05": float(q05),
        "q50": float(q50),
        "q95": float(q95),
        "evpi": float(evpi),
        "evppi_commute": float(evppi_commute),
        "evppi_wage": float(evppi_wage),
    }


def tornado(rental: Rental, mc: MCInputs, p: Params = Params()) -> list[dict]:
    """민감도 토네이도: 한 번에 한 입력만 lo/hi로 흔들고 나머지는 대표값 고정.

    반환: [{입력, save_lo, save_hi, 폭}] — 폭이 큰 입력일수록 결론을 크게 흔든다.
    """
    c = mc.central()

    def save_at(m=None, w=None, D=None, i=None) -> float:
        vals = {"m": m or c["m"], "w": w or c["w"], "D": D or c["D"], "i": i or c["i"]}
        p_ = p.with_(
            hourly_time_value_won=vals["w"],
            school_days_per_month=vals["D"],
            annual_interest_rate=vals["i"],
        )
        return aec_commute(vals["m"], p_) - aec_rental(rental, p_)

    base = save_at()
    specs = [
        ("통학시간(편도분)", {"m": mc.commute_tri[0]}, {"m": mc.commute_tri[2]}),
        ("시간가치(원/h)", {"w": mc.wage_range[0]}, {"w": mc.wage_range[1]}),
        ("등교일수(일/월)", {"D": mc.days_range[0]}, {"D": mc.days_range[1]}),
        ("금리(연)", {"i": mc.rate_range[0]}, {"i": mc.rate_range[1]}),
    ]
    rows = []
    for name, lo_kw, hi_kw in specs:
        s_lo, s_hi = save_at(**lo_kw), save_at(**hi_kw)
        rows.append({
            "입력": name,
            "save_lo": min(s_lo, s_hi),
            "save_hi": max(s_lo, s_hi),
            "폭": abs(s_hi - s_lo),
            "base": base,
        })
    rows.sort(key=lambda r: -r["폭"])
    return rows
