# France source notes

This directory contains the project-maintained source data for France. Row
order is deliberate and must remain append-only after the corresponding notes
have been imported into Anki.

## Current and former regions

`regions.csv` contains the current regions. `regions-old.csv` contains the 21
former metropolitan regions that have a meaningful transition to a current
region; unchanged Corsica and the overseas regions are intentionally omitted
from the historical file. The regional structure and transition relationships
were curated from standard references including
<https://en.wikipedia.org/wiki/Regions_of_France>.

The five overseas regions remain in `regions.csv`, but their map fields are
blank in generated output because the source map's small overseas insets do not
provide useful world context.

## Départements

`departments.csv` contains all 101 départements in official code order. Names,
codes, current-region relationships, and chefs-lieux come from INSEE's 2026
Code officiel géographique:
<https://www.insee.fr/fr/information/8740222>.

The 96 metropolitan departments generate individual locator maps. The five
overseas rows remain in the CSV with blank map fields. Because the four central
Paris-area departments are illegibly small at full-country scale, the cards for
Paris, Hauts-de-Seine, Seine-Saint-Denis, and Val-de-Marne include a circular
magnified inset centered on their true location.

## Cities

`cities.csv` is a curated study list rather than an official statistical
dataset. It includes the metropolitan current regional capitals, nine former
regional capitals, and selected prominent non-capitals. Latitude and longitude
values are project-maintained city-center coordinates used for map placement.

## Map source and license

The exact locator-map originals are checked into `maps/` so regeneration does
not depend on future Commons revisions:

- `departments-base-source.svg`: [France location map-Departements-2015.svg](https://commons.wikimedia.org/wiki/File:France_location_map-Departements-2015.svg),
  SHA-256 `d69f3976884beb20ffa5778a71d579a5612f396a750754ed80596f2d1a1695a5`.
- `regions-current-base-source.svg`: [France location map-Regions-2016.svg](https://commons.wikimedia.org/wiki/File:France_location_map-Regions-2016.svg),
  SHA-256 `b0c4cb7f5acaa8b90bce566ffbb73ce61d6f3b6523b07649e0e26e124873cdd6`.
- `regions-old-base-source.svg`: [France location map-Regions-2015.svg](https://commons.wikimedia.org/wiki/File:France_location_map-Regions-2015.svg),
  SHA-256 `6be3698747cddc9c2475a2ccf1ca815a54d9fde92aee7ff7a002c34dd6d928fb`.

All three use the same WGS84 equirectangular locator projection and published
geographic limits: 5°48′ W to 10° E and 41° N to 51°30′ N. Current-region and
city maps use the 2016 base, historical-region maps use the 2015 base, and
department maps use the department base.

`departments-fill-source.svg` is a project-derived fill-geometry source made
from the exact department locator above. Its grouped department masks were
created by flood-filling that map's native boundary cells and are placed beneath
the original boundary layers. This lets current regions, former regions, and
departments share precisely aligned highlights without mixing geometry from a
different map. City maps use the unmodified current-region base plus markers.

These Commons sources permit reuse under their stated attribution/share-alike
licenses (including CC BY-SA 4.0). Generated maps are modified derivatives.
Public distribution must credit the source authors, link the applicable source
and license, identify the modifications, and satisfy share-alike requirements.

## Generated material

Run `python3 scripts/generate.py FRA` from the repository root. Source files in
this directory are tracked; generated `.acsv` files go to `outputs/FRA`, and rebuildable
media goes to `outputs/FRA/media`.
