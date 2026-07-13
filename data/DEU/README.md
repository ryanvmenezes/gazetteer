# Germany source notes

This directory contains the project-maintained source data for Germany. Row
order is deliberate and must remain append-only after the corresponding notes
have been imported into Anki.

## States

`states.csv` contains Germany's 16 first-level subdivisions, their ISO 3166-2
codes, German and English names, constitutional type labels, and capitals.
Names, types, capitals, and codes were assembled from standard German
administrative geography references and are maintained directly in the CSV.

Each row names its Wikimedia Commons locator file in `commons_file`. The
generator resolves that filename through Wikimedia Commons, retains the file's
Commons page in generated attribution data, and uses the downloaded SVG as the
state map. The relevant map family can be browsed at
<https://commons.wikimedia.org/wiki/Category:SVG_locator_maps_of_states_in_Germany_(location_map_scheme)>.

Commons files may have different authors and licenses. Before distributing a
deck publicly, follow the source link associated with each generated map and
preserve its required author, license, and modification notices.

## Cities

`cities.csv` is a curated study list rather than an official statistical
dataset. It contains every state capital plus selected prominent non-capitals.
The latitude and longitude values are project-maintained city-center
coordinates used to place markers; they are not intended as authoritative
geodetic data.

City maps use a neutralized state locator as their base. Projection calibration
and marker styling live in `map.json`.

## Generated material

Run `python3 scripts/generate.py DEU` from the repository root. Source files in
this directory are tracked; downloaded SVGs go to `cache/DEU`, generated CSVs
go to `outputs/DEU`, and rebuildable media goes to `outputs/DEU/media`.
