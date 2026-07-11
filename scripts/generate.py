#!/usr/bin/env python3
"""Generate Anki CSVs and SVG locator maps from country source data."""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import subprocess
import time
import urllib.parse
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
COMMONS_REDIRECT = "https://commons.wikimedia.org/wiki/Special:Redirect/file"
COMMONS_FILE_PAGE = "https://commons.wikimedia.org/wiki/File:"
USER_AGENT = "GazetteerAnki/0.1 (personal study deck)"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def slug(value: str) -> str:
    replacements = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})
    value = value.lower().translate(replacements)
    return re.sub(r"[^a-z0-9]+", "-", value).strip("-")


def commons_urls(file_name: str) -> tuple[str, str]:
    quoted = urllib.parse.quote(file_name)
    return f"{COMMONS_REDIRECT}/{quoted}", f"{COMMONS_FILE_PAGE}{quoted}"


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "curl", "-L", "--fail", "--silent", "--show-error",
            "--retry", "5", "--retry-delay", "3", "-A", USER_AGENT,
            "-o", str(destination), url,
        ],
        check=True,
    )


def subdivision_filename(country_code: str, subdivision_code: str) -> str:
    suffix = subdivision_code.split("-", 1)[1].lower()
    return f"gaz-{country_code.lower()}-subdivision-{suffix}.svg"


def city_filename(country_code: str, city_native: str) -> str:
    return f"gaz-{country_code.lower()}-city-{slug(city_native)}.svg"


def project_city(latitude: float, longitude: float, projection: dict[str, float]) -> tuple[float, float]:
    lon_fraction = ((longitude - projection["longitude_min"]) /
                    (projection["longitude_max"] - projection["longitude_min"]))
    lat_fraction = ((projection["latitude_max"] - latitude) /
                    (projection["latitude_max"] - projection["latitude_min"]))
    x = projection["x_min"] + lon_fraction * (projection["x_max"] - projection["x_min"])
    y = projection["y_min"] + lat_fraction * (projection["y_max"] - projection["y_min"])
    return x, y


def add_city_marker(source: Path, destination: Path, config: dict, city: dict[str, str]) -> None:
    svg = source.read_text(encoding="utf-8")
    svg = svg.replace(config["highlight_color"], config["neutral_color"])
    x, y = project_city(float(city["latitude"]), float(city["longitude"]), config["projection"])
    marker = (
        f'\n<g id="gaz-city-marker" aria-label="City location">'
        f'<circle cx="{x:.2f}" cy="{y:.2f}" r="13" fill="#FFFFFF" opacity="0.95"/>'
        f'<circle cx="{x:.2f}" cy="{y:.2f}" r="8" fill="{config["marker_color"]}" '
        f'stroke="#333333" stroke-width="1.5"/></g>\n'
    )
    svg = svg.replace("</svg>", f"{marker}</svg>")
    destination.write_text(svg, encoding="utf-8")


def generate(country: str, seed_dir: Path | None) -> None:
    data_dir = PROJECT_DIR / "data" / country
    output_dir = PROJECT_DIR / "outputs" / country
    media_dir = output_dir / "media"
    cache_dir = PROJECT_DIR / "cache" / country
    media_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    config = json.loads((data_dir / "map.json").read_text(encoding="utf-8"))
    subdivisions = read_csv(data_dir / "subdivisions.csv")
    country_code = config["country_code"]
    subdivision_rows: list[dict[str, str]] = []
    cached_by_code: dict[str, Path] = {}

    for subdivision in subdivisions:
        code_suffix = subdivision["subdivision_code"].split("-", 1)[1].lower()
        cached_svg = cache_dir / f"{country_code.lower()}-{code_suffix}-locator.svg"
        if not cached_svg.exists() and seed_dir:
            seed = seed_dir / f"{country_code.lower()}-{code_suffix}-locator.svg"
            if seed.exists():
                shutil.copy2(seed, cached_svg)
        svg_url, source_url = commons_urls(subdivision["commons_file"])
        if not cached_svg.exists():
            download(svg_url, cached_svg)
            time.sleep(1)
        cached_by_code[subdivision["subdivision_code"]] = cached_svg

        filename = subdivision_filename(country_code, subdivision["subdivision_code"])
        shutil.copy2(cached_svg, media_dir / filename)
        subdivision_rows.append({
            "country_native": config["country_native"],
            "country_english": config["country_english"],
            "subdivision_native": subdivision["subdivision_native"],
            "subdivision_english": subdivision["subdivision_english"],
            "capital_native": subdivision["capital_native"],
            "capital_english": subdivision["capital_english"],
            "subdivision_code": subdivision["subdivision_code"],
            "map_image": f'<img src="{filename}" />',
            "map_filename": filename,
            "map_source": source_url,
        })

    write_csv(output_dir / f"{country}_subdivisions.csv", subdivision_rows)

    base_svg = cached_by_code[config["base_subdivision_code"]]
    city_rows: list[dict[str, str]] = []
    for city in read_csv(data_dir / "cities.csv"):
        filename = city_filename(country_code, city["city_native"])
        add_city_marker(base_svg, media_dir / filename, config, city)
        city_rows.append({
            "country_native": config["country_native"],
            "country_english": config["country_english"],
            "city_native": city["city_native"],
            "city_english": city["city_english"],
            "is_capital": city["is_capital"],
            "subdivision_native": city["subdivision_native"],
            "subdivision_english": city["subdivision_english"],
            "latitude": city["latitude"],
            "longitude": city["longitude"],
            "map_image": f'<img src="{filename}" />',
            "map_filename": filename,
        })
    write_csv(output_dir / f"{country}_cities.csv", city_rows)
    print(f"Wrote {len(subdivision_rows)} subdivisions and {len(city_rows)} cities to {output_dir}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("country", choices=sorted(path.name for path in (PROJECT_DIR / "data").iterdir()))
    parser.add_argument("--seed-dir", type=Path, help="Optional directory containing previously downloaded SVGs")
    args = parser.parse_args()
    generate(args.country, args.seed_dir)


if __name__ == "__main__":
    main()
