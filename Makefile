.DEFAULT_GOAL := help

PYTHON ?= python3
COUNTRIES ?=
ANKI_PROFILE ?= Ryan
ANKI_MEDIA ?= $(HOME)/Library/Application Support/Anki2/$(ANKI_PROFILE)/collection.media

.PHONY: help generate generate-deu generate-fra generate-esp test check copy-media refresh-anki anki-inspect anki-import anki-import-dry-run

help:
	@printf '%s\n' \
		'make generate             Generate every country' \
		'make generate COUNTRIES=DEU' \
		'                          Generate selected ISO3 countries (space-separated)' \
		'make generate-deu         Generate Germany' \
		'make generate-fra         Generate France' \
		'make generate-esp         Generate Spain' \
		'make test                 Run the test suite' \
		'make check                Generate everything, then run the tests' \
		'make copy-media           Copy all generated media to Anki' \
		'make refresh-anki         Generate, test, and copy media to Anki' \
		'make anki-inspect         List Anki decks, note types, and fields' \
		'make anki-import          Add or update notes through AnkiConnect' \
		'make anki-import-dry-run  Preview AnkiConnect additions and updates' \
		'' \
		'Anki defaults to profile "$(ANKI_PROFILE)". Override it with:' \
		'make copy-media ANKI_PROFILE=OtherProfile' \
		'make copy-media ANKI_MEDIA="/path/to/collection.media"'

generate:
	$(PYTHON) scripts/generate.py $(COUNTRIES)

generate-deu:
	$(PYTHON) scripts/generate.py DEU

generate-fra:
	$(PYTHON) scripts/generate.py FRA

generate-esp:
	$(PYTHON) scripts/generate.py ESP

test:
	$(PYTHON) -m unittest discover -s tests

check: generate
	$(PYTHON) -m unittest discover -s tests

copy-media:
	scripts/copy_media_to_anki.sh "$(ANKI_MEDIA)"

refresh-anki: check
	scripts/copy_media_to_anki.sh "$(ANKI_MEDIA)"

anki-inspect:
	$(PYTHON) scripts/import_to_anki.py --inspect

anki-import: check
	$(PYTHON) scripts/import_to_anki.py $(COUNTRIES)

anki-import-dry-run: check
	$(PYTHON) scripts/import_to_anki.py --dry-run $(COUNTRIES)
