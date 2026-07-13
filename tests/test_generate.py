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
            output = Path(directory) / "subdivisions.csv"
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
            output = root / "output.csv"
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
            generate.subdivision_filename("DEU", "DE-BY"),
            "gaz-deu-subdivision-by.svg",
        )
        self.assertEqual(
            generate.subdivision_filename("FRA", "FR-42", "subdivision-old"),
            "gaz-fra-subdivision-old-42.svg",
        )
        self.assertEqual(
            generate.subdivision_filename(
                "FRA", "FR-26", "subdivision-department"
            ),
            "gaz-fra-subdivision-department-26.svg",
        )
        self.assertEqual(generate.city_filename("DEU", "Köln"), "gaz-deu-city-koeln.svg")

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
            generate.add_city_markers(source, output, config, [city], city)
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


if __name__ == "__main__":
    unittest.main()
