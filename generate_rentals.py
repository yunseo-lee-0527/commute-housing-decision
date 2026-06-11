# -*- coding: utf-8 -*-
"""generate_rentals.py — 서울대입구역·낙성대역·대학동(녹두거리) 자취방 합성 데이터 생성기.

네이버 부동산은 rate-limit(429), KB부동산은 비공개 한글 파라미터 API라 라이브 크롤이
막힌 상황에서, 실제 매물 분포를 모사한 더미 매물 CSV를 만든다.

핵심 원칙
  · 좌표 : 3개 권역 중심 주변 실제 반경 내로 분산 (안전도 산정에 필요한 lat/lng 확보)
  · 가격 : 2024~2026 관악구 원룸/투룸 월세 시세대를 권역별로 차등 반영
  · 상관 : 신축·오피스텔일수록 보증금·편의·안전설비가 함께 높아지도록 결합
  · 안전 라벨 : safety.py의 _extract_building_features가 읽는 O/X·층정보 형식으로 기입
  · 안전도(점수) : 빈 칸 — score_rental_safety.py가 좌표 기반으로 자동 부여

출력 컬럼은 crawl_naver_rentals.py의 OUTPUT_COLUMNS와 호환되며, 다운스트림
app.py의 편의성 축이 평탄해지지 않도록 수치형 '편의성' 컬럼을 하나 추가한다.
"""
from __future__ import annotations

import argparse
import csv
import math
import random
from pathlib import Path

SNU = {"name": "서울대학교 관악캠퍼스", "lat": 37.459992, "lng": 126.953181}

# 권역별 프로필: 중심좌표·반경·법정동·가격 시세대(만원)·신축경향
AREAS = [
    {
        "name": "서울대입구역",
        "lat": 37.481217, "lng": 126.952713, "radius_km": 0.7,
        "dong": "봉천동",
        "deposit": (500, 2800), "rent": (43, 65), "maint": (4, 11),
        "newness_bias": 0.10,   # 역세권·오피스텔 비중 ↑
    },
    {
        "name": "낙성대역",
        "lat": 37.476930, "lng": 126.963693, "radius_km": 0.75,
        "dong": "인헌동",
        "deposit": (500, 2000), "rent": (40, 60), "maint": (3, 9),
        "newness_bias": 0.00,
    },
    {
        "name": "대학동(녹두거리)",
        "lat": 37.470821, "lng": 126.936928, "radius_km": 0.8,
        "dong": "대학동",
        "deposit": (300, 1400), "rent": (32, 55), "maint": (2, 8),
        "newness_bias": -0.12,  # 학생가·구축 빌라/고시원 비중 ↑
    },
]

HOUSE_TYPES = ["원룸", "원룸", "원룸", "분리형원룸", "투룸", "오피스텔", "빌라"]

OUTPUT_COLUMNS = [
    "권역", "출처", "매물ID", "매물URL", "매물명", "주소", "위도", "경도",
    "주거유형", "보증금_만원", "월세_만원", "관리비_만원", "가격표기",
    "층정보", "계약면적_m2", "전용면적_m2", "방향", "확인일자", "설명", "원문태그",
    "서울대거리_m", "기준역거리_m", "가까운기준점", "편의성", "편의성_라벨", "안전도",
    "공동현관_비밀번호", "지상층여부", "대로변_가까움", "CCTV", "관리인_상주", "가로등",
]


def haversine_m(lat1, lng1, lat2, lng2) -> int:
    r = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return int(2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a)))


def jitter_coord(rng: random.Random, lat: float, lng: float, radius_km: float):
    """중심 주변 반경 내 한 점을 표집하되 중심 쪽으로 몰리게(매물 밀집 모사) 흩뜨린다."""
    radius_m = radius_km * 1000
    # dist = R·u^1.3 : 면적균등(u^0.5)보다 중심에 집중 → 역·상권 코어 클러스터링
    dist = radius_m * (rng.random() ** 1.3)
    ang = rng.uniform(0, 2 * math.pi)
    dnorth = dist * math.cos(ang)
    deast = dist * math.sin(ang)
    dlat = dnorth / 111_320
    dlng = deast / (111_320 * math.cos(math.radians(lat)))
    return round(lat + dlat, 7), round(lng + dlng, 7)


def pick_floor(rng: random.Random, new_score: float):
    """층정보와 지상층여부(O/X)를 생성. 구축일수록 반지하/1층 확률↑."""
    roll = rng.random() - new_score * 0.25  # 신축일수록 저층 리스크 ↓
    if roll < 0.13:
        top = rng.choice([3, 4, 5])
        return f"반지하/{top}층", "X"
    if roll < 0.28:
        top = rng.choice([3, 4, 5])
        return f"1/{top}층", "X"
    if roll < 0.62:
        top = rng.choice([4, 5, 6, 7])
        cur = rng.randint(2, top - 1)
        return f"{cur}/{top}층", "O"
    top = rng.choice([8, 10, 12, 15])
    cur = rng.randint(max(3, top - 5), top)
    return f"고층 {cur}/{top}층", "O"


def ox(rng: random.Random, prob: float) -> str:
    return "O" if rng.random() < prob else "X"


def build_convenience_labels(rng, htype, new_score, station_dist, snu_dist, direction):
    labels = []
    if new_score > 0.66:
        labels.append("신축/준신축")
    if rng.random() < 0.35 + new_score * 0.4:
        labels.append("풀옵션")
    elif rng.random() < 0.5:
        labels.append("옵션 언급")
    if htype in ("오피스텔",) or rng.random() < new_score * 0.6:
        labels.append("엘리베이터")
    if rng.random() < 0.3 + new_score * 0.3:
        labels.append("주차 가능")
    if htype == "분리형원룸":
        labels.append("분리형")
    if htype == "투룸":
        labels.append("투룸 구조")
    if rng.random() < 0.18:
        labels.append("복층")
    if direction in ("남향", "남동향", "남서향"):
        labels.append("채광 양호")
    if rng.random() < 0.25:
        labels.append("즉시입주 가능")
    if station_dist <= 600:
        labels.append("역세권 도보권")
    elif station_dist <= 900:
        labels.append("기준역 도보권")
    if snu_dist <= 1200:
        labels.append("학교 근거리")
    elif snu_dist <= 2200:
        labels.append("학교 접근성 양호")
    return list(dict.fromkeys(labels))


def convenience_score(labels, new_score, station_dist) -> int:
    """편의성 라벨·신축도·역거리로 1~10 점수를 합성한다."""
    base = 4.0 + new_score * 2.2
    base += min(len(labels), 7) * 0.45
    if station_dist <= 600:
        base += 0.8
    return int(max(1, min(10, round(base))))


def generate(per_area: int, seed: int):
    rng = random.Random(seed)
    rows = []
    serial = 0
    for area in AREAS:
        for _ in range(per_area):
            serial += 1
            htype = rng.choice(HOUSE_TYPES)
            # 신축도: 권역 경향 + 매물별 잡음 (0~1)
            new_score = min(1.0, max(0.0, rng.betavariate(2, 2) + area["newness_bias"]))

            lat, lng = jitter_coord(rng, area["lat"], area["lng"], area["radius_km"])
            station_dist = haversine_m(lat, lng, area["lat"], area["lng"])
            snu_dist = haversine_m(lat, lng, SNU["lat"], SNU["lng"])

            # 가격: 권역 시세대 안에서 신축·유형으로 보정
            dlo, dhi = area["deposit"]
            rlo, rhi = area["rent"]
            mlo, mhi = area["maint"]
            type_bump = {"투룸": 1.3, "오피스텔": 1.12, "분리형원룸": 1.04}.get(htype, 1.0)
            rent = rng.uniform(rlo, rhi) * (0.93 + new_score * 0.16) * type_bump
            rent = int(round(rent))
            # 보증금: 월세·신축과 양의 상관, 5만원 단위 반올림
            deposit = rng.uniform(dlo, dhi) * (0.7 + new_score * 0.6) * type_bump
            deposit = int(round(deposit / 50) * 50)
            deposit = max(100, min(dhi, deposit))
            maint = int(round(rng.uniform(mlo, mhi) * (0.8 + new_score * 0.5)))

            floor_info, ground = pick_floor(rng, new_score)
            direction = rng.choice(
                ["남향", "남향", "남동향", "남서향", "동향", "서향", "북향"]
            )
            excl = {
                "원룸": rng.uniform(16, 24), "분리형원룸": rng.uniform(18, 27),
                "투룸": rng.uniform(30, 46), "오피스텔": rng.uniform(17, 30),
                "빌라": rng.uniform(26, 44),
            }[htype]
            supply = excl * rng.uniform(1.25, 1.5)

            labels = build_convenience_labels(
                rng, htype, new_score, station_dist, snu_dist, direction
            )
            conv = convenience_score(labels, new_score, station_dist)

            # 건물 안전 라벨: 신축·오피스텔일수록 설비 구비 확률 ↑
            door_lock = ox(rng, 0.45 + new_score * 0.45 + (0.2 if htype == "오피스텔" else 0))
            cctv = ox(rng, 0.40 + new_score * 0.45 + (0.2 if htype == "오피스텔" else 0))
            manager = ox(rng, 0.10 + new_score * 0.25 + (0.45 if htype == "오피스텔" else 0))
            main_road = ox(rng, 0.55 - station_dist / 4000)
            street_light = ox(rng, 0.65 + (0.2 if station_dist <= 700 else 0))

            rows.append({
                "권역": area["name"],
                "출처": "synthetic_market_model",
                "매물ID": f"SYN{serial:04d}",
                "매물URL": "",
                "매물명": f"{area['dong']} {htype} {serial:03d}",
                "주소": f"서울 관악구 {area['dong']}",
                "위도": lat,
                "경도": lng,
                "주거유형": htype,
                "보증금_만원": deposit,
                "월세_만원": rent,
                "관리비_만원": maint,
                "가격표기": f"월세 {deposit:,}/{rent}",
                "층정보": floor_info,
                "계약면적_m2": round(supply, 1),
                "전용면적_m2": round(excl, 1),
                "방향": direction,
                "확인일자": rng.choice(["2026.05.18", "2026.05.27", "2026.06.03", "2026.06.09"]),
                "설명": "; ".join(labels) if labels else "",
                "원문태그": "; ".join(labels[:4]),
                "서울대거리_m": snu_dist,
                "기준역거리_m": station_dist,
                "가까운기준점": area["name"],
                "편의성": conv,
                "편의성_라벨": "; ".join(labels),
                "안전도": "",  # score_rental_safety.py가 채움
                "공동현관_비밀번호": door_lock,
                "지상층여부": ground,
                "대로변_가까움": main_road,
                "CCTV": cctv,
                "관리인_상주": manager,
                "가로등": street_light,
            })
    return rows


def write_csv(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row.get(c, "") for c in OUTPUT_COLUMNS})


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate synthetic SNU-area rental listings.")
    ap.add_argument("--per-area", type=int, default=30, help="권역당 매물 수")
    ap.add_argument("--seed", type=int, default=20260612, help="재현용 난수 시드")
    ap.add_argument("--output", default="snu_area_rentals_crawled.csv", help="출력 CSV 경로")
    args = ap.parse_args()

    rows = generate(args.per_area, args.seed)
    out = Path(args.output)
    write_csv(out, rows)
    print(f"[DONE] {len(rows)} rows -> {out.resolve()}")


if __name__ == "__main__":
    main()
