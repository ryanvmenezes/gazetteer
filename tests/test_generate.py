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

    def test_gazetteer_filenames(self):
        self.assertEqual(
            generate.subdivision_filename("DEU", "DE-BY"),
            "gaz-deu-subdivision-by.svg",
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


if __name__ == "__main__":
    unittest.main()
