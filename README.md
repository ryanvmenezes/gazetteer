# Gazetteer

Gazetteer builds Anki-ready geography datasets and locator maps one country at
a time. Generated media filenames begin with `gaz-`, making them easy to find
in Anki's `collection.media` directory.

Gazetteer produces a separate set of Anki imports for each country. Every
country currently has:

- `outputs/<ISO3>/subdivisions.csv`: identify a subdivision and review its capital.
- `outputs/<ISO3>/cities.csv`: identify a marked city and review its subdivision.

Countries can add further imports for country-specific material, such as a
historical subdivision mapping. SVG files for each country live alongside its
CSVs in `outputs/<ISO3>/media/`.

Generated CSVs begin with Anki-native `#separator` and `#columns` metadata.
Anki uses these lines to configure the import and display field names without
creating a note from an ordinary header row.

## Generate Deck Data

```bash
python3 scripts/generate.py
```

The command generates every country under `data/`. To build selected countries,
pass their ISO alpha-3 codes, for example `python3 scripts/generate.py DEU`.
It downloads Wikimedia Commons locator SVGs into `cache/` and writes each
country's CSVs and Anki media to `outputs/<ISO3>/`. Cache and generated media
are ignored by Git; generated CSVs are tracked.

To copy all generated media into Anki:

```bash
scripts/copy_media_to_anki.sh "/path/to/Anki2/Profile/collection.media"
```

## Choosing cities

`data/DEU/cities.csv` begins with every state capital plus selected prominent
non-capitals. The generator emits city cards for every listed city so the deck
can test where capitals and other notable cities sit within their subdivisions.

A practical selection rule is:

1. Include every national and first-level subdivision capital.
2. Add the largest or most culturally important non-capitals.
3. Add cities that clarify easily confused regions or state boundaries.
4. Keep the first deck small, then add cities after the existing set is easy.

Each city has latitude and longitude in the source CSV. The generator projects
those coordinates onto the same Wikimedia locator-map canvas used by the state
cards, neutralizes the highlighted state, adds hollow dots for every listed city
in the country, and highlights the current city as the only filled red dot.
Country-specific projection calibration lives in `data/DEU/map.json`.

## Sort order

Every row has a unique `sort_key` containing the ISO3 country code, a numbered
note-family namespace, and the source row number. For example, German
subdivision keys look like `DEU_01_SUB1_007`, while city keys look like
`DEU_02_CITY_007`. This keeps cities and subdivisions distinct when they share
an Anki deck. Additional country-specific imports can use subsequent family
numbers such as `03` and `04`.

Within each note family, row order follows the source CSV, so it remains
deliberate and stable. `country_order` controls generation order but is omitted
from keys because each country's datasets live in their own output folder.

Treat row order as append-only once a CSV has been imported into Anki. Anki uses
`sort_key` to update existing notes, so new records should be added at the end
of their source CSV regardless of alphabetical order.

## Adding a country

Create `data/<ISO3>/subdivisions.csv`, `cities.csv`, and `map.json` following
`data/DEU`. Give the country a unique `country_order`. In source CSVs, include
English labels even when they match the native label; generated CSVs leave
duplicate English city, subdivision, and capital fields blank. Subdivision source rows
also include native and English type labels, such as `Land` / `State` or
`Freistaat` / `Free State`, plus `subdivision_level` and
`parent_subdivision_code`. Generated subdivision CSVs resolve the parent code
into native and English parent names. Level-one rows leave all parent fields
blank so every country can use the same Anki note type. The generator is
data-driven, so no Python changes should be needed for countries whose
Wikimedia locator maps use the same pattern.

## GitHub workflow

Commit source data, generator changes, and generated CSVs after each country.
Generated media and cache files stay out of Git because they can be rebuilt.
