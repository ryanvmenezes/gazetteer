#!/usr/bin/env python3
"""Generate country-scoped Anki text imports and SVG locator maps."""

from __future__ import annotations

import argparse
import copy
import csv
import json
import re
import shutil
import subprocess
import time
import unicodedata
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_DIR / "data"
OUTPUT_DIR = PROJECT_DIR / "outputs"
COMMONS_REDIRECT = "https://commons.wikimedia.org/wiki/Special:Redirect/file"
COMMONS_FILE_PAGE = "https://commons.wikimedia.org/wiki/File:"
USER_AGENT = "GazetteerAnki/0.2 (personal study deck)"

ET.register_namespace("", "http://www.w3.org/2000/svg")
ET.register_namespace("inkscape", "http://www.inkscape.org/namespaces/inkscape")
ET.register_namespace("sodipodi", "http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd")
ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")


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
    replacements = str.maketrans({
        "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
        "æ": "ae", "œ": "oe",
    })
    value = unicodedata.normalize(
        "NFKD", value.lower().translate(replacements)
    ).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", value).strip("-")


def media_name_slug(value: str) -> str:
    """Use the Spanish-first portion of bilingual display names for media."""
    return slug(value.split(" / ", 1)[0])


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
    subdivision_native: str,
    media_group: str = "subdivision",
) -> str:
    return (
        f"gazz_{country_code.lower()}_{media_group}_"
        f"{media_name_slug(subdivision_native)}.svg"
    )


def city_filename(country_code: str, city_native: str) -> str:
    return f"gazz_{country_code.lower()}_city_{media_name_slug(city_native)}.svg"


def clear_country_media(media_dir: Path, country_code: str) -> None:
    for pattern in (
        f"gaz-{country_code.lower()}-*.svg",
        f"gazz_{country_code.lower()}_*.svg",
    ):
        for path in media_dir.glob(pattern):
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


def type_english_value(value: str, config: dict) -> str:
    value = config.get("subdivision_type_english_overrides", {}).get(
        value, value
    )
    return "" if value in config.get("subdivision_type_english_omissions", []) else value


def subdivision_type_english_value(subdivision: dict[str, str], config: dict) -> str:
    return type_english_value(subdivision["subdivision_type_english"], config)


def parent_subdivision_type_native_value(
    subdivision: dict[str, str], config: dict
) -> str:
    value = subdivision["parent_subdivision_type_native"]
    return config.get("parent_subdivision_type_native_overrides", {}).get(
        value, value
    )


def project_city(latitude: float, longitude: float, projection: dict[str, float]) -> tuple[float, float]:
    lon_fraction = ((longitude - projection["longitude_min"]) /
                    (projection["longitude_max"] - projection["longitude_min"]))
    lat_fraction = ((projection["latitude_max"] - latitude) /
                    (projection["latitude_max"] - projection["latitude_min"]))
    x = projection["x_min"] + lon_fraction * (projection["x_max"] - projection["x_min"])
    y = projection["y_min"] + lat_fraction * (projection["y_max"] - projection["y_min"])
    return x, y


def city_marker(city: dict[str, str], config: dict, highlighted: bool) -> str:
    if city.get("map_x") and city.get("map_y"):
        x, y = float(city["map_x"]), float(city["map_y"])
    else:
        x, y = project_city(float(city["latitude"]), float(city["longitude"]), config["projection"])
    if highlighted:
        halo_radius = config.get("highlighted_marker_halo_radius", 18)
        marker_radius = config.get("highlighted_marker_radius", 11)
        marker_stroke_width = config.get("highlighted_marker_stroke_width", 2)
        return (
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{halo_radius}" fill="#FFFFFF" opacity="0.95"/>'
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{marker_radius}" fill="{config["marker_color"]}" '
            f'stroke="#333333" stroke-width="{marker_stroke_width}"/>'
        )
    context_radius = config.get("context_marker_radius", 4.5)
    context_stroke_width = config.get("context_marker_stroke_width", 1.25)
    return (
        f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{context_radius}" fill="#FFFFFF" '
        f'opacity="0.85" stroke="#333333" stroke-width="{context_stroke_width}"/>'
    )


def add_city_markers(
    source: Path | bytes,
    destination: Path,
    config: dict,
    cities: list[dict[str, str]],
    highlighted_city: dict[str, str],
) -> None:
    svg = (
        source.decode("utf-8")
        if isinstance(source, bytes)
        else source.read_text(encoding="utf-8")
    )
    svg = svg.replace(config["highlight_color"], config["neutral_color"])
    other_markers = [
        city_marker(city, config, highlighted=False)
        for city in cities
        if city is not highlighted_city
    ]
    highlighted_marker = city_marker(highlighted_city, config, highlighted=True)
    marker = (
        f'\n<g id="gaz-city-markers" aria-label="City locations">'
        f'{highlighted_marker}{"".join(other_markers)}</g>\n'
    )
    svg, replacements = re.subn(
        r"</(?:[A-Za-z_][A-Za-z0-9_.-]*:)?svg>\s*$",
        lambda match: f"{marker}{match.group(0)}",
        svg,
    )
    if replacements != 1:
        raise ValueError(f"Expected one closing SVG tag; found {replacements}")
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

    generated_target = id_index.get(f"gaz-target-{target_id}")
    if generated_target is not None:
        return generated_target

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
    if not matches:
        matches = [
            element
            for element_id, element in id_index.items()
            if element_id == target_id
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
    fill_overlay_path: Path | None = None,
    fill_overlay_transform: str | None = None,
    fill_overlay_before_id: str | None = None,
) -> bytes:
    tree = ET.parse(template_path)
    root = tree.getroot()
    if fill_overlay_path:
        overlay_root = ET.parse(fill_overlay_path).getroot()
        overlay_id_index = {
            element.get("id"): element
            for element in overlay_root.iter()
            if element.get("id")
        }
        overlay_parent_index = {
            child: parent for parent in overlay_root.iter() for child in parent
        }
        overlay = ET.Element(
            "{http://www.w3.org/2000/svg}g",
            {
                "id": "gaz-fill-targets",
                "{http://www.inkscape.org/namespaces/inkscape}label":
                    "Départements Métropolitains",
            },
        )
        if fill_overlay_transform:
            overlay.set("transform", fill_overlay_transform)
        overlay_ids = list(target_ids)
        overlay_ids.extend(
            companion_id
            for target_id in target_ids
            for companion_id in target_companions.get(target_id, [])
        )
        for target_id in overlay_ids:
            source_element = (
                overlay_id_index[target_id]
                if target_id in overlay_id_index
                else find_svg_target(
                    overlay_id_index, overlay_parent_index, target_id
                )
            )
            target_element = copy.deepcopy(source_element)
            for parent in list(target_element.iter()):
                for child in list(parent):
                    if child.tag.rsplit("}", 1)[-1] == "text":
                        parent.remove(child)
            target_wrapper = ET.Element(
                "{http://www.w3.org/2000/svg}g",
                {"id": f"gaz-target-{target_id}"},
            )
            target_wrapper.append(target_element)
            overlay.append(target_wrapper)

        inkscape_label = "{http://www.inkscape.org/namespaces/inkscape}label"
        overlay_parent = root
        insert_at = len(root)
        if fill_overlay_before_id:
            before_element = next(
                (
                    element for element in root.iter()
                    if element.get("id") == fill_overlay_before_id
                ),
                None,
            )
            if before_element is None:
                raise ValueError(
                    f"SVG overlay insertion target {fill_overlay_before_id} not found"
                )
            overlay_parent = next(
                parent for parent in root.iter() if before_element in list(parent)
            )
            insert_at = list(overlay_parent).index(before_element)
        else:
            for index, element in enumerate(root):
                if (
                    element.get(inkscape_label) == "Lakes"
                    or element.get("fill", "").upper() == "#C8EBFF"
                ):
                    insert_at = index
                    break
        overlay_parent.insert(insert_at, overlay)
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
    inset: dict | None = None,
) -> None:
    root = ET.fromstring(template)
    id_index = {element.get("id"): element for element in root.iter() if element.get("id")}
    parent_index = {child: parent for parent in root.iter() for child in parent}
    for target_id in target_ids:
        target = find_svg_target(id_index, parent_index, target_id)
        set_svg_fill(target, highlight_color)
        parent = parent_index.get(target)
        if parent is not None:
            parent.remove(target)
            parent.append(target)
        for companion_id in target_companions.get(target_id, []):
            companion = id_index[companion_id]
            set_svg_fill(companion, highlight_color)
            parent = parent_index.get(companion)
            if parent is not None:
                parent.remove(companion)
                parent.append(companion)
    if inset and set(target_ids) & set(inset["target_ids"]):
        add_svg_magnifier(root, inset)
    ET.ElementTree(root).write(destination, encoding="utf-8", xml_declaration=True)


def add_svg_magnifier(root: ET.Element, inset: dict) -> None:
    """Overlay a clipped, enlarged copy of the map at its geographic location."""
    svg_namespace = "http://www.w3.org/2000/svg"
    source_x = float(inset["source_x"])
    source_y = float(inset["source_y"])
    center_x = float(inset.get("center_x", source_x))
    center_y = float(inset.get("center_y", source_y))
    radius = float(inset["radius"])
    scale = float(inset["scale"])

    excluded_tags = {"defs", "metadata", "namedview"}
    map_children = [
        copy.deepcopy(child)
        for child in root
        if child.tag.rsplit("}", 1)[-1] not in excluded_tags
    ]

    defs = next(
        (
            child
            for child in root
            if child.tag == f"{{{svg_namespace}}}defs"
        ),
        None,
    )
    if defs is None:
        defs = ET.Element(f"{{{svg_namespace}}}defs")
        root.insert(0, defs)
    clip_path = ET.SubElement(
        defs,
        f"{{{svg_namespace}}}clipPath",
        {"id": "gaz-map-inset-clip"},
    )
    ET.SubElement(
        clip_path,
        f"{{{svg_namespace}}}circle",
        {"cx": str(center_x), "cy": str(center_y), "r": str(radius)},
    )

    ET.SubElement(
        root,
        f"{{{svg_namespace}}}circle",
        {
            "id": "gaz-map-inset-halo",
            "cx": str(center_x),
            "cy": str(center_y),
            "r": str(radius),
            "fill": inset.get("halo_color", "#FFFFFF"),
            "stroke": inset.get("halo_color", "#FFFFFF"),
            "stroke-width": str(inset.get("halo_width", 18)),
        },
    )
    clipped_group = ET.SubElement(
        root,
        f"{{{svg_namespace}}}g",
        {
            "id": "gaz-map-inset",
            "clip-path": "url(#gaz-map-inset-clip)",
        },
    )
    enlarged_map = ET.SubElement(
        clipped_group,
        f"{{{svg_namespace}}}g",
        {
            "transform": (
                f"translate({center_x} {center_y}) scale({scale}) "
                f"translate({-source_x} {-source_y})"
            )
        },
    )
    enlarged_map.extend(map_children)
    ET.SubElement(
        root,
        f"{{{svg_namespace}}}circle",
        {
            "id": "gaz-map-inset-border",
            "cx": str(center_x),
            "cy": str(center_y),
            "r": str(radius),
            "fill": "none",
            "stroke": inset.get("border_color", "#646464"),
            "stroke-width": str(inset.get("border_width", 6)),
        },
    )


def subdivision_output_row(
    subdivision: dict[str, str],
    config: dict,
    sort_key: str,
    filename: str,
    with_parent: bool,
) -> dict[str, str]:
    capital_native = subdivision["capital_native"]
    if (
        config.get("blank_redundant_capitals")
        and capital_native == subdivision["subdivision_native"]
    ):
        capital_native = ""
    capital_english = (
        english_if_different(
            subdivision["capital_native"], subdivision["capital_english"]
        )
        if capital_native
        else ""
    )
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
        "subdivision_type_english": subdivision_type_english_value(
            subdivision, config
        ),
        "capital_native": capital_native,
        "capital_english": capital_english,
        "subdivision_code": subdivision["subdivision_code"],
    }
    if with_parent:
        output_row.update({
            "parent_subdivision_native": subdivision["parent_subdivision_native"],
            "parent_subdivision_english": english_if_different(
                subdivision["parent_subdivision_native"],
                subdivision["parent_subdivision_english"],
            ),
            "parent_subdivision_type_native": parent_subdivision_type_native_value(
                subdivision, config
            ),
            "parent_subdivision_type_english": type_english_value(
                subdivision["parent_subdivision_type_english"], config
            ),
            "parent_subdivision_code": subdivision["parent_subdivision_code"],
        })
    output_row.update({
        "map_image": f'<img src="{filename}" />' if filename else "",
        "map_filename": filename,
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
    omitted_target_ids = set(config.get("map_omitted_target_ids", []))
    neutral_subdivisions = read_csv(
        source_path.parent / config.get("map_neutral_source", source_path.name)
    )
    all_target_ids = {
        target_id
        for subdivision in neutral_subdivisions
        for target_id in subdivision["map_target_ids"].split(";")
        if target_id not in omitted_target_ids
    }
    template = prepare_svg_template(
        source_path.parent / config["map_template"],
        all_target_ids,
        set(config["map_hidden_layers"]),
        config["neutral_color"],
        config.get("map_target_companions", {}),
        source_path.parent / config["map_fill_overlay"]
        if config.get("map_fill_overlay")
        else None,
        config.get("map_fill_overlay_transform"),
        config.get("map_fill_overlay_before_id"),
    )
    rows = []
    for row_number, subdivision in enumerate(subdivisions, start=1):
        target_ids = subdivision["map_target_ids"].split(";")
        if set(target_ids).issubset(omitted_target_ids):
            rows.append(subdivision_output_row(
                subdivision,
                config,
                row_sort_key(config, family_order, family_code, row_number),
                "",
                with_parent,
            ))
            continue
        filename = subdivision_filename(
            config["country_code"], subdivision["subdivision_native"], media_kind
        )
        highlight_svg_template(
            template,
            media_dir / filename,
            target_ids,
            config["highlight_color"],
            config.get("map_target_companions", {}),
            config.get("map_inset"),
        )
        rows.append(subdivision_output_row(
            subdivision,
            config,
            row_sort_key(config, family_order, family_code, row_number),
            filename,
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
        svg_url, _ = commons_urls(subdivision["commons_file"])
        if not cached_svg.exists():
            download(download_urls.get(subdivision["commons_file"], svg_url), cached_svg)
            time.sleep(config.get("download_delay", 1))
        cached_by_code[subdivision["subdivision_code"]] = cached_svg

        filename = subdivision_filename(
            country_code, subdivision["subdivision_native"], media_kind
        )
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
            "subdivision_type_english": subdivision_type_english_value(
                subdivision, config
            ),
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
                "parent_subdivision_type_native": parent_subdivision_type_native_value(
                    subdivision, config
                ),
                "parent_subdivision_type_english": type_english_value(
                    subdivision["parent_subdivision_type_english"], config
                ),
                "parent_subdivision_code": subdivision["parent_subdivision_code"],
            })
        output_row.update({
            "map_image": f'<img src="{filename}" />',
            "map_filename": filename,
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
    media_dir.mkdir(parents=True, exist_ok=True)
    clear_country_media(media_dir, country_code)
    if "map_template" in config:
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
    else:
        cache_dir.mkdir(parents=True, exist_ok=True)

    subdivision_source = data_dir / config.get(
        "subdivision_source", "subdivisions.csv"
    )
    parent_source = data_dir / config.get(
        "subdivision_parent_source", "subdivisions_with_parent.csv"
    )
    children_source = data_dir / config.get(
        "subdivision_children_source", "subdivisions_children.csv"
    )
    parent_rows: list[dict[str, str]] = []
    children_rows: list[dict[str, str]] = []
    if "map_template" in config:
        subdivision_rows = generate_template_subdivision_set(
            subdivision_source,
            country_output_dir / config["subdivision_output"],
            media_dir,
            config,
            family_order=1,
            family_code="SUB1",
            media_kind=config.get("subdivision_media_group", "subdivision"),
        )
        cached_by_code: dict[str, Path] = {}
        current_subdivisions = read_csv(subdivision_source)
        current_target_ids = {
            target_id
            for subdivision in current_subdivisions
            for target_id in subdivision["map_target_ids"].split(";")
            if target_id not in set(config.get("map_omitted_target_ids", []))
        }
        city_fill_overlay = config.get(
            "city_map_fill_overlay", config.get("map_fill_overlay")
        )
        city_base_svg = prepare_svg_template(
            data_dir / config.get("city_map_template", config["map_template"]),
            current_target_ids if city_fill_overlay else set(),
            set(config["map_hidden_layers"]),
            config["neutral_color"],
            config.get("map_target_companions", {}),
            data_dir / city_fill_overlay if city_fill_overlay else None,
            config.get("map_fill_overlay_transform"),
            config.get("map_fill_overlay_before_id"),
        )
        if parent_source.exists():
            parent_config = dict(config)
            parent_config["map_template"] = config.get(
                "parent_map_template", config["map_template"]
            )
            parent_config["map_source"] = config.get(
                "parent_map_source", config["map_source"]
            )
            parent_rows = generate_template_subdivision_set(
                parent_source,
                country_output_dir / config["subdivision_parent_output"],
                media_dir,
                parent_config,
                family_order=3,
                family_code="HIST",
                media_kind=config.get("parent_media_group", "subdivision-old"),
                with_parent=True,
            )
        if children_source.exists():
            children_config = dict(config)
            children_config["map_template"] = config.get(
                "children_map_template", config["map_template"]
            )
            children_config["map_source"] = config.get(
                "children_map_source", config["map_source"]
            )
            children_config["map_neutral_source"] = config.get(
                "children_map_neutral_source",
                config.get("map_neutral_source", children_source.name),
            )
            children_config["map_hidden_layers"] = [
                label
                for label in config["map_hidden_layers"]
                if label not in set(config.get("children_map_visible_layers", []))
            ]
            children_config["map_target_companions"] = {
                **config.get("map_target_companions", {}),
                **config.get("children_map_target_companions", {}),
            }
            children_config["map_inset"] = config.get("children_map_inset")
            children_config["blank_redundant_capitals"] = config.get(
                "children_blank_redundant_capitals", False
            )
            children_config["map_fill_overlay"] = config.get(
                "children_map_fill_overlay", config.get("map_fill_overlay")
            )
            children_config["map_fill_overlay_before_id"] = config.get(
                "children_map_fill_overlay_before_id",
                config.get("map_fill_overlay_before_id"),
            )
            children_rows = generate_template_subdivision_set(
                children_source,
                country_output_dir / config["subdivision_children_output"],
                media_dir,
                children_config,
                family_order=4,
                family_code="SUB2",
                media_kind=config.get(
                    "children_media_group", "subdivision-department"
                ),
                with_parent=True,
            )
    else:
        subdivision_rows, cached_by_code = generate_subdivision_set(
            subdivision_source,
            country_output_dir / config["subdivision_output"],
            cache_dir,
            media_dir,
            config,
            seed_dir,
            family_order=1,
            family_code="SUB1",
            media_kind=config.get("subdivision_media_group", "subdivision"),
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
                media_kind=config.get("parent_media_group", "subdivision-old"),
                with_parent=True,
            )
        if children_source.exists():
            children_rows, _ = generate_subdivision_set(
                children_source,
                country_output_dir / config["subdivision_children_output"],
                cache_dir,
                media_dir,
                config,
                seed_dir,
                family_order=4,
                family_code="SUB2",
                media_kind=config.get(
                    "children_media_group", "subdivision-department"
                ),
                with_parent=True,
            )

    city_rows: list[dict[str, str]] = []
    city_source = data_dir / "cities.csv"
    if city_source.exists():
        base_svg = (
            city_base_svg
            if "map_template" in config
            else cached_by_code[config["base_subdivision_code"]]
        )
        cities = read_csv(city_source)
        omitted_cities = set(config.get("map_omitted_cities", []))
        mapped_cities = [
            city for city in cities if city["city_native"] not in omitted_cities
        ]
        for row_number, city in enumerate(cities, start=1):
            filename = ""
            if city["city_native"] not in omitted_cities:
                filename = city_filename(country_code, city["city_native"])
                add_city_markers(
                    base_svg, media_dir / filename, config, mapped_cities, city
                )
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
                "map_image": f'<img src="{filename}" />' if filename else "",
                "map_filename": filename,
            })
        write_csv(
            country_output_dir / config.get("city_output", "cities.acsv"),
            city_rows,
        )
    return subdivision_rows + parent_rows + children_rows, city_rows


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
    map_count = 0
    for data_dir in country_directories(selected):
        subdivisions, cities = generate_country(data_dir, seed_dir)
        subdivision_count += len(subdivisions)
        city_count += len(cities)
        map_count += len(list(
            (OUTPUT_DIR / data_dir.name / "media").glob(
                f"gazz_{data_dir.name.lower()}_*.svg"
            )
        ))

    print(
        f"Wrote {subdivision_count} subdivisions, {city_count} cities, "
        f"and {map_count} maps to country folders in {OUTPUT_DIR}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("countries", nargs="*", help="Optional ISO alpha-3 country codes, e.g. DEU FRA")
    parser.add_argument("--seed-dir", type=Path, help="Optional directory containing downloaded SVGs")
    args = parser.parse_args()
    generate(args.countries or None, args.seed_dir)


if __name__ == "__main__":
    main()
