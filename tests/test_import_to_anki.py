import importlib.util
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "import_to_anki.py"
SPEC = importlib.util.spec_from_file_location("gazetteer_anki_import", SCRIPT)
anki_import = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(anki_import)


class AnkiImportTests(unittest.TestCase):
    def test_read_acsv_uses_anki_columns_metadata(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "cities.acsv"
            path.write_text(
                "#separator:Comma\n"
                "#columns:sort_key,city_native,map_image\n"
                'DEU_02_CITY_001,Berlin,"<img src=""gazz_deu_city_berlin.svg"" />"\n',
                encoding="utf-8",
            )
            columns, rows = anki_import.read_acsv(path)

        self.assertEqual(columns, ["sort_key", "city_native", "map_image"])
        self.assertEqual(rows[0]["sort_key"], "DEU_02_CITY_001")
        self.assertEqual(rows[0]["city_native"], "Berlin")
        self.assertEqual(
            rows[0]["map_image"], '<img src="gazz_deu_city_berlin.svg" />'
        )

    def test_read_acsv_requires_sort_key(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.acsv"
            path.write_text(
                "#separator:Comma\n#columns:name\nBerlin\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "sort_key"):
                anki_import.read_acsv(path)

    def test_selected_countries_validates_configuration(self):
        config = {"countries": {"DEU": {}, "FRA": {}}}
        self.assertEqual(anki_import.selected_countries(config, ["FRA"]), ["FRA"])
        with self.assertRaisesRegex(ValueError, "ESP"):
            anki_import.selected_countries(config, ["ESP"])

    def test_validate_model_allows_attribution_only_output_columns(self):
        original_request = anki_import.request
        anki_import.request = lambda *args, **kwargs: ["sort_key", "name"]
        try:
            fields = anki_import.validate_model(
                "Subdivision", ["sort_key", "name", "map_source"], "unused"
            )
        finally:
            anki_import.request = original_request

        self.assertEqual(fields, ["sort_key", "name"])


if __name__ == "__main__":
    unittest.main()
