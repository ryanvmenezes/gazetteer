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
overseas rows remain in the CSV with blank map fields. Department maps retain
the Paris–Petite Couronne inset so Paris, Hauts-de-Seine,
Seine-Saint-Denis, and Val-de-Marne remain distinguishable.

## Cities

`cities.csv` is a curated study list rather than an official statistical
dataset. It includes the metropolitan current regional capitals, nine former
regional capitals, and selected prominent non-capitals. Latitude and longitude
values are project-maintained city-center coordinates used for map placement.

## Map source and license

All French maps are derived locally from `maps/regions-template-source.svg`, a
checked-in copy of Wikimedia Commons file `France régionale.svg` by Nilstilar:
<https://commons.wikimedia.org/wiki/File:France_r%C3%A9gionale.svg>.

The source is licensed CC BY-SA 4.0. Generated maps are modified derivatives:
the generator removes unused layers, neutralizes department fills, combines
departments into current or former regions, and adds city markers. Public
distribution must credit the author, link the source and CC BY-SA 4.0 license,
identify the modifications, and satisfy the share-alike requirement.

## Generated material

Run `python3 scripts/generate.py FRA` from the repository root. Source files in
this directory are tracked; generated CSVs go to `outputs/FRA`, and rebuildable
media goes to `outputs/FRA/media`.
