#!/usr/bin/env python3
"""Generate consolidated Anki CSVs and SVG locator maps."""

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
DATA_DIR = PROJECT_DIR / "data"
OUTPUT_DIR = PROJECT_DIR / "outputs"
MEDIA_DIR = OUTPUT_DIR / "media"
COMMONS_REDIRECT = "https://commons.wikimedia.org/wiki/Special:Redirect/file"
COMMONS_FILE_PAGE = "https://commons.wikimedia.org/wiki/File:"
USER_AGENT = "GazetteerAnki/0.2 (personal study deck)"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
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


def country_sort_key(config: dict) -> str:
    return f'{config["country_code"]}_{int(config["country_order"]):02d}'


def row_sort_key(config: dict, row_number: int) -> str:
    return f'{int(config["country_order"]):02d}_{config["country_code"]}_{row_number:03d}'


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


def generate_country(data_dir: Path, seed_dir: Path | None) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    config = json.loads((data_dir / "map.json").read_text(encoding="utf-8"))
    country_code = config["country_code"]
    cache_dir = PROJECT_DIR / "cache" / country_code
    cache_dir.mkdir(parents=True, exist_ok=True)
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)

    subdivision_rows: list[dict[str, str]] = []
    cached_by_code: dict[str, Path] = {}
    for row_number, subdivision in enumerate(read_csv(data_dir / "subdivisions.csv"), start=1):
        code_suffix = subdivision["subdivision_code"].split("-", 1)[1].lower()
        source_prefix = subdivision["subdivision_code"].split("-", 1)[0].lower()
        cached_svg = cache_dir / f"{source_prefix}-{code_suffix}-locator.svg"
        if not cached_svg.exists() and seed_dir:
            seed = seed_dir / cached_svg.name
            if seed.exists():
                shutil.copy2(seed, cached_svg)
        svg_url, source_url = commons_urls(subdivision["commons_file"])
        if not cached_svg.exists():
            download(svg_url, cached_svg)
            time.sleep(1)
        cached_by_code[subdivision["subdivision_code"]] = cached_svg

        filename = subdivision_filename(country_code, subdivision["subdivision_code"])
        shutil.copy2(cached_svg, MEDIA_DIR / filename)
        subdivision_rows.append({
            "sort_key": row_sort_key(config, row_number),
            "country_sort_key": country_sort_key(config),
            "country_code": country_code,
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

    base_svg = cached_by_code[config["base_subdivision_code"]]
    city_rows: list[dict[str, str]] = []
    for row_number, city in enumerate(read_csv(data_dir / "cities.csv"), start=1):
        filename = city_filename(country_code, city["city_native"])
        add_city_marker(base_svg, MEDIA_DIR / filename, config, city)
        city_rows.append({
            "sort_key": row_sort_key(config, row_number),
            "country_sort_key": country_sort_key(config),
            "country_code": country_code,
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
    return subdivision_rows, city_rows


def country_directories(selected: list[str] | None) -> list[Path]:
    directories = [path for path in DATA_DIR.iterdir() if path.is_dir()]
    if selected:
        requested = set(selected)
        directories = [path for path in directories if path.name in requested]
        missing = requested - {path.name for path in directories}
        if missing:
            raise ValueError(f"Unknown country code(s): {', '.join(sorted(missing))}")
    return sorted(
        directories,
        key=lambda path: json.loads((path / "map.json").read_text(encoding="utf-8"))["country_order"],
    )


def generate(selected: list[str] | None, seed_dir: Path | None) -> None:
    all_subdivisions: list[dict[str, str]] = []
    all_cities: list[dict[str, str]] = []
    for data_dir in country_directories(selected):
        subdivisions, cities = generate_country(data_dir, seed_dir)
        all_subdivisions.extend(subdivisions)
        all_cities.extend(cities)

    write_csv(OUTPUT_DIR / "gazetteer_subdivisions.csv", all_subdivisions)
    write_csv(OUTPUT_DIR / "gazetteer_cities.csv", all_cities)
    print(
        f"Wrote {len(all_subdivisions)} subdivisions, {len(all_cities)} cities, "
        f"and {len(all_subdivisions) + len(all_cities)} maps to {OUTPUT_DIR}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("countries", nargs="*", help="Optional ISO alpha-3 country codes, e.g. DEU FRA")
    parser.add_argument("--seed-dir", type=Path, help="Optional directory containing downloaded SVGs")
    args = parser.parse_args()
    generate(args.countries or None, args.seed_dir)


if __name__ == "__main__":
    main()
