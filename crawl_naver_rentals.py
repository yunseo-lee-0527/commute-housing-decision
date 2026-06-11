"""
Collect candidate rental listings around SNU Station, Nakseongdae Station,
and Daehak-dong/Nokdu Street, then normalize them for the term project.

The script intentionally leaves safety columns blank. Safety quantification is a
separate research step, so this crawler only prepares observable listing data and
human-readable convenience labels.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests


OUTPUT_COLUMNS = [
    "권역",
    "출처",
    "매물ID",
    "매물URL",
    "매물명",
    "주소",
    "위도",
    "경도",
    "주거유형",
    "보증금_만원",
    "월세_만원",
    "관리비_만원",
    "가격표기",
    "층정보",
    "계약면적_m2",
    "전용면적_m2",
    "방향",
    "확인일자",
    "설명",
    "원문태그",
    "서울대거리_m",
    "기준역거리_m",
    "가까운기준점",
    "편의성_라벨",
    "안전도",
    "공동현관_비밀번호",
    "지상층여부",
    "대로변_가까움",
    "CCTV",
    "관리인_상주",
    "가로등",
]


SNU = {"name": "서울대학교 관악캠퍼스", "lat": 37.459992, "lng": 126.953181}

TARGET_AREAS = [
    {"name": "서울대입구역", "lat": 37.481217, "lng": 126.952713, "radius_km": 1.1},
    {"name": "낙성대역", "lat": 37.476930, "lng": 126.963693, "radius_km": 1.1},
    {"name": "대학동(녹두거리)", "lat": 37.470821, "lng": 126.936928, "radius_km": 1.2},
]

OLD_MOBILE_URL = "https://m.land.naver.com/cluster/ajax/articleList"
NEW_FRONT_API = "https://fin.land.naver.com/front-api/v1/article/boundedArticles"
NEW_LAND_API = "https://new.land.naver.com/api/articles"


@dataclass(frozen=True)
class Bounds:
    left: float
    right: float
    top: float
    bottom: float


def km_bounds(lat: float, lng: float, radius_km: float) -> Bounds:
    lat_delta = radius_km / 111.0
    lng_delta = radius_km / (111.0 * math.cos(math.radians(lat)))
    return Bounds(
        left=round(lng - lng_delta, 7),
        right=round(lng + lng_delta, 7),
        top=round(lat + lat_delta, 7),
        bottom=round(lat - lat_delta, 7),
    )


def haversine_m(lat1: float | None, lng1: float | None, lat2: float, lng2: float) -> int | str:
    if lat1 is None or lng1 is None:
        return ""
    radius = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return int(2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a)))


def sleep_polite(base: float) -> None:
    time.sleep(base + random.uniform(0.25, 0.75))


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        }
    )
    return session


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return "; ".join(clean_text(v) for v in value if clean_text(v))
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value).strip()


def money_to_manwon(value: Any) -> int | str:
    if value is None or value == "":
        return ""
    if isinstance(value, (int, float)):
        return int(value)

    text = clean_text(value)
    text = text.replace(",", "").replace("만원", "").replace(" ", "")
    if not text or text in {"-", "협의"}:
        return ""

    total = 0.0
    if "억" in text:
        before, after = text.split("억", 1)
        if before:
            total += float(re.sub(r"[^0-9.]", "", before) or 0) * 10000
        if after:
            total += float(re.sub(r"[^0-9.]", "", after) or 0)
        return int(total)

    number = re.sub(r"[^0-9.]", "", text)
    return int(float(number)) if number else ""


def parse_price_pair(price_text: str) -> tuple[int | str, int | str]:
    match = re.search(r"([0-9,억\s.]+)\s*/\s*([0-9,억\s.]+)", price_text or "")
    if not match:
        return "", ""
    return money_to_manwon(match.group(1)), money_to_manwon(match.group(2))


def first_value(obj: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        if key in obj and obj[key] not in (None, ""):
            return obj[key]
    return ""


def nested_first(obj: Any, keys: list[str]) -> Any:
    if isinstance(obj, dict):
        direct = first_value(obj, keys)
        if direct not in (None, ""):
            return direct
        for value in obj.values():
            found = nested_first(value, keys)
            if found not in (None, ""):
                return found
    elif isinstance(obj, list):
        for value in obj:
            found = nested_first(value, keys)
            if found not in (None, ""):
                return found
    return ""


def to_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def extract_floor_label(floor_info: str) -> list[str]:
    text = floor_info.replace(" ", "")
    labels: list[str] = []
    if any(token in text for token in ["B", "지하", "반지하"]):
        labels.append("반지하/지하")
    if re.search(r"(^|/|,|\\()1층", text):
        labels.append("1층")
    if "고층" in text:
        labels.append("고층")
    if "중층" in text:
        labels.append("중층")
    return labels


def convenience_labels(row: dict[str, Any], area: dict[str, Any]) -> str:
    text = " ".join(
        clean_text(row.get(key))
        for key in ["매물명", "주소", "설명", "원문태그", "층정보", "방향"]
    )
    labels: list[str] = []

    keyword_labels = [
        (["풀옵션", "풀 옵션"], "풀옵션"),
        (["옵션"], "옵션 언급"),
        (["엘리베이터", "엘베"], "엘리베이터 언급"),
        (["주차"], "주차 언급"),
        (["반려", "애완"], "반려동물 관련 언급"),
        (["즉시입주", "즉시 입주"], "즉시입주 가능"),
        (["신축", "준신축"], "신축/준신축"),
        (["남향", "채광"], "채광/방향 장점"),
        (["복층"], "복층"),
        (["분리형"], "분리형"),
        (["테라스", "베란다"], "테라스/베란다"),
        (["단기"], "단기 가능"),
        (["관리비포함", "관리비 포함"], "관리비 포함 언급"),
        (["무보증"], "무보증 언급"),
        (["언덕"], "언덕 언급"),
    ]
    for keywords, label in keyword_labels:
        if any(keyword in text for keyword in keywords):
            labels.append(label)

    labels.extend(extract_floor_label(clean_text(row.get("층정보"))))

    lat = to_float(row.get("위도"))
    lng = to_float(row.get("경도"))
    station_dist = haversine_m(lat, lng, area["lat"], area["lng"])
    snu_dist = haversine_m(lat, lng, SNU["lat"], SNU["lng"])

    if isinstance(station_dist, int) and station_dist <= 800:
        labels.append("기준역 도보권")
    if isinstance(snu_dist, int) and snu_dist <= 2200:
        labels.append("학교 접근성 양호")
    if isinstance(snu_dist, int) and snu_dist <= 1200:
        labels.append("학교 근거리")

    deduped = list(dict.fromkeys(labels))
    return "; ".join(deduped)


def normalize_old_mobile(item: dict[str, Any], area: dict[str, Any]) -> dict[str, Any]:
    lat = to_float(item.get("lat"))
    lng = to_float(item.get("lng"))
    article_id = clean_text(item.get("atclNo"))
    row = {
        "권역": area["name"],
        "출처": "naver_m_land_articleList",
        "매물ID": article_id,
        "매물URL": f"https://fin.land.naver.com/articles/{article_id}" if article_id else "",
        "매물명": clean_text(first_value(item, ["atclNm", "bildNm", "rletTpNm"])),
        "주소": clean_text(first_value(item, ["address", "atclAddr", "dongNm"])),
        "위도": lat or "",
        "경도": lng or "",
        "주거유형": clean_text(item.get("rletTpNm")),
        "보증금_만원": money_to_manwon(item.get("hanPrc")),
        "월세_만원": money_to_manwon(item.get("rentPrc")),
        "관리비_만원": money_to_manwon(first_value(item, ["manageCost", "maintenanceCost", "sameAddrCnt"])),
        "가격표기": clean_text(first_value(item, ["prc", "rentPrc", "hanPrc"])),
        "층정보": clean_text(item.get("flrInfo")),
        "계약면적_m2": clean_text(item.get("spc1")),
        "전용면적_m2": clean_text(item.get("spc2")),
        "방향": clean_text(item.get("direction")),
        "확인일자": clean_text(item.get("atclCfmYmd")),
        "설명": clean_text(item.get("atclFetrDesc")),
        "원문태그": clean_text(item.get("tagList")),
        "서울대거리_m": haversine_m(lat, lng, SNU["lat"], SNU["lng"]),
        "기준역거리_m": haversine_m(lat, lng, area["lat"], area["lng"]),
        "가까운기준점": area["name"],
        "안전도": "",
        "공동현관_비밀번호": "",
        "지상층여부": "",
        "대로변_가까움": "",
        "CCTV": "",
        "관리인_상주": "",
        "가로등": "",
    }
    row["편의성_라벨"] = convenience_labels(row, area)
    return row


def normalize_new_api(item: dict[str, Any], area: dict[str, Any], source: str) -> dict[str, Any]:
    lat = to_float(nested_first(item, ["lat", "latitude", "yCoordinate", "y"]))
    lng = to_float(nested_first(item, ["lng", "longitude", "xCoordinate", "x"]))
    article_id = clean_text(nested_first(item, ["articleNumber", "articleNo", "atclNo", "id"]))
    price_text = clean_text(nested_first(item, ["priceText", "priceName", "tradePrice", "articlePrice"]))

    deposit = nested_first(item, ["warrantyPrice", "depositPrice", "deposit", "hanPrc"])
    rent = nested_first(item, ["rentPrice", "monthlyRent", "rentPrc"])
    if (not deposit or not rent) and price_text:
        parsed_deposit, parsed_rent = parse_price_pair(price_text)
        deposit = deposit or parsed_deposit
        rent = rent or parsed_rent

    row = {
        "권역": area["name"],
        "출처": source,
        "매물ID": article_id,
        "매물URL": f"https://fin.land.naver.com/articles/{article_id}" if article_id else "",
        "매물명": clean_text(nested_first(item, ["articleName", "name", "title", "atclNm"])),
        "주소": clean_text(nested_first(item, ["address", "jibunAddress", "roadAddress", "legalDivisionName"])),
        "위도": lat or "",
        "경도": lng or "",
        "주거유형": clean_text(nested_first(item, ["realEstateTypeName", "realestateTypeName", "rletTpNm"])),
        "보증금_만원": money_to_manwon(deposit),
        "월세_만원": money_to_manwon(rent),
        "관리비_만원": money_to_manwon(nested_first(item, ["managementFee", "maintenanceFee", "manageCost"])),
        "가격표기": price_text,
        "층정보": clean_text(nested_first(item, ["floorInfo", "flrInfo"])),
        "계약면적_m2": clean_text(nested_first(item, ["supplyArea", "space", "spc1"])),
        "전용면적_m2": clean_text(nested_first(item, ["exclusiveArea", "exclusiveSpace", "spc2"])),
        "방향": clean_text(nested_first(item, ["direction", "directionName"])),
        "확인일자": clean_text(nested_first(item, ["articleConfirmYmd", "atclCfmYmd", "confirmDate"])),
        "설명": clean_text(nested_first(item, ["description", "articleFeatureDescription", "atclFetrDesc"])),
        "원문태그": clean_text(nested_first(item, ["tagList", "tags", "articleTags"])),
        "서울대거리_m": haversine_m(lat, lng, SNU["lat"], SNU["lng"]),
        "기준역거리_m": haversine_m(lat, lng, area["lat"], area["lng"]),
        "가까운기준점": area["name"],
        "안전도": "",
        "공동현관_비밀번호": "",
        "지상층여부": "",
        "대로변_가까움": "",
        "CCTV": "",
        "관리인_상주": "",
        "가로등": "",
    }
    row["편의성_라벨"] = convenience_labels(row, area)
    return row


def fetch_old_mobile(session: requests.Session, area: dict[str, Any], max_pages: int, delay: float) -> list[dict[str, Any]]:
    bounds = km_bounds(area["lat"], area["lng"], area["radius_km"])
    rows: list[dict[str, Any]] = []
    for page in range(1, max_pages + 1):
        params = {
            "itemId": "",
            "mapKey": "",
            "lgeo": "",
            "showR0": "",
            "rletTpCd": "OPST:VL:OR",
            "tradTpCd": "B2",
            "z": "15",
            "lat": area["lat"],
            "lon": area["lng"],
            "btm": bounds.bottom,
            "lft": bounds.left,
            "top": bounds.top,
            "rgt": bounds.right,
            "totCnt": "0",
            "cortarNo": "1162000000",
            "sort": "rank",
            "page": page,
        }
        response = session.get(OLD_MOBILE_URL, params=params, timeout=20)
        if response.status_code == 429:
            print(f"[WARN] old mobile API rate-limited at {area['name']} page {page}.")
            break
        try:
            payload = response.json()
        except ValueError:
            print(f"[WARN] old mobile API returned non-JSON: {response.status_code}")
            break
        body = payload.get("body") if isinstance(payload, dict) else None
        if not body:
            break
        rows.extend(normalize_old_mobile(item, area) for item in body)
        sleep_polite(delay)
    return rows


def extract_result_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    result = payload.get("result", payload)
    for key in ["articles", "articleList", "list", "items", "content"]:
        value = result.get(key) if isinstance(result, dict) else None
        if isinstance(value, list):
            return [v for v in value if isinstance(v, dict)]
    if isinstance(result, list):
        return [v for v in result if isinstance(v, dict)]
    return []


def fetch_new_front_api(session: requests.Session, area: dict[str, Any], delay: float) -> list[dict[str, Any]]:
    bounds = km_bounds(area["lat"], area["lng"], area["radius_km"])
    referer = (
        "https://fin.land.naver.com/map?"
        "articleTradeTypes=B2&articleRealEstateTypes=C01:C02:A02"
        f"&cortarNo=1162000000&center={area['lat']},{area['lng']}&zoom=15"
    )
    headers = {
        "Origin": "https://fin.land.naver.com",
        "Referer": referer,
        "Content-Type": "application/json",
    }
    session.get(referer, headers=headers, timeout=20)
    payload = {
        "filter": {"tradeTypes": ["B2"], "realEstateTypes": ["C01", "C02", "A02"]},
        "boundingBox": {
            "left": bounds.left,
            "right": bounds.right,
            "top": bounds.top,
            "bottom": bounds.bottom,
        },
        "precision": 15,
        "articlePagingRequest": {"size": 30, "articleSortType": "RANKING_DESC"},
        "userChannelType": "PC",
    }
    response = session.post(NEW_FRONT_API, headers=headers, json=payload, timeout=20)
    if response.status_code == 429:
        print(f"[WARN] new front API rate-limited at {area['name']}.")
        return []
    response.raise_for_status()
    sleep_polite(delay)
    items = extract_result_items(response.json())
    return [normalize_new_api(item, area, "naver_fin_boundedArticles") for item in items]


def fetch_new_land_api(session: requests.Session, area: dict[str, Any], max_pages: int, delay: float) -> list[dict[str, Any]]:
    referer = (
        "https://new.land.naver.com/rooms?"
        f"ms={area['lat']},{area['lng']},15&a=OR:VL:OPST&b=B2&e=RETAIL"
    )
    session.get(referer, timeout=20)
    rows: list[dict[str, Any]] = []
    for page in range(1, max_pages + 1):
        params = {
            "cortarNo": "1162000000",
            "order": "rank",
            "realEstateType": "OR:VL:OPST",
            "tradeType": "B2",
            "tag": "::::::::",
            "rentPriceMin": "0",
            "rentPriceMax": "900000000",
            "priceMin": "0",
            "priceMax": "900000000",
            "areaMin": "0",
            "areaMax": "900000000",
            "showArticle": "false",
            "sameAddressGroup": "false",
            "priceType": "RETAIL",
            "page": str(page),
            "articleState": "",
            "isComplex": "false",
        }
        response = session.get(NEW_LAND_API, params=params, headers={"Referer": referer}, timeout=20)
        if response.status_code == 429:
            print(f"[WARN] new.land API rate-limited at {area['name']} page {page}.")
            break
        response.raise_for_status()
        payload = response.json()
        items = payload.get("articleList") or payload.get("body") or []
        if not items:
            break
        rows.extend(normalize_new_api(item, area, "naver_new_land_articles") for item in items)
        sleep_polite(delay)
    return rows


def dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str, str]] = set()
    unique: list[dict[str, Any]] = []
    for row in rows:
        key = (
            clean_text(row.get("매물ID")),
            clean_text(row.get("매물명")),
            clean_text(row.get("위도")),
            clean_text(row.get("경도")),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in OUTPUT_COLUMNS})


def crawl(max_pages: int, delay: float) -> list[dict[str, Any]]:
    session = make_session()
    all_rows: list[dict[str, Any]] = []
    for area in TARGET_AREAS:
        print(f"[INFO] collecting: {area['name']}")
        area_rows: list[dict[str, Any]] = []
        area_rows.extend(fetch_old_mobile(session, area, max_pages=max_pages, delay=delay))
        if not area_rows:
            area_rows.extend(fetch_new_front_api(session, area, delay=delay))
        if not area_rows:
            area_rows.extend(fetch_new_land_api(session, area, max_pages=max_pages, delay=delay))
        print(f"[INFO] {area['name']}: {len(area_rows)} rows")
        all_rows.extend(area_rows)
        sleep_polite(delay)
    return dedupe_rows(all_rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Crawl and normalize SNU-area rental listings.")
    parser.add_argument("--output", default="snu_area_rentals_crawled.csv", help="Output CSV path")
    parser.add_argument("--max-pages", type=int, default=5, help="Max pages per source/area")
    parser.add_argument("--delay", type=float, default=2.0, help="Base delay between requests, seconds")
    args = parser.parse_args()

    rows = crawl(max_pages=args.max_pages, delay=args.delay)
    output = Path(args.output)
    write_csv(output, rows)

    if rows:
        print(f"[DONE] saved {len(rows)} rows -> {output.resolve()}")
    else:
        print(
            "[DONE] saved header-only CSV. Naver returned no public rows or rate-limited "
            f"this session -> {output.resolve()}"
        )


if __name__ == "__main__":
    main()
