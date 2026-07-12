#!/usr/bin/env python3
"""Generate country-scoped Anki CSVs and SVG locator maps."""

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
        fieldnames = list(rows[0])
        handle.write("#separator:Comma\n")
        csv.writer(handle).writerow([f"#columns:{fieldnames[0]}", *fieldnames[1:]])
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
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


def clear_country_media(media_dir: Path, country_code: str) -> None:
    for path in media_dir.glob(f"gaz-{country_code.lower()}-*.svg"):
        path.unlink()


def row_sort_key(
    config: dict,
    family_order: int,
    family_code: str,
    row_number: int,
) -> str:
    return (
        f'{config["country_code"]}_{family_order:02d}_{family_code}_'
        f'{row_number:03d}'
    )


def english_if_different(native: str, english: str) -> str:
    return "" if native == english else english


def not_capital_value(city: dict[str, str]) -> str:
    return "true" if city["is_capital"].lower() != "y" else ""


def project_city(latitude: float, longitude: float, projection: dict[str, float]) -> tuple[float, float]:
    lon_fraction = ((longitude - projection["longitude_min"]) /
                    (projection["longitude_max"] - projection["longitude_min"]))
    lat_fraction = ((projection["latitude_max"] - latitude) /
                    (projection["latitude_max"] - projection["latitude_min"]))
    x = projection["x_min"] + lon_fraction * (projection["x_max"] - projection["x_min"])
    y = projection["y_min"] + lat_fraction * (projection["y_max"] - projection["y_min"])
    return x, y


def city_marker(city: dict[str, str], config: dict, highlighted: bool) -> str:
    x, y = project_city(float(city["latitude"]), float(city["longitude"]), config["projection"])
    if highlighted:
        return (
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="13" fill="#FFFFFF" opacity="0.95"/>'
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="8" fill="{config["marker_color"]}" '
            f'stroke="#333333" stroke-width="1.5"/>'
        )
    return (
        f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4.5" fill="#FFFFFF" '
        f'opacity="0.85" stroke="#333333" stroke-width="1.25"/>'
    )


def add_city_markers(
    source: Path,
    destination: Path,
    config: dict,
    cities: list[dict[str, str]],
    highlighted_city: dict[str, str],
) -> None:
    svg = source.read_text(encoding="utf-8")
    svg = svg.replace(config["highlight_color"], config["neutral_color"])
    other_markers = [
        city_marker(city, config, highlighted=False)
        for city in cities
        if city is not highlighted_city
    ]
    highlighted_marker = city_marker(highlighted_city, config, highlighted=True)
    marker = (
        f'\n<g id="gaz-city-markers" aria-label="City locations">'
        f'{"".join(other_markers)}{highlighted_marker}</g>\n'
    )
    svg = svg.replace("</svg>", f"{marker}</svg>")
    destination.write_text(svg, encoding="utf-8")


def generate_country(data_dir: Path, seed_dir: Path | None) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    config = json.loads((data_dir / "map.json").read_text(encoding="utf-8"))
    country_code = config["country_code"]
    cache_dir = PROJECT_DIR / "cache" / country_code
    country_output_dir = OUTPUT_DIR / country_code
    media_dir = country_output_dir / "media"
    cache_dir.mkdir(parents=True, exist_ok=True)
    media_dir.mkdir(parents=True, exist_ok=True)
    clear_country_media(media_dir, country_code)

    subdivision_rows: list[dict[str, str]] = []
    cached_by_code: dict[str, Path] = {}
    subdivisions = read_csv(data_dir / "subdivisions.csv")
    subdivisions_by_code = {
        subdivision["subdivision_code"]: subdivision
        for subdivision in subdivisions
    }
    for row_number, subdivision in enumerate(subdivisions, start=1):
        parent_code = subdivision["parent_subdivision_code"]
        parent = subdivisions_by_code.get(parent_code)
        if parent_code and parent is None:
            raise ValueError(
                f"Unknown parent subdivision code {parent_code} for "
                f'{subdivision["subdivision_code"]}'
            )
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
        shutil.copy2(cached_svg, media_dir / filename)
        subdivision_rows.append({
            "sort_key": row_sort_key(config, 1, "SUB1", row_number),
            "country_code": country_code,
            "country_native": config["country_native"],
            "country_english": config["country_english"],
            "subdivision_native": subdivision["subdivision_native"],
            "subdivision_english": english_if_different(
                subdivision["subdivision_native"],
                subdivision["subdivision_english"],
            ),
            "subdivision_type_native": subdivision["subdivision_type_native"],
            "subdivision_type_english": subdivision["subdivision_type_english"],
            "subdivision_level": subdivision["subdivision_level"],
            "parent_subdivision_code": parent_code,
            "parent_subdivision_native": parent["subdivision_native"] if parent else "",
            "parent_subdivision_english": english_if_different(
                parent["subdivision_native"],
                parent["subdivision_english"],
            ) if parent else "",
            "capital_native": subdivision["capital_native"],
            "capital_english": english_if_different(
                subdivision["capital_native"],
                subdivision["capital_english"],
            ),
            "subdivision_code": subdivision["subdivision_code"],
            "map_image": f'<img src="{filename}" />',
            "map_filename": filename,
            "map_source": source_url,
        })

    base_svg = cached_by_code[config["base_subdivision_code"]]
    city_rows: list[dict[str, str]] = []
    cities = read_csv(data_dir / "cities.csv")
    for row_number, city in enumerate(cities, start=1):
        filename = city_filename(country_code, city["city_native"])
        add_city_markers(base_svg, media_dir / filename, config, cities, city)
        city_rows.append({
            "sort_key": row_sort_key(config, 2, "CITY", row_number),
            "country_code": country_code,
            "country_native": config["country_native"],
            "country_english": config["country_english"],
            "city_native": city["city_native"],
            "city_english": english_if_different(
                city["city_native"],
                city["city_english"],
            ),
            "not_capital": not_capital_value(city),
            "subdivision_native": city["subdivision_native"],
            "subdivision_english": english_if_different(
                city["subdivision_native"],
                city["subdivision_english"],
            ),
            "latitude": city["latitude"],
            "longitude": city["longitude"],
            "map_image": f'<img src="{filename}" />',
            "map_filename": filename,
        })
    write_csv(country_output_dir / "subdivisions.csv", subdivision_rows)
    write_csv(country_output_dir / "cities.csv", city_rows)
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
    subdivision_count = 0
    city_count = 0
    for data_dir in country_directories(selected):
        subdivisions, cities = generate_country(data_dir, seed_dir)
        subdivision_count += len(subdivisions)
        city_count += len(cities)

    print(
        f"Wrote {subdivision_count} subdivisions, {city_count} cities, "
        f"and {subdivision_count + city_count} maps to country folders in {OUTPUT_DIR}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("countries", nargs="*", help="Optional ISO alpha-3 country codes, e.g. DEU FRA")
    parser.add_argument("--seed-dir", type=Path, help="Optional directory containing downloaded SVGs")
    args = parser.parse_args()
    generate(args.countries or None, args.seed_dir)


if __name__ == "__main__":
    main()
