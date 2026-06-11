# -*- coding: utf-8 -*-
"""safety.py — 안전 점수의 객관 체크리스트 정의.

"안전 6점이 무슨 뜻인가?"에 대한 답: 점수는 임의의 숫자가 아니라
사실 확인이 가능한 항목들의 합으로 '정의'된다.

  채점표 (합계 최대 10점)
    도어락·공동현관  +2.0      관리인 상주      +2.0
    1층 아님         +1.5      귀갓길 가로등    +2.0
    큰길 인접        +1.5      CCTV             +1.0

따라서 커트라인 6점은 "예: 도어락 + 비1층 + 큰길 + CCTV 수준은 갖춘 집"
이라는 자연어로 번역 가능하다. 체크리스트 컬럼이 CSV에 없으면
기존 safety 숫자로 자동 폴백한다 (하위 호환).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

# (CSV 컬럼명, 화면 표시명, 배점)
RUBRIC: list[tuple[str, str, float]] = [
    ("door_lock", "도어락·공동현관", 2.0),
    ("not_ground", "1층 아님", 1.5),
    ("main_road", "큰길 인접", 1.5),
    ("cctv", "CCTV", 1.0),
    ("manager", "관리인 상주", 2.0),
    ("street_light", "귀갓길 가로등", 2.0),
]

MAX_SCORE: float = sum(w for _, _, w in RUBRIC)  # 10.0


def load_checklist(csv_path: str = "rentals_dummy.csv") -> pd.DataFrame | None:
    """매물 CSV에서 체크리스트를 읽어 매물명(name) 인덱스의 표로 반환.

    파일이 없거나 체크리스트 컬럼이 없으면 None (호출 측에서 기존
    safety 숫자로 폴백) — CSV가 아직 옛 형식인 팀원 환경에서도 깨지지 않게.
    """
    path = Path(csv_path)
    if not path.exists():
        return None
    df = pd.read_csv(path)
    cols = [c for c, _, _ in RUBRIC]
    if not all(c in df.columns for c in cols):
        return None
    return df.set_index("name")[cols].astype(int)


def derived_scores(checklist: pd.DataFrame) -> pd.Series:
    """체크리스트 → 안전 점수. 점수 = Σ(항목 O/X × 배점)."""
    score = sum(checklist[c] * w for c, _, w in RUBRIC)
    return score.rename("안전객관")


def breakdown_table(checklist: pd.DataFrame) -> pd.DataFrame:
    """매물 × 항목 O/X 표 (+ 합계) — '점수가 어떻게 만들어졌는지' 화면용."""
    out = pd.DataFrame(index=checklist.index)
    for c, label, w in RUBRIC:
        out[f"{label} (+{w:g})"] = checklist[c].map({1: "O", 0: "—"})
    out["안전 점수"] = derived_scores(checklist)
    return out.reset_index().rename(columns={"name": "대안"})


def describe_cutoff(cutoff: float) -> str:
    """커트라인 숫자를 자연어 예시로 번역 — '6점 = 예: 도어락+비1층+큰길+CCTV'."""
    items = sorted(RUBRIC, key=lambda r: -r[2])
    picked, total = [], 0.0
    for _, label, w in items:
        if total >= cutoff:
            break
        picked.append(label)
        total += w
    if not picked:
        return "제약 없음"
    return " + ".join(picked) + f" 수준 (합계 {total:g}점)"
