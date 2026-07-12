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
import xml.etree.ElementTree as ET
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


def commons_download_urls(file_names: list[str]) -> dict[str, str]:
    if not file_names:
        return {}
    result = subprocess.run(
        [
            "curl", "-L", "--fail", "--silent", "--show-error",
            "--retry", "8", "--retry-delay", "5", "--retry-all-errors",
            "-A", USER_AGENT,
            "--get", "https://commons.wikimedia.org/w/api.php",
            "--data", "action=query",
            "--data", "format=json",
            "--data", "formatversion=2",
            "--data", "prop=imageinfo",
            "--data", "iiprop=url",
            "--data-urlencode", f'titles={"|".join(f"File:{name}" for name in file_names)}',
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    urls = {}
    for page in payload["query"]["pages"]:
        if "missing" in page or not page.get("imageinfo"):
            raise ValueError(f'Unknown Wikimedia Commons file: {page["title"]}')
        urls[page["title"].removeprefix("File:")] = page["imageinfo"][0]["url"]
    return urls


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "curl", "-L", "--fail", "--silent", "--show-error",
            "--retry", "8", "--retry-delay", "5", "--retry-all-errors",
            "-A", USER_AGENT,
            "-o", str(destination), url,
        ],
        check=True,
    )


def subdivision_filename(
    country_code: str,
    subdivision_code: str,
    media_kind: str = "subdivision",
) -> str:
    suffix = subdivision_code.split("-", 1)[1].lower()
    return f"gaz-{country_code.lower()}-{media_kind}-{suffix}.svg"


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
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="18" fill="#FFFFFF" opacity="0.95"/>'
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="11" fill="{config["marker_color"]}" '
            f'stroke="#333333" stroke-width="2"/>'
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


def set_svg_fill(element: ET.Element, color: str) -> None:
    for child in element.iter():
        fill_changed = False
        fill = child.get("fill")
        if fill and fill.lower() != "none":
            child.set("fill", color)
            child.set("fill-opacity", "1")
            fill_changed = True
        style = child.get("style")
        if style:
            declarations = []
            for declaration in style.split(";"):
                if declaration.startswith("fill:") and declaration != "fill:none":
                    declaration = f"fill:{color}"
                    fill_changed = True
                if fill_changed and declaration.startswith("fill-opacity:"):
                    declaration = "fill-opacity:1"
                declarations.append(declaration)
            if fill_changed and not any(
                declaration.startswith("fill-opacity:") for declaration in declarations
            ):
                declarations.append("fill-opacity:1")
            child.set("style", ";".join(declarations))


def find_svg_target(
    id_index: dict[str, ET.Element],
    parent_index: dict[ET.Element, ET.Element],
    target_id: str,
) -> ET.Element:
    inkscape_label = "{http://www.inkscape.org/namespaces/inkscape}label"

    def is_in_department_layer(element: ET.Element) -> bool:
        while element in parent_index:
            element = parent_index[element]
            if element.get(inkscape_label) in {
                "Départements Métropolitains",
                "Encarts Départements d'Outre-Mer",
            }:
                return True
        return False

    matches = [
        element
        for element_id, element in id_index.items()
        if element_id == target_id or element_id.startswith(f"{target_id} ")
        if is_in_department_layer(element)
    ]
    if len(matches) != 1:
        raise ValueError(
            f"SVG target {target_id} matched {len(matches)} elements; expected exactly one"
        )
    return matches[0]


def prepare_svg_template(
    template_path: Path,
    target_ids: set[str],
    hidden_layer_labels: set[str],
    neutral_color: str,
    target_companions: dict[str, list[str]],
) -> bytes:
    tree = ET.parse(template_path)
    root = tree.getroot()
    id_index = {element.get("id"): element for element in root.iter() if element.get("id")}
    parent_index = {child: parent for parent in root.iter() for child in parent}

    inkscape_label = "{http://www.inkscape.org/namespaces/inkscape}label"
    for element in root.iter():
        if element.get(inkscape_label) in {
            "Départements Métropolitains",
            "Encarts Départements d'Outre-Mer",
        }:
            declarations = [
                declaration
                for declaration in element.get("style", "").split(";")
                if declaration and not declaration.startswith("display:")
            ]
            declarations.append("display:inline")
            element.set("style", ";".join(declarations))
    for element in list(root.iter()):
        if element.get(inkscape_label) in hidden_layer_labels:
            parent_index[element].remove(element)
    for target_id in target_ids:
        set_svg_fill(find_svg_target(id_index, parent_index, target_id), neutral_color)
        for companion_id in target_companions.get(target_id, []):
            set_svg_fill(id_index[companion_id], neutral_color)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def highlight_svg_template(
    template: bytes,
    destination: Path,
    target_ids: list[str],
    highlight_color: str,
    target_companions: dict[str, list[str]],
) -> None:
    root = ET.fromstring(template)
    id_index = {element.get("id"): element for element in root.iter() if element.get("id")}
    parent_index = {child: parent for parent in root.iter() for child in parent}
    for target_id in target_ids:
        set_svg_fill(find_svg_target(id_index, parent_index, target_id), highlight_color)
        for companion_id in target_companions.get(target_id, []):
            set_svg_fill(id_index[companion_id], highlight_color)
    ET.ElementTree(root).write(destination, encoding="utf-8", xml_declaration=True)


def subdivision_output_row(
    subdivision: dict[str, str],
    config: dict,
    sort_key: str,
    filename: str,
    source_url: str,
    with_parent: bool,
) -> dict[str, str]:
    output_row = {
        "sort_key": sort_key,
        "country_code": config["country_code"],
        "country_native": config["country_native"],
        "country_english": config["country_english"],
        "subdivision_native": subdivision["subdivision_native"],
        "subdivision_english": english_if_different(
            subdivision["subdivision_native"], subdivision["subdivision_english"]
        ),
        "subdivision_type_native": subdivision["subdivision_type_native"],
        "subdivision_type_english": subdivision["subdivision_type_english"],
        "capital_native": subdivision["capital_native"],
        "capital_english": english_if_different(
            subdivision["capital_native"], subdivision["capital_english"]
        ),
        "subdivision_code": subdivision["subdivision_code"],
    }
    if with_parent:
        output_row.update({
            "parent_subdivision_native": subdivision["parent_subdivision_native"],
            "parent_subdivision_english": english_if_different(
                subdivision["parent_subdivision_native"],
                subdivision["parent_subdivision_english"],
            ),
            "parent_subdivision_type_native": subdivision["parent_subdivision_type_native"],
            "parent_subdivision_type_english": subdivision["parent_subdivision_type_english"],
            "parent_subdivision_code": subdivision["parent_subdivision_code"],
        })
    output_row.update({
        "map_image": f'<img src="{filename}" />',
        "map_filename": filename,
        "map_source": source_url,
    })
    return output_row


def generate_template_subdivision_set(
    source_path: Path,
    output_path: Path,
    media_dir: Path,
    config: dict,
    family_order: int,
    family_code: str,
    media_kind: str,
    with_parent: bool = False,
) -> list[dict[str, str]]:
    subdivisions = read_csv(source_path)
    all_target_ids = {
        target_id
        for subdivision in subdivisions
        for target_id in subdivision["map_target_ids"].split(";")
    }
    template = prepare_svg_template(
        source_path.parent / config["map_template"],
        all_target_ids,
        set(config["map_hidden_layers"]),
        config["neutral_color"],
        config.get("map_target_companions", {}),
    )
    rows = []
    for row_number, subdivision in enumerate(subdivisions, start=1):
        filename = subdivision_filename(
            config["country_code"], subdivision["subdivision_code"], media_kind
        )
        highlight_svg_template(
            template,
            media_dir / filename,
            subdivision["map_target_ids"].split(";"),
            config["highlight_color"],
            config.get("map_target_companions", {}),
        )
        rows.append(subdivision_output_row(
            subdivision,
            config,
            row_sort_key(config, family_order, family_code, row_number),
            filename,
            config["map_source"],
            with_parent,
        ))
    write_csv(output_path, rows)
    return rows


def generate_subdivision_set(
    source_path: Path,
    output_path: Path,
    cache_dir: Path,
    media_dir: Path,
    config: dict,
    seed_dir: Path | None,
    family_order: int,
    family_code: str,
    media_kind: str,
    with_parent: bool = False,
) -> tuple[list[dict[str, str]], dict[str, Path]]:
    country_code = config["country_code"]
    rows: list[dict[str, str]] = []
    cached_by_code: dict[str, Path] = {}
    subdivisions = read_csv(source_path)
    missing_files = []
    for subdivision in subdivisions:
        code_suffix = subdivision["subdivision_code"].split("-", 1)[1].lower()
        cache_prefix = (
            subdivision["subdivision_code"].split("-", 1)[0].lower()
            if media_kind == "subdivision"
            else media_kind
        )
        if not (cache_dir / f"{cache_prefix}-{code_suffix}-locator.svg").exists():
            missing_files.append(subdivision["commons_file"])
    download_urls = commons_download_urls(missing_files)

    for row_number, subdivision in enumerate(subdivisions, start=1):
        code_suffix = subdivision["subdivision_code"].split("-", 1)[1].lower()
        cache_prefix = (
            subdivision["subdivision_code"].split("-", 1)[0].lower()
            if media_kind == "subdivision"
            else media_kind
        )
        cached_svg = cache_dir / f"{cache_prefix}-{code_suffix}-locator.svg"
        if not cached_svg.exists() and seed_dir:
            seed = seed_dir / cached_svg.name
            if seed.exists():
                shutil.copy2(seed, cached_svg)
        svg_url, source_url = commons_urls(subdivision["commons_file"])
        if not cached_svg.exists():
            download(download_urls.get(subdivision["commons_file"], svg_url), cached_svg)
            time.sleep(config.get("download_delay", 1))
        cached_by_code[subdivision["subdivision_code"]] = cached_svg

        filename = subdivision_filename(country_code, subdivision["subdivision_code"], media_kind)
        shutil.copy2(cached_svg, media_dir / filename)
        output_row = {
            "sort_key": row_sort_key(config, family_order, family_code, row_number),
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
            "capital_native": subdivision["capital_native"],
            "capital_english": english_if_different(
                subdivision["capital_native"],
                subdivision["capital_english"],
            ),
            "subdivision_code": subdivision["subdivision_code"],
        }
        if with_parent:
            output_row.update({
                "parent_subdivision_native": subdivision["parent_subdivision_native"],
                "parent_subdivision_english": english_if_different(
                    subdivision["parent_subdivision_native"],
                    subdivision["parent_subdivision_english"],
                ),
                "parent_subdivision_type_native": subdivision["parent_subdivision_type_native"],
                "parent_subdivision_type_english": subdivision["parent_subdivision_type_english"],
                "parent_subdivision_code": subdivision["parent_subdivision_code"],
            })
        output_row.update({
            "map_image": f'<img src="{filename}" />',
            "map_filename": filename,
            "map_source": source_url,
        })
        rows.append(output_row)
    write_csv(output_path, rows)
    return rows, cached_by_code


def generate_country(data_dir: Path, seed_dir: Path | None) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    config = json.loads((data_dir / "map.json").read_text(encoding="utf-8"))
    country_code = config["country_code"]
    cache_dir = PROJECT_DIR / "cache" / country_code
    country_output_dir = OUTPUT_DIR / country_code
    media_dir = country_output_dir / "media"
    cache_dir.mkdir(parents=True, exist_ok=True)
    media_dir.mkdir(parents=True, exist_ok=True)
    clear_country_media(media_dir, country_code)

    parent_source = data_dir / "subdivisions_with_parent.csv"
    parent_rows: list[dict[str, str]] = []
    if "map_template" in config:
        subdivision_rows = generate_template_subdivision_set(
            data_dir / "subdivisions.csv",
            country_output_dir / config["subdivision_output"],
            media_dir,
            config,
            family_order=1,
            family_code="SUB1",
            media_kind="subdivision",
        )
        cached_by_code: dict[str, Path] = {}
        if parent_source.exists():
            parent_rows = generate_template_subdivision_set(
                parent_source,
                country_output_dir / config["subdivision_parent_output"],
                media_dir,
                config,
                family_order=3,
                family_code="HIST",
                media_kind="subdivision-old",
                with_parent=True,
            )
    else:
        subdivision_rows, cached_by_code = generate_subdivision_set(
            data_dir / "subdivisions.csv",
            country_output_dir / config["subdivision_output"],
            cache_dir,
            media_dir,
            config,
            seed_dir,
            family_order=1,
            family_code="SUB1",
            media_kind="subdivision",
        )
        if parent_source.exists():
            parent_rows, _ = generate_subdivision_set(
                parent_source,
                country_output_dir / config["subdivision_parent_output"],
                cache_dir,
                media_dir,
                config,
                seed_dir,
                family_order=3,
                family_code="HIST",
                media_kind="subdivision-old",
                with_parent=True,
            )

    city_rows: list[dict[str, str]] = []
    city_source = data_dir / "cities.csv"
    if city_source.exists():
        base_svg = cached_by_code[config["base_subdivision_code"]]
        cities = read_csv(city_source)
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
        write_csv(country_output_dir / "cities.csv", city_rows)
    return subdivision_rows + parent_rows, city_rows


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
