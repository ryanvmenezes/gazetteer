import importlib.util
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "generate.py"
SPEC = importlib.util.spec_from_file_location("gazetteer_generate", SCRIPT)
generate = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(generate)


class GenerateTests(unittest.TestCase):
    def test_gazetteer_filenames(self):
        self.assertEqual(
            generate.subdivision_filename("DEU", "DE-BY"),
            "gaz-deu-subdivision-by.svg",
        )
        self.assertEqual(generate.city_filename("DEU", "Köln"), "gaz-deu-city-koeln.svg")

    def test_sort_keys_preserve_country_and_row_order(self):
        config = {"country_code": "DEU", "country_order": 1}
        self.assertEqual(generate.country_sort_key(config), "01_DEU")
        self.assertEqual(generate.row_sort_key(config, 7), "01_DEU_007")

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
        self.assertIn('r="13" fill="#FFFFFF"', rendered)
        self.assertIn('cx="60.00" cy="30.00" r="4.5" fill="#FFFFFF"', rendered)
        self.assertIn('stroke-width="1.25"', rendered)
        self.assertIn('<path fill="#FEFEE9"/>', rendered)


if __name__ == "__main__":
    unittest.main()
