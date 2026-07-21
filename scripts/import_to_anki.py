#!/usr/bin/env python3
"""Add or update generated Gazetteer notes through AnkiConnect."""

from __future__ import annotations

import argparse
import csv
import json
import urllib.error
import urllib.request
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_DIR / "outputs"
DEFAULT_CONFIG = PROJECT_DIR / "anki-import.json"
DEFAULT_URL = "http://127.0.0.1:8765"


class AnkiConnectError(RuntimeError):
    pass


def request(action: str, params: dict | None = None, url: str = DEFAULT_URL):
    payload = json.dumps(
        {"action": action, "version": 6, "params": params or {}}
    ).encode("utf-8")
    try:
        with urllib.request.urlopen(
            urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
            )
        ) as response:
            result = json.load(response)
    except urllib.error.URLError as error:
        raise AnkiConnectError(
            f"Could not connect to AnkiConnect at {url}. Is desktop Anki running?"
        ) from error
    if result.get("error"):
        raise AnkiConnectError(f'{action}: {result["error"]}')
    return result.get("result")


def read_acsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    columns = next(
        (
            line.removeprefix("#columns:").split(",")
            for line in lines
            if line.startswith("#columns:")
        ),
        None,
    )
    if not columns:
        raise ValueError(f"Missing #columns metadata in {path}")
    rows = list(
        csv.DictReader(
            (line for line in lines if line and not line.startswith("#")),
            fieldnames=columns,
        )
    )
    if any(not row.get("sort_key") for row in rows):
        raise ValueError(f"Every row in {path} must have a sort_key")
    return columns, rows


def inspect_anki(url: str) -> None:
    decks = request("deckNames", url=url)
    models = request("modelNames", url=url)
    print("Decks:")
    for deck in decks:
        print(f"  {deck}")
    print("\nNote types:")
    for model in models:
        fields = request("modelFieldNames", {"modelName": model}, url)
        print(f'  {model}: {", ".join(fields)}')


def load_config(path: Path) -> dict:
    if not path.exists():
        raise ValueError(
            f"Missing {path}. Start Anki and run `make anki-inspect`, then "
            "create the import mapping from anki-import.example.json."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def find_existing_notes(
    rows: list[dict[str, str]], model: str, url: str
) -> dict[str, int]:
    existing = {}
    for row in rows:
        sort_key = row["sort_key"]
        note_ids = request("findNotes", {"query": f'sort_key:"{sort_key}"'}, url)
        if len(note_ids) > 1:
            raise ValueError(f"Multiple Anki notes have sort_key {sort_key}")
        if note_ids:
            existing[sort_key] = note_ids[0]
    if existing:
        note_info = request("notesInfo", {"notes": list(existing.values())}, url)
        wrong_models = [
            info["noteId"]
            for info in note_info
            if info["modelName"] != model
        ]
        if wrong_models:
            raise ValueError(
                f'Existing notes {wrong_models} do not use configured note type "{model}"'
            )
    return existing


def validate_model(model: str, columns: list[str], url: str) -> list[str]:
    model_fields = request("modelFieldNames", {"modelName": model}, url)
    missing = set(model_fields) - set(columns)
    if missing:
        raise ValueError(
            f'The generated import is missing fields required by note type "{model}": '
            f'{", ".join(sorted(missing))}'
        )
    return model_fields


def sync_import(
    path: Path,
    deck: str,
    model: str,
    country_code: str,
    url: str,
    dry_run: bool,
) -> tuple[int, int]:
    columns, rows = read_acsv(path)
    model_fields = validate_model(model, columns, url)
    existing = find_existing_notes(rows, model, url)
    added = updated = 0
    tags = ["gazetteer", f"gazetteer::{country_code.lower()}"]

    if not dry_run:
        request("createDeck", {"deck": deck}, url)
    for row in rows:
        fields = {field: row[field] for field in model_fields}
        note_id = existing.get(row["sort_key"])
        if note_id:
            updated += 1
            if dry_run:
                continue
            request(
                "updateNoteFields",
                {"note": {"id": note_id, "fields": fields}},
                url,
            )
            request("addTags", {"notes": [note_id], "tags": " ".join(tags)}, url)
            card_ids = request("findCards", {"query": f"nid:{note_id}"}, url)
            if card_ids:
                request("changeDeck", {"cards": card_ids, "deck": deck}, url)
        else:
            added += 1
            if dry_run:
                continue
            request(
                "addNote",
                {
                    "note": {
                        "deckName": deck,
                        "modelName": model,
                        "fields": fields,
                        "tags": tags,
                        "options": {"allowDuplicate": False},
                    }
                },
                url,
            )
    return added, updated


def sync_media(country_dir: Path, url: str, dry_run: bool) -> int:
    media = sorted((country_dir / "media").glob("gazz_*.svg"))
    if not dry_run:
        for path in media:
            request(
                "storeMediaFile",
                {"filename": path.name, "path": str(path), "deleteExisting": True},
                url,
            )
    return len(media)


def selected_countries(config: dict, requested: list[str]) -> list[str]:
    configured = config.get("countries", {})
    if not requested:
        return list(configured)
    missing = set(requested) - set(configured)
    if missing:
        raise ValueError(
            f'No Anki import configuration for: {", ".join(sorted(missing))}'
        )
    return requested


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("countries", nargs="*", help="ISO3 country codes")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--inspect", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    try:
        if args.inspect:
            inspect_anki(args.url)
            return
        config = load_config(args.config)
        for country_code in selected_countries(config, args.countries):
            country = config["countries"][country_code]
            country_dir = OUTPUT_DIR / country_code
            for filename, model in country["imports"].items():
                added, updated = sync_import(
                    country_dir / filename,
                    country["deck"],
                    model,
                    country_code,
                    args.url,
                    args.dry_run,
                )
                print(f"{country_code}/{filename}: {added} add, {updated} update")
            media_count = sync_media(country_dir, args.url, args.dry_run)
            print(f"{country_code}/media: {media_count} files")
        if args.dry_run:
            print("Dry run: no Anki changes were made.")
    except (AnkiConnectError, OSError, ValueError) as error:
        parser.exit(1, f"error: {error}\n")


if __name__ == "__main__":
    main()
