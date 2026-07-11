# Gazetteer

Gazetteer builds Anki-ready geography datasets and locator maps one country at
a time. Generated media filenames begin with `gaz-`, making them easy to find
in Anki's `collection.media` directory.

Germany currently produces two independent imports:

- `germany_subdivisions.csv`: identify a state and review its capital.
- `germany_cities.csv`: identify a marked city and review its state.

## Generate Germany

```bash
python3 scripts/generate.py germany
```

The command downloads the Wikimedia Commons state locator SVGs into `cache/`
and writes CSVs and Anki media to `outputs/germany/`. The cache and generated
outputs are deliberately excluded from Git; the source data and generator are
the reproducible project.

To copy all generated media into Anki:

```bash
scripts/copy_media_to_anki.sh "/path/to/Anki2/Profile/collection.media"
```

## Choosing cities

`data/germany/cities.csv` begins with every state capital plus Köln. A useful
next tier would be nationally prominent non-capitals such as Frankfurt am Main,
Leipzig, Dortmund, Essen, Nürnberg, Heidelberg, and Freiburg im Breisgau.

A practical selection rule is:

1. Include every national and first-level subdivision capital.
2. Add the largest or most culturally important non-capitals.
3. Add cities that clarify easily confused regions or state boundaries.
4. Keep the first deck small, then add cities after the existing set is easy.

Each city has latitude and longitude in the source CSV. The generator projects
those coordinates onto the same Wikimedia locator-map canvas used by the state
cards, neutralizes the highlighted state, and adds a red dot with a white halo.
Country-specific projection calibration lives in `data/germany/map.json`.

## Adding a country

Create `data/<country>/subdivisions.csv`, `cities.csv`, and `map.json` following
Germany's files. The generator is data-driven, so no Python changes should be
needed for countries whose Wikimedia locator maps use the same pattern.

## GitHub workflow

Commit source data and generator changes after each country. Generated files
stay out of Git because they can be rebuilt; attach a zip to a release if you
want downloadable Anki bundles.
