import math
import os
import pickle
import sys
from datetime import datetime, timedelta
from pathlib import Path

import folium
import pandas as pd
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

st.set_page_config(page_title="등교 방식 추천", layout="wide")


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
    "hourly_time_value_won": 10320,
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
    budget: float,
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
    df["예산충족"] = df["월총비용"] <= budget
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
    df["예산패널티"] = df["예산충족"].map({True: 0, False: 0.25})
    weights = normalize_weights(weights)
    df["종합점수"] = (
        df["경제성점수"] * weights["economic"]
        + df["시간점수"] * weights["time"]
        + df["편의점수"] * weights["convenience"]
        + df["안전점수"] * weights["safety"]
        - df["예산패널티"]
    )
    return df.sort_values(["예산충족", "종합점수"], ascending=[False, False])


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


def sensitivity_analysis(home: dict, budget: float, weights: dict) -> pd.DataFrame:
    rows = []
    for rent_delta in [-20, -10, 0, 10, 20]:
        for rate_pct in [3, 5, 7, 9]:
            for time_multiplier in [0.7, 1.0, 1.3, 1.6]:
                df = build_alternatives(
                    home,
                    budget,
                    rate_pct / 100,
                    ASSUMPTIONS["hourly_time_value_won"] * time_multiplier,
                    weights,
                    rent_delta=rent_delta,
                )
                best = df.iloc[0]
                rows.append(
                    {
                        "월세변화": rent_delta,
                        "금리(%)": rate_pct,
                        "시간가치배율": time_multiplier,
                        "추천유형": best["유형"],
                        "추천대안": best["대안"],
                        "추천AEC": best["AEC"],
                    }
                )
    return pd.DataFrame(rows)


init_state()

st.title("등교 방식 추천")
st.caption("현 거주지를 검색하고 지도에서 확인한 뒤, 통학과 자취를 NPV/AEC 및 시간 기회비용 기준으로 비교합니다.")

input_col, budget_col = st.columns([2, 1])
with input_col:
    query = st.text_input("현 거주지 검색", placeholder="예: 대치현대 아파트, 안양역, 경기도 안양시 동안구 관양동")
with budget_col:
    budget = st.number_input("월 최대 사용 가능 비용(만원)", min_value=20, max_value=300, value=90, step=5)

st.subheader("의사결정 성향")
preset_col, custom_col = st.columns([1.1, 2.9])
with preset_col:
    preference_preset = st.selectbox("성향 프리셋", list(AHP_PRESETS.keys()), index=1)
with custom_col:
    st.caption("값이 클수록 해당 조건을 더 중요하게 반영합니다. 프리셋 선택 후 직접 조정할 수 있습니다.")

preset = AHP_PRESETS[preference_preset]
w1, w2, w3, w4 = st.columns(4)
with w1:
    economic_weight = st.slider("비용", 1, 9, max(1, round(preset["economic"] * 10)))
with w2:
    time_weight = st.slider("시간", 1, 9, max(1, round(preset["time"] * 10)))
with w3:
    convenience_weight = st.slider("편의성", 1, 9, max(1, round(preset["convenience"] * 10)))
with w4:
    safety_weight = st.slider("안전", 1, 9, max(1, round(preset["safety"] * 10)))

decision_weights = normalize_weights(
    {
        "economic": economic_weight,
        "time": time_weight,
        "convenience": convenience_weight,
        "safety": safety_weight,
    }
)
st.caption(
    "반영 가중치: "
    f"비용 {decision_weights['economic']:.0%}, "
    f"시간 {decision_weights['time']:.0%}, "
    f"편의성 {decision_weights['convenience']:.0%}, "
    f"안전 {decision_weights['safety']:.0%}"
)

if query.strip() and query != st.session_state.last_query:
    st.session_state.search_results = cached_search_places(query)
    st.session_state.last_query = query
    st.session_state.analysis_done = False
    if st.session_state.search_results:
        st.session_state.selected_home = st.session_state.search_results[0]

search_col, clear_col = st.columns([4, 1])
with search_col:
    if st.button("주소 검색", use_container_width=True):
        st.session_state.search_results = cached_search_places(query)
        st.session_state.last_query = query
        st.session_state.analysis_done = False
        if st.session_state.search_results:
            st.session_state.selected_home = st.session_state.search_results[0]
with clear_col:
    if st.button("초기화", use_container_width=True):
        st.session_state.search_results = []
        st.session_state.selected_home = None
        st.session_state.analysis_done = False
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
    selected_label = st.selectbox("검색 결과 선택", labels, index=index)
    st.session_state.selected_home = st.session_state.search_results[labels.index(selected_label)]
elif st.session_state.last_query:
    st.warning(
        f"'{st.session_state.last_query}' 검색 결과가 없습니다. "
        "REST API 키가 맞는지 확인하거나 지도에서 직접 위치를 클릭해 선택하세요."
    )

with st.expander("검색 상태 확인"):
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

selected_home = st.session_state.selected_home
if selected_home:
    st.success(f"선택 위치: {selected_home['name']} / {selected_home['address']}")

render_location_map(selected_home)

if not selected_home:
    st.info("먼저 주소를 검색하거나 지도에서 현 거주지를 클릭하세요.")
    st.stop()

recommend_clicked = st.button("추천 받기", use_container_width=True)
if not recommend_clicked:
    st.stop()

if selected_home is None:
    st.error("현 거주지가 선택되지 않았습니다. 주소 검색 결과를 선택하거나 지도에서 위치를 클릭해주세요.")
    st.stop()

rate = ASSUMPTIONS["annual_interest_rate"]
time_value = ASSUMPTIONS["hourly_time_value_won"]
result = build_alternatives(selected_home, budget, rate, time_value, decision_weights)
best = result.iloc[0]
commute_row = result[result["유형"] == "통학"].iloc[0]
rental_rows = result[result["유형"] == "자취"].copy()
best_economic_rental = rental_rows.sort_values("AEC").iloc[0]

st.subheader("추천 결과")
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("추천", best["대안"])
col2.metric("유형", best["유형"])
col3.metric("월 현금지출", f"{best['월현금지출']:.0f}만원")
col4.metric("월 시간손실", f"{best['월시간손실비용']:.0f}만원")
col5.metric("월 실질비용", f"{best['월실질비용']:.0f}만원")

st.caption(
    f"시간손실비용 = 편도시간 × 2(왕복) × 월 {ASSUMPTIONS['school_days_per_month']}일 "
    f"× 최저시급 {ASSUMPTIONS['hourly_time_value_won']:,}원 ÷ 60. "
    "NPV/AEC에도 이 시간손실비용을 포함합니다."
)

if not bool(best["예산충족"]):
    st.error("현재 월 예산을 충족하는 대안이 없습니다.")
elif best["유형"] == "통학":
    st.success("현재 입력 조건에서는 자취보다 현 거주지 통학이 더 적합합니다.")
else:
    st.success("현재 입력 조건에서는 자취가 더 적합합니다.")

st.subheader("경제성 공학 비교")
econ1, econ2, econ3 = st.columns(3)
econ1.metric("통학 AEC", f"{commute_row['AEC']:.0f}만원/년")
econ2.metric("최저 자취 AEC", f"{best_economic_rental['AEC']:.0f}만원/년")
econ3.metric("AEC 차이", f"{best_economic_rental['AEC'] - commute_row['AEC']:.0f}만원/년")

break_even = best_economic_rental["손익분기월세"]
if pd.isna(break_even):
    st.warning(
        f"{best_economic_rental['대안']}은 월세가 0만원이어도 통학보다 경제적으로 불리합니다."
    )
elif best_economic_rental["월세"] <= break_even:
    st.info(
        f"{best_economic_rental['대안']}의 월세는 {best_economic_rental['월세']:.0f}만원이고, "
        f"통학과 같아지는 손익분기 월세는 약 {break_even:.0f}만원입니다. 현재 월세에서는 자취가 경제적으로 유리합니다."
    )
else:
    st.info(
        f"{best_economic_rental['대안']}의 월세는 {best_economic_rental['월세']:.0f}만원이고, "
        f"통학과 같아지는 손익분기 월세는 약 {break_even:.0f}만원입니다. 월세가 이 이하일 때 자취가 경제적으로 유리합니다."
    )

display_cols = [
    "대안",
    "유형",
    "예산충족",
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
st.dataframe(
    result[display_cols].style.format(
        {
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
    ),
    use_container_width=True,
)

st.subheader("비용 비교")
st.bar_chart(result.set_index("대안")[["월현금지출", "월시간손실비용", "월실질비용"]])

st.subheader("민감도 분석")
sensitivity = sensitivity_analysis(selected_home, budget, decision_weights)
summary = (
    sensitivity.groupby(["추천유형", "추천대안"])
    .size()
    .reset_index(name="선택횟수")
    .sort_values("선택횟수", ascending=False)
)
st.write("월세, 금리, 통학시간 가치가 바뀔 때 추천 대안이 얼마나 자주 유지되는지 확인합니다.")
st.dataframe(summary, use_container_width=True)
st.dataframe(
    sensitivity.style.format({"추천AEC": "{:.0f}", "시간가치배율": "{:.1f}"}),
    use_container_width=True,
)

with st.expander("자동 적용 기본값"):
    st.write(
        pd.DataFrame(
            [
                ["분석기간", f"{ASSUMPTIONS['analysis_years']}년"],
                ["금리", f"{ASSUMPTIONS['annual_interest_rate'] * 100:.1f}%"],
                ["시간가치", f"{ASSUMPTIONS['hourly_time_value_won']:,}원/시간"],
                ["월 등교일수", f"{ASSUMPTIONS['school_days_per_month']}일"],
                ["자취 식비", f"{ASSUMPTIONS['living_food']}만원/월"],
                ["자취 공과금", f"{ASSUMPTIONS['living_utility_extra']}만원/월"],
                ["인터넷", f"{ASSUMPTIONS['living_internet']}만원/월"],
                ["생필품", f"{ASSUMPTIONS['living_supply']}만원/월"],
                ["통학 교통비", f"{ASSUMPTIONS['commute_base_transport']}만원/월"],
                ["통학 추가 식비", f"{ASSUMPTIONS['commute_food_extra']}만원/월"],
                ["이사비", f"{ASSUMPTIONS['moving_cost']}만원"],
            ],
            columns=["항목", "값"],
        )
    )
