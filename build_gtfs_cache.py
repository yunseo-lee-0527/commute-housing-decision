import pickle
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).parent
GTFS_DIR = Path(r"C:\Users\iy579\Desktop\[해커톤 5팀] 최종제출파일\[해커톤 5팀] 최종제출파일")
CACHE_PATH = PROJECT_DIR / "gtfs_seoul_cache.pkl"

SEOUL_BOUNDS = {
    "min_lat": 37.35,
    "max_lat": 37.72,
    "min_lng": 126.75,
    "max_lng": 127.25,
}


def parse_seconds(value: str) -> int | None:
    try:
        hour, minute, second = [int(part) for part in str(value).split(":")]
    except ValueError:
        return None
    return hour * 3600 + minute * 60 + second


def in_bounds(stops: pd.DataFrame) -> pd.Series:
    return (
        stops["stop_lat"].between(SEOUL_BOUNDS["min_lat"], SEOUL_BOUNDS["max_lat"])
        & stops["stop_lon"].between(SEOUL_BOUNDS["min_lng"], SEOUL_BOUNDS["max_lng"])
    )


def main() -> None:
    stops_path = GTFS_DIR / "stops.txt"
    stop_times_path = GTFS_DIR / "stop_times.txt"

    print("Loading stops...")
    stops = pd.read_csv(stops_path)
    seoul_stops = stops[in_bounds(stops)].copy()
    seoul_stop_ids = set(seoul_stops["stop_id"].astype(str))
    print(f"Seoul-area stops: {len(seoul_stops):,}")

    graph = {stop_id: {} for stop_id in seoul_stop_ids}
    trip_buffer = {}

    columns = ["trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence"]
    print("Streaming stop_times. This can take several minutes...")
    for chunk_index, chunk in enumerate(
        pd.read_csv(stop_times_path, usecols=columns, chunksize=1_000_000)
    ):
        chunk["stop_id"] = chunk["stop_id"].astype(str)
        chunk = chunk[chunk["stop_id"].isin(seoul_stop_ids)].copy()
        if chunk.empty:
            continue

        chunk["stop_sequence"] = pd.to_numeric(chunk["stop_sequence"], errors="coerce")
        chunk["arrival_s"] = chunk["arrival_time"].map(parse_seconds)
        chunk["departure_s"] = chunk["departure_time"].map(parse_seconds)
        chunk.dropna(subset=["stop_sequence", "arrival_s", "departure_s"], inplace=True)
        chunk.sort_values(["trip_id", "stop_sequence"], inplace=True)

        for trip_id, group in chunk.groupby("trip_id", sort=False):
            records = group[["stop_id", "arrival_s", "departure_s", "stop_sequence"]].to_dict("records")
            if trip_id in trip_buffer:
                records = [trip_buffer.pop(trip_id)] + records
            for prev, cur in zip(records, records[1:]):
                if cur["stop_sequence"] <= prev["stop_sequence"]:
                    continue
                travel = int(cur["arrival_s"] - prev["departure_s"])
                if travel < 0:
                    travel += 24 * 3600
                if travel <= 0 or travel > 7200:
                    continue
                u, v = prev["stop_id"], cur["stop_id"]
                old = graph.setdefault(u, {}).get(v)
                if old is None or travel < old:
                    graph[u][v] = travel
            if records:
                trip_buffer[trip_id] = records[-1]

        if chunk_index % 10 == 0:
            edge_count = sum(len(v) for v in graph.values())
            print(f"Chunk {chunk_index:,}: edges={edge_count:,}")

    cache = {
        "stops": seoul_stops[["stop_id", "stop_name", "stop_lat", "stop_lon"]].to_dict("records"),
        "graph": graph,
        "walk_speed_mps": 1.2,
        "transfer_penalty_s": 5 * 60,
    }
    with CACHE_PATH.open("wb") as file:
        pickle.dump(cache, file)
    print(f"Saved cache: {CACHE_PATH}")


if __name__ == "__main__":
    main()
