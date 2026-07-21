import importlib.util
import csv
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "generate.py"
SPEC = importlib.util.spec_from_file_location("gazetteer_generate", SCRIPT)
generate = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(generate)


class GenerateTests(unittest.TestCase):
    def test_write_csv_uses_anki_file_headers(self):
        rows = [{"sort_key": "DEU_01_SUB1_001", "name": "Bayern"}]
        with TemporaryDirectory() as directory:
            output = Path(directory) / "subdivisions.acsv"
            generate.write_csv(output, rows)
            lines = output.read_text(encoding="utf-8").splitlines()

        self.assertEqual(lines[0], "#separator:Comma")
        self.assertEqual(lines[1], "#columns:sort_key,name")
        self.assertEqual(
            next(csv.reader([lines[2]])),
            ["DEU_01_SUB1_001", "Bayern"],
        )

    def test_parent_subdivision_output_adds_reusable_parent_fields(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "subdivisions_with_parent.csv"
            output = root / "output.acsv"
            cache = root / "cache"
            media = root / "media"
            cache.mkdir()
            media.mkdir()
            source.write_text(
                "subdivision_native,subdivision_english,subdivision_type_native,"
                "subdivision_type_english,capital_native,capital_english,"
                "subdivision_code,parent_subdivision_native,"
                "parent_subdivision_english,parent_subdivision_type_native,"
                "parent_subdivision_type_english,parent_subdivision_code,commons_file\n"
                "Alsace,Alsace,Ancienne région,Former region,Strasbourg,Strasbourg,"
                "FR-42,Grand Est,Grand Est,Région actuelle,Current region,FR-GES,"
                "Alsace in France.svg\n",
                encoding="utf-8",
            )
            (cache / "subdivision-old-42-locator.svg").write_text(
                "<svg/>", encoding="utf-8"
            )
            rows, _ = generate.generate_subdivision_set(
                source,
                output,
                cache,
                media,
                {"country_code": "FRA", "country_native": "France", "country_english": "France"},
                None,
                family_order=3,
                family_code="HIST",
                media_kind="subdivision-old",
                with_parent=True,
            )

        self.assertEqual(rows[0]["sort_key"], "FRA_03_HIST_001")
        self.assertEqual(rows[0]["parent_subdivision_native"], "Grand Est")
        self.assertEqual(rows[0]["parent_subdivision_english"], "")
        self.assertEqual(rows[0]["parent_subdivision_code"], "FR-GES")

    def test_gazetteer_filenames(self):
        self.assertEqual(
            generate.subdivision_filename("DEU", "Bayern", "state"),
            "gazz_deu_state_bayern.svg",
        )
        self.assertEqual(
            generate.subdivision_filename("FRA", "Alsace", "region-old"),
            "gazz_fra_region-old_alsace.svg",
        )
        self.assertEqual(
            generate.subdivision_filename(
                "FRA", "Haute-Garonne", "departement"
            ),
            "gazz_fra_departement_haute-garonne.svg",
        )
        self.assertEqual(
            generate.city_filename("FRA", "Saint-Étienne"),
            "gazz_fra_city_saint-etienne.svg",
        )
        self.assertEqual(
            generate.city_filename("ESP", "Valencia / València"),
            "gazz_esp_city_valencia.svg",
        )
        self.assertEqual(
            generate.subdivision_filename(
                "ESP", "País Vasco / Euskadi", "community"
            ),
            "gazz_esp_community_pais-vasco.svg",
        )

    def test_sort_keys_preserve_country_and_row_order(self):
        config = {"country_code": "DEU", "country_order": 1}
        self.assertEqual(
            generate.row_sort_key(config, 1, "SUB1", 7),
            "DEU_01_SUB1_007",
        )
        self.assertEqual(
            generate.row_sort_key(config, 2, "CITY", 7),
            "DEU_02_CITY_007",
        )

    def test_english_output_is_blank_when_it_matches_native(self):
        self.assertEqual(generate.english_if_different("Berlin", "Berlin"), "")
        self.assertEqual(generate.english_if_different("Bayern", "Bavaria"), "Bavaria")

    def test_redundant_subdivision_type_english_can_be_omitted(self):
        config = {
            "subdivision_type_english_omissions": [
                "Region", "Department", "Region (1982–2015)", "Current region"
            ],
        }
        self.assertEqual(generate.type_english_value("Region", config), "")
        self.assertEqual(generate.type_english_value("Department", config), "")
        self.assertEqual(generate.type_english_value("Region (1982–2015)", config), "")
        self.assertEqual(generate.type_english_value("Current region", config), "")

    def test_not_capital_is_blank_for_capitals_and_true_for_others(self):
        self.assertEqual(generate.not_capital_value({"is_capital": "y"}), "")
        self.assertEqual(generate.not_capital_value({"is_capital": "n"}), "true")

    def test_city_markers_include_context_and_highlight_target(self):
        config = {
            "highlight_color": "#C11E1E",
            "neutral_color": "#FEFEE9",
            "marker_color": "#C11E1E",
            "projection": {
                "longitude_min": 5.0,
                "longitude_max": 15.0,
                "latitude_min": 47.0,
                "latitude_max": 55.0,
                "x_min": 0.0,
                "x_max": 100.0,
                "y_min": 0.0,
                "y_max": 80.0,
            },
        }
        cities = [
            {"latitude": "51.0", "longitude": "10.0"},
            {"latitude": "52.0", "longitude": "11.0"},
        ]
        with TemporaryDirectory() as directory:
            source = Path(directory) / "source.svg"
            output = Path(directory) / "output.svg"
            source.write_text('<svg><path fill="#C11E1E"/></svg>', encoding="utf-8")
            generate.add_city_markers(source, output, config, cities, cities[0])
            rendered = output.read_text(encoding="utf-8")

        self.assertIn('id="gaz-city-markers"', rendered)
        self.assertIn('cx="50.00" cy="40.00"', rendered)
        self.assertIn('r="18" fill="#FFFFFF"', rendered)
        self.assertIn('r="11" fill="#C11E1E"', rendered)
        self.assertIn('stroke-width="2"', rendered)
        self.assertIn('cx="60.00" cy="30.00" r="4.5" fill="#FFFFFF"', rendered)
        self.assertIn('stroke-width="1.25"', rendered)
        self.assertIn('<path fill="#FEFEE9"/>', rendered)
        self.assertLess(
            rendered.index('r="11" fill="#C11E1E"'),
            rendered.index('r="4.5" fill="#FFFFFF"'),
        )

    def test_city_markers_support_namespaced_svg_closing_tag(self):
        config = {
            "highlight_color": "#C11E1E",
            "neutral_color": "#FEFEE9",
            "marker_color": "#C11E1E",
            "projection": {
                "longitude_min": 0, "longitude_max": 1,
                "latitude_min": 0, "latitude_max": 1,
                "x_min": 0, "x_max": 1, "y_min": 0, "y_max": 1,
            },
        }
        city = {"latitude": "0.5", "longitude": "0.5"}
        with TemporaryDirectory() as directory:
            source = Path(directory) / "source.svg"
            output = Path(directory) / "output.svg"
            source.write_text("<ns0:svg></ns0:svg>", encoding="utf-8")
            generate.add_city_markers(source.read_bytes(), output, config, [city], city)
            rendered = output.read_text(encoding="utf-8")

        self.assertIn('id="gaz-city-markers"', rendered)
        self.assertTrue(rendered.endswith("</ns0:svg>"))

    def test_template_maps_reveal_department_layer_and_highlight_targets(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg"
            xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape">
          <g inkscape:label="Départements Métropolitains" style="display:none">
            <g id="67 Bas-Rhin"><path style="fill:#abcdef;fill-opacity:0.5"/></g>
            <g id="68 Haut-Rhin"><path style="fill:#abcdef"/></g>
          </g>
          <g id="overlay" inkscape:label="Régions Métropolitaines"><path/></g>
        </svg>'''
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.svg"
            output = root / "output.svg"
            source.write_text(svg, encoding="utf-8")
            template = generate.prepare_svg_template(
                source, {"67", "68"}, {"Régions Métropolitaines"}, "#FEFEE9", {}
            )
            generate.highlight_svg_template(
                template, output, ["67", "68"], "#C11E1E", {}
            )
            rendered = output.read_text(encoding="utf-8")

        self.assertIn("display:inline", rendered)
        self.assertNotIn('id="overlay"', rendered)
        self.assertEqual(rendered.count("fill:#C11E1E"), 2)
        self.assertNotIn("fill-opacity:0.5", rendered)

    def test_template_maps_support_generic_named_targets(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg">
          <g id="DE-RP"><path style="fill:#abcdef;stroke:#646464"/></g>
        </svg>'''
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.svg"
            output = root / "output.svg"
            source.write_text(svg, encoding="utf-8")
            template = generate.prepare_svg_template(
                source, {"DE-RP"}, set(), "#FEFEE9", {}
            )
            generate.highlight_svg_template(
                template, output, ["DE-RP"], "#C11E1E", {}
            )
            rendered = output.read_text(encoding="utf-8")

        self.assertIn("fill:#C11E1E", rendered)

    def test_fill_overlay_can_be_inserted_beneath_boundary_layer(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg">
          <g id="shapes"><path id="area-1" style="fill:#abcdef"/></g>
          <g id="boundaries"><path style="fill:none;stroke:#333333"/></g>
        </svg>'''
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.svg"
            source.write_text(svg, encoding="utf-8")
            template = generate.prepare_svg_template(
                source,
                {"area-1"},
                set(),
                "#FEFEE9",
                {},
                source,
                fill_overlay_before_id="boundaries",
            ).decode("utf-8")

        self.assertIn('id="gaz-target-area-1"', template)
        self.assertLess(
            template.index('id="gaz-fill-targets"'),
            template.index('id="boundaries"'),
        )

    def test_spain_sources_include_expected_rows(self):
        data = SCRIPT.parents[1] / "data" / "ESP"
        communities = generate.read_csv(data / "autonomous-communities.csv")
        provinces = generate.read_csv(data / "provinces.csv")
        cities = generate.read_csv(data / "cities.csv")

        self.assertEqual(len(communities), 17)
        self.assertEqual(len(provinces), 50)
        self.assertEqual(len(cities), 35)
        self.assertNotIn("Ceuta", {row["subdivision_native"] for row in communities})
        self.assertNotIn("Melilla", {row["subdivision_native"] for row in communities})
        community_names = {row["subdivision_native"] for row in communities}
        self.assertIn(
            "Comunidad Valenciana / Comunitat Valenciana", community_names
        )
        self.assertIn("País Vasco / Euskadi", community_names)

    def test_template_map_inset_is_limited_to_configured_targets(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg">
          <g id="75"><path style="fill:#abcdef"/></g>
          <g id="76"><path style="fill:#abcdef"/></g>
        </svg>'''
        inset = {
            "target_ids": ["75"],
            "source_x": 10,
            "source_y": 20,
            "radius": 5,
            "scale": 4,
        }
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.svg"
            inset_output = root / "inset.svg"
            plain_output = root / "plain.svg"
            source.write_text(svg, encoding="utf-8")
            template = generate.prepare_svg_template(
                source, {"75", "76"}, set(), "#FEFEE9", {}
            )
            generate.highlight_svg_template(
                template, inset_output, ["75"], "#C11E1E", {}, inset
            )
            generate.highlight_svg_template(
                template, plain_output, ["76"], "#C11E1E", {}, inset
            )
            inset_rendered = inset_output.read_text()
            plain_rendered = plain_output.read_text()

        self.assertIn('id="gaz-map-inset"', inset_rendered)
        self.assertNotIn('id="gaz-map-inset"', plain_rendered)

    def test_subdivision_output_never_includes_map_source(self):
        subdivision = {
            "subdivision_native": "Bayern",
            "subdivision_english": "Bavaria",
            "subdivision_type_native": "Freistaat",
            "subdivision_type_english": "Free State",
            "capital_native": "München",
            "capital_english": "Munich",
            "subdivision_code": "DE-BY",
        }
        config = {
            "country_code": "DEU",
            "country_native": "Deutschland",
            "country_english": "Germany",
        }

        row = generate.subdivision_output_row(
            subdivision,
            config,
            "DEU_01_SUB1_002",
            "gazz_deu_state_bayern.svg",
            False,
        )

        self.assertNotIn("map_source", row)

    def test_redundant_capital_can_be_blank_in_output(self):
        subdivision = {
            "subdivision_native": "Madrid",
            "subdivision_english": "Madrid",
            "subdivision_type_native": "Provincia",
            "subdivision_type_english": "Province",
            "capital_native": "Madrid",
            "capital_english": "Madrid",
            "subdivision_code": "ES-M",
        }
        config = {
            "country_code": "ESP",
            "country_native": "España",
            "country_english": "Spain",
            "blank_redundant_capitals": True,
        }

        row = generate.subdivision_output_row(
            subdivision, config, "ESP_04_SUB2_001", "map.svg", False
        )

        self.assertEqual(row["capital_native"], "")
        self.assertEqual(row["capital_english"], "")


if __name__ == "__main__":
    unittest.main()
