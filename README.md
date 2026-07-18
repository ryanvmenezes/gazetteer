# Gazetteer

Gazetteer builds Anki-ready geography datasets and locator maps one country at
a time. Generated media filenames begin with `gaz-`, making them easy to find
in Anki's `collection.media` directory.

This project was developed with ChatGPT/Codex, building on
[previous work](https://github.com/ryanvmenezes/gazetteer-old) by the 
repository author.

Gazetteer produces a separate set of Anki imports for each country. Every
country currently has:

- `outputs/<ISO3>/subdivisions--<topic>.csv`: identify a subdivision and review its capital.
- `outputs/<ISO3>/cities.csv`: identify a marked city and review its subdivision.

Countries can add further imports for country-specific material, such as a
historical subdivision mapping. SVG files for each country live alongside its
CSVs in `outputs/<ISO3>/media/`.

Subdivision filenames use `<note-type>--<topic>.csv`. The text before `--`
identifies the Anki note type, while the text after it identifies the country's
topic. Germany therefore emits `subdivisions--states.csv`. France emits
`subdivisions--regions.csv` and
`subdivisions-with-parent--regions-old.csv`; the latter adds reusable
`parent_subdivision_*` fields for mapping each former region to its current
region. France also emits `subdivisions-with-parent--departments.csv`, using
the same parent schema to map each second-level département to its current
region.

Generated CSVs begin with Anki-native `#separator` and `#columns` metadata.
Anki uses these lines to configure the import and display field names without
creating a note from an ordinary header row.

## Generate Deck Data

The common commands are available through the `Makefile`:

```bash
make generate                       # Generate every country
make generate COUNTRIES=DEU         # Generate one or more ISO3 countries
make test                           # Run the test suite
make check                          # Generate everything and run the tests
make copy-media                     # Copy generated media to the default Anki profile
make refresh-anki                   # Generate, test, and copy media
make help                           # Show all available commands
```

The Anki media destination defaults to the `Ryan` profile on macOS. To use another profile or path:

```bash
make copy-media ANKI_PROFILE=OtherProfile
make copy-media ANKI_MEDIA="/path/to/collection.media"
```

The underlying generator can also be run directly:

```bash
python3 scripts/generate.py
```

The command generates every country under `data/`. To build selected countries,
pass their ISO alpha-3 codes, for example `python3 scripts/generate.py DEU`.
Template-backed countries build directly from tracked SVGs under
`data/<ISO3>/maps/` and write their CSVs and Anki media to `outputs/<ISO3>/`.
Generated media is ignored by Git; generated CSVs are tracked.

France uses three checked-in Wikimedia locator maps: a department map, a
current-region map, and a 1982–2015 region map. Each output family therefore
shows only its appropriate boundary system. A checked-in fill source derived
from the exact department locator provides aligned shapes for highlighting; the
generator places those fills beneath each locator map's original boundary
layer. It never downloads a separate locator for every row.

The French city deck uses the current-region locator as its neutral base. It
contains every metropolitan current regional capital, nine former regional
capitals, and a small set of additional prominent cities. Overseas cities are
omitted because their context dots are not useful at the inset-map scale. Both
current and former regional capitals have a blank `not_capital` value so
historical-region cards can omit redundant capital questions; only cities that
were neither kind of capital use `true`.

French maps omit the overseas inset layer because those small locator boxes do
not provide useful world context. The five overseas rows remain in the current
region CSV, but their `map_image` and `map_filename` fields are blank and no
corresponding SVGs are generated. The historical-with-parent file omits those
unchanged regions and Corsica because they have no transition to quiz. The
source URL remains for attribution.

To copy all generated media into Anki:

```bash
scripts/copy_media_to_anki.sh "/path/to/Anki2/Profile/collection.media"
```

## Choosing cities

`data/<ISO3>/cities.csv` lists the capitals and selected prominent non-capitals
included in that country's deck. The generator emits city cards for every
listed city so the deck can test where capitals and other notable cities sit
within their subdivisions.

A practical selection rule is:

1. Include every national and first-level subdivision capital.
2. Add the largest or most culturally important non-capitals.
3. Add cities that clarify easily confused regions or subdivision boundaries.
4. Keep the first deck small, then add cities after the existing set is easy.

Each city has latitude and longitude in the source CSV. The generator places
those coordinates on the country's neutral Wikimedia locator-map canvas, adds
hollow dots for every listed context city, and highlights the current city as
the only filled red dot. Country-specific map and projection configuration
lives in `data/<ISO3>/map.json`.

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

Give source CSVs literate, country-specific names and declare their schema roles
in `map.json`. Germany uses `states.csv`; France uses `regions.csv`,
`regions-old.csv`, and `departments.csv`. Add `cities.csv` when the country has
a city deck, and give the country a unique `country_order`. In source CSVs, include
English labels even when they match the native label; generated CSVs leave
duplicate English city, subdivision, and capital fields blank. Subdivision source rows
also include native and English type labels, such as `Land` / `State` or
`Freistaat` / `Free State`. The generator is data-driven, so no Python changes
should be needed for countries whose Wikimedia locator maps use the same
pattern.

## Country data sources

Country-specific source provenance, selection decisions, transformations, and
licensing notes live alongside the source data:

- [Germany source notes](data/DEU/README.md)
- [France source notes](data/FRA/README.md)

## GitHub workflow

Commit source data, generator changes, and generated CSVs after each country.
Generated media stays out of Git because it can be rebuilt. The generator still
supports a cache for legacy per-row Commons locator downloads, but the current
template-backed countries do not create one.
