# Gazetteer

Gazetteer builds Anki-ready geography datasets and locator maps one country at
a time. Generated media filenames begin with `gaz-`, making them easy to find
in Anki's `collection.media` directory.

Gazetteer always produces two growing Anki imports across all countries:

- `gazetteer_subdivisions.csv`: identify a subdivision and review its capital.
- `gazetteer_cities.csv`: identify a marked city and review its subdivision.

## Generate Deck Data

```bash
python3 scripts/generate.py
```

The command generates every country under `data/`. To build selected countries,
pass their ISO alpha-3 codes, for example `python3 scripts/generate.py DEU`.
It downloads Wikimedia Commons locator SVGs into `cache/` and writes the two
consolidated CSVs plus Anki media to `outputs/`. The cache and generated
outputs are deliberately excluded from Git; the source data and generator are
the reproducible project.

To copy all generated media into Anki:

```bash
scripts/copy_media_to_anki.sh "/path/to/Anki2/Profile/collection.media"
```

## Choosing cities

`data/DEU/cities.csv` begins with every state capital plus Köln. A useful
next tier would be nationally prominent non-capitals such as Frankfurt am Main,
Leipzig, Dortmund, Essen, Nürnberg, Heidelberg, and Freiburg im Breisgau.

A practical selection rule is:

1. Include every national and first-level subdivision capital.
2. Add the largest or most culturally important non-capitals.
3. Add cities that clarify easily confused regions or state boundaries.
4. Keep the first deck small, then add cities after the existing set is easy.

Each city has latitude and longitude in the source CSV. The generator projects
those coordinates onto the same Wikimedia locator-map canvas used by the state
cards, neutralizes the highlighted state, adds hollow dots for every city in the
country, and highlights the current city as the only filled red dot.
Country-specific projection calibration lives in `data/DEU/map.json`.

## Sort order

Every row has a `country_sort_key` such as `01_DEU` and a unique `sort_key`
such as `01_DEU_007`. The sequence number comes first in the Anki sort key so
countries follow `country_order` instead of sorting alphabetically. Row order
follows the source CSV, so it also remains deliberate and stable.

## Adding a country

Create `data/<ISO3>/subdivisions.csv`, `cities.csv`, and `map.json` following
`data/DEU`. Give the country a unique `country_order`. The generator is
data-driven, so no Python changes should be needed for countries whose
Wikimedia locator maps use the same pattern.

## GitHub workflow

Commit source data and generator changes after each country. Generated files
stay out of Git because they can be rebuilt; attach a zip to a release if you
want downloadable Anki bundles.
