# Germany source notes

This directory contains the project-maintained source data for Germany. Row
order is deliberate and must remain append-only after the corresponding notes
have been imported into Anki.

## States

`states.csv` contains Germany's 16 first-level subdivisions, their ISO 3166-2
codes, German and English names, constitutional type labels, and capitals.
Names, types, capitals, and codes were assembled from standard German
administrative geography references and are maintained directly in the CSV.

Each row identifies its state shape in `map_target_ids`. All subdivision and
city maps are generated from the single preserved Wikimedia Commons base map
at `maps/states-base-source.svg` and its project-derived, highlightable template
at `maps/states-template-source.svg`.

The base is an exact download of
<https://commons.wikimedia.org/wiki/File:Germany_location_map.svg> (SHA-256
`93149b5a79c838f3e8b7099ea84fa61fb1c7d766370967cc7b317f1ac70df9f0`).
It is an equirectangular map by NordNordWest with documented limits of 55.1° N,
47.2° N, 5.5° E, and 15.5° E. The derived template adds fillable state shapes
from the former
[per-state Commons locator maps](https://commons.wikimedia.org/wiki/Category:SVG_locator_maps_of_states_in_Germany_(location_map_scheme))
by TUBS without changing the preserved base. Generated maps link back to the
base map's Commons page for attribution. Before distributing a deck publicly,
preserve the authors, licenses, and modification notices for both sources.

## Cities

`cities.csv` is a curated study list rather than an official statistical
dataset. It contains every state capital plus selected prominent non-capitals.
The latitude and longitude values are project-maintained city-center
coordinates used to place markers; they are not intended as authoritative
geodetic data.

City maps use the neutralized shared template as their base. The projection in
`map.json` follows the geographic limits documented on the Commons source page;
marker styling also lives there.

## Generated material

Run `python3 scripts/generate.py DEU` from the repository root. Source files in
this directory are tracked, generated CSVs go to `outputs/DEU`, and rebuildable
media goes to `outputs/DEU/media`. Germany's tracked template is read directly,
so generation does not create a cache directory.
