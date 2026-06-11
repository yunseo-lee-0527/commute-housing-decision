"""크롤링 매물 CSV에 CPTED/GIS 기반 안전도 점수를 붙이는 CLI."""
from __future__ import annotations

import argparse
from pathlib import Path

from safety import DEFAULT_SAFETY_DATA_DIR, score_rental_csv


def main() -> None:
    parser = argparse.ArgumentParser(description="Score rental safety from latitude/longitude.")
    parser.add_argument("--input", default="snu_area_rentals_crawled.csv", help="입력 매물 CSV")
    parser.add_argument("--output", default="snu_area_rentals_scored.csv", help="출력 CSV")
    parser.add_argument("--safety-data-dir", default=str(DEFAULT_SAFETY_DATA_DIR), help="관악구 안전 데이터 폴더")
    args = parser.parse_args()

    scored = score_rental_csv(
        Path(args.input),
        Path(args.output),
        data_dir=Path(args.safety_data_dir),
    )
    print(f"saved {args.output} ({len(scored)} rows)")


if __name__ == "__main__":
    main()
