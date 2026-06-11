# -*- coding: utf-8 -*-
"""CPTED/GIS 기반 관악구 주거 안전도 산정 모듈.

이 파일의 핵심 함수는 두 가지다.

1. score_home_safety(lat, lon)
   집의 위도/경도만으로 공공 안전 인프라 접근성 점수를 계산한다.

2. score_rental_csv(input_csv, output_csv)
   크롤링된 매물 CSV에 safety, 안전최종, 세부 컴포넌트 점수 컬럼을 붙인다.

주의: 이 점수는 실제 범죄확률 예측값이 아니라, CPTED 선행연구와 관악구 공개
공간데이터를 결합한 "상대적 주거환경 안전도" 지표다.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math
import re
from typing import Any

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_SAFETY_DATA_DIR = BASE_DIR / "data" / "safety_gwanak" / "processed"
EARTH_RADIUS_M = 6_371_008.8


# ---------------------------------------------------------------------------
# Backward-compatible checklist rubric
# ---------------------------------------------------------------------------

RUBRIC: list[tuple[str, str, float]] = [
    ("door_lock", "도어락/공동현관", 2.0),
    ("not_ground", "1층/지하 아님", 1.5),
    ("main_road", "대로변 인접", 1.5),
    ("cctv", "건물 CCTV", 1.0),
    ("manager", "관리인 상주", 2.0),
    ("street_light", "근거리 가로등", 2.0),
]

MAX_SCORE: float = sum(w for _, _, w in RUBRIC)


def load_checklist(csv_path: str = "snu_area_rentals_scored.csv") -> pd.DataFrame | None:
    """체크리스트형(영문 O/X 컬럼) CSV를 읽어 매물명 index의 O/X 표로 반환한다.

    현재 매물 데이터는 CPTED/GIS 좌표 기반 안전도(SafetyScorer)를 쓰므로 RUBRIC
    영문 컬럼이 없으면 None을 돌려주고, 호출부는 좌표 기반 안전도로 폴백한다.
    """
    path = Path(csv_path)
    if not path.exists():
        return None
    df = pd.read_csv(path)
    cols = [c for c, _, _ in RUBRIC]
    if "name" not in df.columns or not all(c in df.columns for c in cols):
        return None
    return df.set_index("name")[cols].apply(pd.to_numeric, errors="coerce").fillna(0).astype(int)


def derived_scores(checklist: pd.DataFrame) -> pd.Series:
    """체크리스트 기반 건물 안전 점수. 0~10점."""
    score = sum(checklist[c] * w for c, _, w in RUBRIC)
    return score.rename("안전점수")


def breakdown_table(checklist: pd.DataFrame) -> pd.DataFrame:
    """체크리스트 항목별 O/X와 합계 점수 표."""
    out = pd.DataFrame(index=checklist.index)
    for c, label, w in RUBRIC:
        out[f"{label} (+{w:g})"] = checklist[c].map({1: "O", 0: "X"}).fillna("X")
    out["안전 점수"] = derived_scores(checklist)
    return out.reset_index().rename(columns={"name": "대안"})


def describe_cutoff(cutoff: float) -> str:
    """안전 커트라인의 직관적 의미를 체크리스트 항목 조합으로 설명한다."""
    items = sorted(RUBRIC, key=lambda r: -r[2])
    picked: list[str] = []
    total = 0.0
    for _, label, w in items:
        if total >= cutoff:
            break
        picked.append(label)
        total += w
    if not picked:
        return "제약 없음"
    return " + ".join(picked) + f" 수준(합계 {total:g}점)"


# ---------------------------------------------------------------------------
# CPTED/GIS scoring engine
# ---------------------------------------------------------------------------

COMPONENT_WEIGHTS = {
    "cctv": 0.30,
    "lighting": 0.25,
    "police": 0.20,
    "safe_route": 0.15,
    "emergency": 0.10,
}

COMPONENT_LABELS = {
    "cctv": "CCTV 접근성",
    "lighting": "조명 접근성",
    "police": "경찰/치안시설 접근성",
    "safe_route": "안심귀갓길 접근성",
    "emergency": "비상/지원시설 접근성",
}

LAT_ALIASES = ("lat", "latitude", "위도", "center_lat")
LON_ALIASES = ("lng", "lon", "longitude", "경도", "center_lon")


@dataclass(frozen=True)
class ComponentScore:
    score: float
    nearest_m: float | None
    count_within_cutoff: int


def _read_csv(path: Path) -> pd.DataFrame:
    for encoding in ("utf-8-sig", "utf-8", "cp949"):
        try:
            return pd.read_csv(path, encoding=encoding)
        except UnicodeDecodeError:
            continue
    return pd.read_csv(path)


def _first_existing(columns: pd.Index, aliases: tuple[str, ...]) -> str | None:
    lowered = {str(c).lower(): c for c in columns}
    for alias in aliases:
        if alias in columns:
            return alias
        if alias.lower() in lowered:
            return lowered[alias.lower()]
    return None


def _numeric(value: Any, default: float | None = None) -> float | None:
    if value is None or pd.isna(value):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        text = str(value).replace(",", "")
        match = re.search(r"-?\d+(?:\.\d+)?", text)
        return float(match.group(0)) if match else default


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """두 WGS84 좌표 사이의 구면거리(m)."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def _local_xy_m(lat: float, lon: float, ref_lat: float, ref_lon: float) -> tuple[float, float]:
    x = math.radians(lon - ref_lon) * EARTH_RADIUS_M * math.cos(math.radians(ref_lat))
    y = math.radians(lat - ref_lat) * EARTH_RADIUS_M
    return x, y


def _point_to_segment_distance_m(
    lat: float,
    lon: float,
    a: tuple[float, float],
    b: tuple[float, float],
) -> float:
    px, py = _local_xy_m(lat, lon, lat, lon)
    ax, ay = _local_xy_m(a[0], a[1], lat, lon)
    bx, by = _local_xy_m(b[0], b[1], lat, lon)
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    cx, cy = ax + t * dx, ay + t * dy
    return math.hypot(px - cx, py - cy)


def _parse_wkt_lines(wkt: Any) -> list[list[tuple[float, float]]]:
    """LINESTRING/MULTILINESTRING WKT를 [(lat, lon), ...] 리스트로 변환."""
    if not isinstance(wkt, str) or "LINESTRING" not in wkt.upper():
        return []
    text = wkt.strip()
    upper = text.upper()
    if upper.startswith("MULTILINESTRING"):
        inner = text[text.find("((") + 2 : text.rfind("))")]
        raw_parts = re.split(r"\)\s*,\s*\(", inner)
    else:
        inner = text[text.find("(") + 1 : text.rfind(")")]
        raw_parts = [inner]

    lines: list[list[tuple[float, float]]] = []
    for part in raw_parts:
        coords: list[tuple[float, float]] = []
        for lon_s, lat_s in re.findall(r"(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)", part):
            coords.append((float(lat_s), float(lon_s)))
        if len(coords) >= 2:
            lines.append(coords)
    return lines


def _distance_to_lines_m(lat: float, lon: float, lines: list[list[tuple[float, float]]]) -> float | None:
    best: float | None = None
    for line in lines:
        for a, b in zip(line, line[1:]):
            dist = _point_to_segment_distance_m(lat, lon, a, b)
            if best is None or dist < best:
                best = dist
    return best


def _distance_decay(distance_m: float | None, core_m: float, cutoff_m: float) -> float:
    if distance_m is None:
        return 0.0
    if distance_m <= core_m:
        return 1.0
    if distance_m >= cutoff_m:
        return 0.0
    return (cutoff_m - distance_m) / (cutoff_m - core_m)


def _police_decay(distance_m: float | None) -> float:
    if distance_m is None:
        return 0.0
    if distance_m <= 50:
        return 1.0
    if distance_m <= 500:
        return 1.0 - (distance_m - 50) / 450 * 0.35
    if distance_m <= 1000:
        return 0.65 * (1000 - distance_m) / 500
    return 0.0


def _truthy(value: Any) -> bool | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"", "nan", "none", "null"}:
        return None
    if text in {"1", "y", "yes", "true", "t", "o", "있음", "예", "가능"}:
        return True
    if text in {"0", "n", "no", "false", "f", "x", "없음", "아니오", "불가"}:
        return False
    return None


def _find_by_contains(columns: pd.Index, *needles: str) -> str | None:
    for col in columns:
        text = str(col)
        if all(needle in text for needle in needles):
            return col
    return None


def _points_from_df(df: pd.DataFrame) -> list[tuple[float, float]]:
    lat_col = _first_existing(df.columns, LAT_ALIASES)
    lon_col = _first_existing(df.columns, LON_ALIASES)
    if lat_col is None or lon_col is None:
        return []
    points: list[tuple[float, float]] = []
    for _, row in df.iterrows():
        lat = _numeric(row.get(lat_col))
        lon = _numeric(row.get(lon_col))
        if lat is not None and lon is not None:
            points.append((lat, lon))
    return points


def _nearest_point_component(
    lat: float,
    lon: float,
    points: list[tuple[float, float]],
    core_m: float,
    cutoff_m: float,
    police: bool = False,
) -> ComponentScore:
    if not points:
        return ComponentScore(0.0, None, 0)
    distances = [haversine_m(lat, lon, p_lat, p_lon) for p_lat, p_lon in points]
    nearest = min(distances)
    count = sum(d <= cutoff_m for d in distances)
    score = _police_decay(nearest) if police else _distance_decay(nearest, core_m, cutoff_m)
    return ComponentScore(score, nearest, count)


def _nearest_route_component(
    lat: float,
    lon: float,
    routes: list[list[tuple[float, float]]],
    core_m: float,
    cutoff_m: float,
) -> ComponentScore:
    if not routes:
        return ComponentScore(0.0, None, 0)
    distances = [_distance_to_lines_m(lat, lon, [route]) for route in routes]
    distances = [d for d in distances if d is not None]
    if not distances:
        return ComponentScore(0.0, None, 0)
    nearest = min(distances)
    count = sum(d <= cutoff_m for d in distances)
    return ComponentScore(_distance_decay(nearest, core_m, cutoff_m), nearest, count)


def _component_to_dict(component: ComponentScore) -> dict[str, float | None | int]:
    return {
        "score": round(component.score, 4),
        "nearest_m": None if component.nearest_m is None else round(component.nearest_m, 1),
        "count_within_cutoff": component.count_within_cutoff,
    }


def _grade(score_100: float) -> str:
    if score_100 >= 90:
        return "A"
    if score_100 >= 80:
        return "A-"
    if score_100 >= 70:
        return "B+"
    if score_100 >= 60:
        return "B"
    if score_100 >= 50:
        return "C"
    return "D"


class SafetyScorer:
    """관악구 안전 인프라 데이터로 좌표별 안전도 점수를 계산한다."""

    def __init__(self, data_dir: str | Path = DEFAULT_SAFETY_DATA_DIR):
        self.data_dir = Path(data_dir)
        self.cctv_points: list[tuple[float, float]] = []
        self.lighting_points: list[tuple[float, float]] = []
        self.police_points: list[tuple[float, float]] = []
        self.emergency_points: list[tuple[float, float]] = []
        self.safe_routes: list[list[tuple[float, float]]] = []
        self._load()

    def _load(self) -> None:
        facilities_path = self.data_dir / "gwanak_safe_facilities.csv"
        if facilities_path.exists():
            facilities = _read_csv(facilities_path)
            code_col = "시설코드" if "시설코드" in facilities.columns else facilities.columns[6]
            codes = pd.to_numeric(facilities[code_col], errors="coerce")
            self.cctv_points.extend(_points_from_df(facilities[codes.eq(302)]))
            self.lighting_points.extend(_points_from_df(facilities[codes.eq(305)]))
            self.emergency_points.extend(_points_from_df(facilities[codes.isin([301, 306, 307, 308])]))

        streetlights_path = self.data_dir / "gwanak_streetlights.csv"
        if streetlights_path.exists():
            self.lighting_points.extend(_points_from_df(_read_csv(streetlights_path)))

        smartpoles_path = self.data_dir / "gwanak_smartpoles.csv"
        if smartpoles_path.exists():
            smartpoles = _read_csv(smartpoles_path)
            cctv_col = _find_by_contains(smartpoles.columns, "CCTV")
            light_col = _find_by_contains(smartpoles.columns, "보안등")
            bell_col = _find_by_contains(smartpoles.columns, "비상벨")
            if cctv_col:
                self.cctv_points.extend(_points_from_df(smartpoles[smartpoles[cctv_col].map(_truthy).eq(True)]))
            if light_col:
                self.lighting_points.extend(_points_from_df(smartpoles[smartpoles[light_col].map(_truthy).eq(True)]))
            if bell_col:
                self.emergency_points.extend(_points_from_df(smartpoles[smartpoles[bell_col].map(_truthy).eq(True)]))

        services_path = self.data_dir / "gwanak_safe_services.csv"
        if services_path.exists():
            self.emergency_points.extend(_points_from_df(_read_csv(services_path)))

        police_path = self.data_dir / "gwanak_police_facilities.csv"
        if police_path.exists():
            self.police_points.extend(_points_from_df(_read_csv(police_path)))

        routes_path = self.data_dir / "gwanak_safe_route_links.csv"
        if routes_path.exists():
            routes = _read_csv(routes_path)
            if "geometry_wkt" in routes.columns:
                for wkt in routes["geometry_wkt"]:
                    self.safe_routes.extend(_parse_wkt_lines(wkt))

    def public_environment_score(self, lat: float, lon: float) -> tuple[float, dict[str, ComponentScore]]:
        components = {
            "cctv": _nearest_point_component(lat, lon, self.cctv_points, 100, 300),
            "lighting": _nearest_point_component(lat, lon, self.lighting_points, 10, 50),
            "police": _nearest_point_component(lat, lon, self.police_points, 50, 1000, police=True),
            "safe_route": _nearest_route_component(lat, lon, self.safe_routes, 30, 150),
            "emergency": _nearest_point_component(lat, lon, self.emergency_points, 50, 150),
        }
        score = sum(components[key].score * weight for key, weight in COMPONENT_WEIGHTS.items()) * 100
        return score, components

    def score_location(self, lat: float, lon: float, building_features: dict[str, Any] | None = None) -> dict[str, Any]:
        public_score, components = self.public_environment_score(lat, lon)
        building_score = building_safety_score_100(building_features)
        final_score = public_score if building_score is None else public_score * 0.65 + building_score * 0.35
        return {
            "safety_score_100": round(final_score, 2),
            "safety_score_10": round(final_score / 10, 2),
            "grade": _grade(final_score),
            "public_environment_score_100": round(public_score, 2),
            "building_score_100": None if building_score is None else round(building_score, 2),
            "components": {key: _component_to_dict(value) for key, value in components.items()},
        }


def building_safety_score_100(features: dict[str, Any] | None) -> float | None:
    """매물 라벨이 있을 때 건물 자체 안전도를 0~100으로 계산한다.

    입력 가능한 키:
    door_lock, building_cctv, manager, not_ground, main_road, street_light
    """
    if not features:
        return None

    values = {key: _truthy(value) for key, value in features.items()}
    pieces: list[tuple[float, float]] = []

    if values.get("door_lock") is not None:
        pieces.append((0.45, 1.0 if values["door_lock"] else 0.0))

    monitoring = [values.get("building_cctv"), values.get("manager")]
    monitoring = [v for v in monitoring if v is not None]
    if monitoring:
        pieces.append((0.20, 1.0 if any(monitoring) else 0.0))

    if values.get("not_ground") is not None:
        pieces.append((0.20, 1.0 if values["not_ground"] else 0.0))

    visibility = [values.get("main_road"), values.get("street_light")]
    visibility = [v for v in visibility if v is not None]
    if visibility:
        pieces.append((0.15, 1.0 if any(visibility) else 0.0))

    weight_sum = sum(weight for weight, _ in pieces)
    if weight_sum == 0:
        return None
    return sum(weight * score for weight, score in pieces) / weight_sum * 100


def _floor_not_ground(value: Any) -> bool | None:
    if value is None or pd.isna(value):
        return None
    text = str(value)
    if any(token in text for token in ("지하", "B1", "b1", "반지하")):
        return False
    if re.search(r"(^|[^0-9])1\s*층", text):
        return False
    if re.search(r"\d+\s*층", text):
        return True
    return _truthy(value)


def _extract_building_features(row: pd.Series) -> dict[str, Any]:
    def pick(*names: str) -> Any:
        for name in names:
            if name in row.index and not pd.isna(row[name]):
                return row[name]
        return None

    not_ground = pick("not_ground", "1층/지하여부", "저층위험")
    if not_ground is None:
        not_ground = _floor_not_ground(pick("층정보", "floor"))

    return {
        "door_lock": pick("door_lock", "공동현관_비밀번호", "공동현관", "출입통제", "도어락"),
        "building_cctv": pick("building_cctv", "cctv", "CCTV", "건물CCTV"),
        "manager": pick("manager", "관리인_상주", "관리인"),
        "not_ground": not_ground,
        "main_road": pick("main_road", "대로변_가까움", "대로변"),
        "street_light": pick("street_light", "가로등", "보안등"),
    }


def _add_app_compat_columns(df: pd.DataFrame) -> pd.DataFrame:
    """크롤링 CSV를 app.py가 읽을 수 있는 영문 컬럼 형태로 보강한다."""
    out = df.copy()
    aliases = {
        "name": ("name", "매물명", "대안"),
        "address": ("address", "주소"),
        "lat": ("lat", "위도", "latitude"),
        "lng": ("lng", "경도", "lon", "longitude"),
        "deposit": ("deposit", "보증금_만원", "보증금"),
        "monthly_rent": ("monthly_rent", "월세_만원", "월세"),
        "maintenance_fee": ("maintenance_fee", "관리비_만원", "관리비"),
        "monthly_transport": ("monthly_transport", "월교통비_만원", "월교통비"),
        "convenience": ("convenience", "편의도", "편의성", "편의성_점수"),
    }
    for target, names in aliases.items():
        if target in out.columns:
            continue
        source = _first_existing(out.columns, names)
        if source is not None:
            out[target] = out[source]

    for col, default in [("monthly_transport", 2.0), ("convenience", 6.0)]:
        if col not in out.columns:
            out[col] = default

    if "safety" not in out.columns and "safety_score_10" in out.columns:
        out["safety"] = out["safety_score_10"]
    return out


def score_dataframe(df: pd.DataFrame, data_dir: str | Path = DEFAULT_SAFETY_DATA_DIR) -> pd.DataFrame:
    """매물 DataFrame에 안전도 컬럼을 추가한다."""
    out = df.copy()
    lat_col = _first_existing(out.columns, LAT_ALIASES)
    lon_col = _first_existing(out.columns, LON_ALIASES)
    if lat_col is None or lon_col is None:
        raise ValueError("CSV에 위도/경도 컬럼(lat/lng 또는 위도/경도)이 필요합니다.")

    scorer = SafetyScorer(data_dir)
    rows: list[dict[str, Any]] = []
    for _, row in out.iterrows():
        lat = _numeric(row.get(lat_col))
        lon = _numeric(row.get(lon_col))
        if lat is None or lon is None:
            rows.append({})
            continue
        result = scorer.score_location(lat, lon, _extract_building_features(row))
        flat = {
            "safety_score_100": result["safety_score_100"],
            "safety_score_10": result["safety_score_10"],
            "safety": result["safety_score_10"],
            "안전최종": result["safety_score_10"],
            "안전도": result["safety_score_10"],
            "안전등급": result["grade"],
            "안전_공공환경": round(result["public_environment_score_100"] / 10, 2),
            "안전_건물보정": None
            if result["building_score_100"] is None
            else round(result["building_score_100"] / 10, 2),
        }
        for key, component in result["components"].items():
            flat[f"안전_{key}"] = round(component["score"] * 10, 2)
            flat[f"가까운_{key}_m"] = component["nearest_m"]
            flat[f"{key}_반경내개수"] = component["count_within_cutoff"]
        rows.append(flat)

    scored = pd.concat([out.reset_index(drop=True), pd.DataFrame(rows)], axis=1)
    if "safety_score_100" in scored.columns and not scored.empty:
        scored["안전_백분위"] = scored["safety_score_100"].rank(pct=True, method="average").mul(100).round(1)
    return _add_app_compat_columns(scored)


def score_rental_csv(
    input_csv: str | Path,
    output_csv: str | Path,
    data_dir: str | Path = DEFAULT_SAFETY_DATA_DIR,
) -> pd.DataFrame:
    """CSV 파일을 읽어 안전도 점수 컬럼을 붙이고 저장한다."""
    input_path = Path(input_csv)
    output_path = Path(output_csv)
    df = _read_csv(input_path)
    scored = score_dataframe(df, data_dir=data_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    scored.to_csv(output_path, index=False, encoding="utf-8-sig")
    return scored


def score_home_safety(
    lat: float,
    lon: float,
    data_dir: str | Path = DEFAULT_SAFETY_DATA_DIR,
    building_features: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """단일 좌표의 안전도 점수를 반환한다."""
    return SafetyScorer(data_dir).score_location(float(lat), float(lon), building_features)
