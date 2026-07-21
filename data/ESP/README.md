# Spain source data

Spain generates first-level cards for the 17 autonomous communities and
second-level cards for the 50 provinces. Ceuta and Melilla are omitted because
they are autonomous cities rather than autonomous communities or provinces.

Names and capitals were compiled from:

- [Autonomous communities of Spain](https://en.wikipedia.org/wiki/Autonomous_communities_of_Spain)
- [Provinces of Spain](https://en.wikipedia.org/wiki/Provinces_of_Spain)

Where a subdivision or city has a distinct co-official local-language name,
the native field records the Spanish form first and the local form second—for
example `Cataluña / Catalunya`, `País Vasco / Euskadi`,
`Navarra / Nafarroa`, `Islas Baleares / Illes Balears`, and
`Comunidad Valenciana / Comunitat Valenciana`. English fields provide the
familiar English name when it differs.

The checked-in locator maps are preserved copies of these Wikimedia Commons
files:

- [Spain location map.svg](https://commons.wikimedia.org/wiki/File:Spain_location_map.svg)
- [Spain location map with provinces.svg](https://commons.wikimedia.org/wiki/File:Spain_location_map_with_provinces.svg)

The generator uses the first as the clean autonomous-community and city
canvas. It uses exact fill geometry from the second for autonomous-community
and province highlights. City coordinates are projected using the geographic
bounds documented on the Wikimedia map page: 44.4° N, 34.7° N, 9.9° W, and
4.8° E.

The Canary Islands remain in both subdivision datasets, but their map fields
are blank and no Canary SVGs are generated. Canary capital cities are omitted
from `cities.csv` because the mainland projection cannot place them usefully.

The city dataset begins with the 16 mapped autonomous-community capitals and
then adds Bilbao, Gijón, La Coruña, Vigo, Málaga, Granada, Córdoba, Alicante,
Cartagena, Salamanca, Tarragona, Cádiz, Jerez de la Frontera, Gerona, Albacete,
Badajoz, Cáceres, Ibiza, and Huesca. New cities remain appended at the bottom
so existing city sort keys stay stable.

Province source rows retain every capital. In the generated province import,
the capital fields are blank when the capital has the same bilingual display
name as the province; only the 10 nonmatching or expanded capital names remain.
