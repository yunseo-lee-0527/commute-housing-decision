from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests


BASE = Path("data/safety_gwanak")
RAW = BASE / "raw"
EXTRACTED = BASE / "extracted"
OUT = BASE / "processed"
GWANAK_CODE = "1162000000"


def save_gdf(gdf, name, source, summary):
    gdf = gdf.copy()
    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326)
    gdf = gdf.to_crs(epsg=4326)
    rep = gdf.geometry.representative_point()
    gdf["center_lon"] = rep.x
    gdf["center_lat"] = rep.y
    gdf["geometry_wkt"] = gdf.geometry.to_wkt()
    gdf["source_dataset"] = source

    csv_path = OUT / f"{name}.csv"
    geojson_path = OUT / f"{name}.geojson"
    gdf.drop(columns="geometry").to_csv(csv_path, index=False, encoding="utf-8-sig")
    gdf.to_file(geojson_path, driver="GeoJSON")

    summary.append(
        {
            "dataset": name,
            "rows": len(gdf),
            "source": source,
            "csv": str(csv_path),
            "geojson": str(geojson_path),
        }
    )


def read_boundary():
    boundary_path = RAW / "gwanak_boundary_nominatim.geojson"
    if not boundary_path.exists():
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q": "Gwanak-gu, Seoul, South Korea",
                "format": "geojson",
                "polygon_geojson": 1,
                "limit": 1,
            },
            headers={"User-Agent": "commute-housing-decision/0.1 student research"},
            timeout=30,
        )
        response.raise_for_status()
        boundary_path.write_text(response.text, encoding="utf-8")
    return gpd.read_file(boundary_path).to_crs(epsg=4326)


def process_safe_route_shps(summary):
    configs = [
        ("safe_facility_shp", "gwanak_safe_facilities", 2, "Seoul Safe Route Facilities SHP"),
        ("safe_route_shp", "gwanak_safe_route_links", 1, "Seoul Safe Route Links SHP"),
        ("safe_service_shp", "gwanak_safe_services", 2, "Seoul Safe Route Services SHP"),
    ]
    for folder, name, code_col_idx, source in configs:
        shp = next((EXTRACTED / folder).glob("*.shp"))
        gdf = gpd.read_file(shp).to_crs(epsg=4326)
        code_col = gdf.columns[code_col_idx]
        codes = gdf[code_col].astype(str).str.replace(r"\.0$", "", regex=True)
        save_gdf(gdf[codes.eq(GWANAK_CODE)].copy(), name, source, summary)


def process_streetlights(boundary_poly, summary):
    streetlights = pd.read_csv(RAW / "seoul_streetlight.csv", encoding="cp949")
    streetlights = streetlights.iloc[:, :3].copy()
    streetlights.columns = ["light_id", "lat", "lon"]
    streetlights["lat"] = pd.to_numeric(streetlights["lat"], errors="coerce")
    streetlights["lon"] = pd.to_numeric(streetlights["lon"], errors="coerce")
    streetlights = streetlights.dropna(subset=["lat", "lon"])

    gdf = gpd.GeoDataFrame(
        streetlights,
        geometry=gpd.points_from_xy(streetlights["lon"], streetlights["lat"]),
        crs="EPSG:4326",
    )
    gwanak = gdf[gdf.geometry.within(boundary_poly)].copy()
    gwanak["facility_group"] = "streetlight"
    gwanak["filter_note"] = "Spatially filtered from citywide CSV by Gwanak boundary."
    save_gdf(gwanak, "gwanak_streetlights", "Seoul Streetlight CSV", summary)


def process_smartpoles(summary):
    smartpoles = pd.read_csv(RAW / "gwanak_smartpole.csv", encoding="cp949")
    smartpoles = smartpoles.copy()
    smartpoles["lat"] = pd.to_numeric(smartpoles.iloc[:, 3], errors="coerce")
    smartpoles["lon"] = pd.to_numeric(smartpoles.iloc[:, 4], errors="coerce")
    smartpoles = smartpoles.dropna(subset=["lat", "lon"])
    gdf = gpd.GeoDataFrame(
        smartpoles,
        geometry=gpd.points_from_xy(smartpoles["lon"], smartpoles["lat"]),
        crs="EPSG:4326",
    )
    gdf["facility_group"] = "smartpole"
    save_gdf(gdf, "gwanak_smartpoles", "Gwanak Smartpole CSV", summary)


def process_police_facilities(boundary_poly, summary):
    parts = []
    for layer_id, layer_name in [(0, "police_station"), (1, "police_substation")]:
        url = (
            "https://portal.esrikr.com/arcgis/rest/services/Hosted/"
            f"KR_PoliceStation/FeatureServer/{layer_id}/query"
        )
        response = requests.get(
            url,
            params={
                "where": "1=1",
                "outFields": "*",
                "returnGeometry": "true",
                "f": "geojson",
                "resultRecordCount": 5000,
                "outSR": "4326",
            },
            timeout=60,
        )
        response.raise_for_status()
        raw_file = RAW / f"kr_{layer_name}_all.geojson"
        raw_file.write_text(response.text, encoding="utf-8")

        gdf = gpd.read_file(raw_file).to_crs(epsg=4326)
        if len(gdf):
            gdf["facility_group"] = layer_name
            parts.append(gdf)

    if parts:
        police = pd.concat(parts, ignore_index=True)
        gwanak = police[police.geometry.within(boundary_poly)].copy()
    else:
        gwanak = gpd.GeoDataFrame(columns=["geometry"], geometry="geometry", crs="EPSG:4326")
    save_gdf(gwanak, "gwanak_police_facilities", "Esri Korea KR_PoliceStation FeatureServer", summary)


def write_count_files():
    specs = [
        ("gwanak_safe_facilities.csv", 6, "facility_code"),
        ("gwanak_safe_services.csv", 1, "service_code"),
        ("gwanak_police_facilities.csv", None, "facility_group"),
    ]
    for file_name, col_idx, label in specs:
        path = OUT / file_name
        if not path.exists():
            continue
        df = pd.read_csv(path, encoding="utf-8-sig")
        col = label if col_idx is None else df.columns[col_idx]
        if col not in df.columns:
            continue
        freq = df[col].value_counts(dropna=False).reset_index()
        freq.columns = [label, "count"]
        freq.to_csv(OUT / f"{Path(file_name).stem}_{label}_counts.csv", index=False, encoding="utf-8-sig")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    summary = []

    boundary = read_boundary()
    boundary_poly = boundary.geometry.iloc[0]
    boundary_out = boundary[["geometry"]].copy()
    boundary_out["boundary_name"] = "Gwanak-gu"
    save_gdf(boundary_out, "gwanak_boundary_osm", "OpenStreetMap Nominatim boundary", summary)

    process_safe_route_shps(summary)
    process_streetlights(boundary_poly, summary)
    process_smartpoles(summary)
    process_police_facilities(boundary_poly, summary)

    pd.DataFrame(summary).to_csv(OUT / "inventory.csv", index=False, encoding="utf-8-sig")
    write_count_files()


if __name__ == "__main__":
    main()
