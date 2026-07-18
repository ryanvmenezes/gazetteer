.DEFAULT_GOAL := help

PYTHON ?= python3
COUNTRIES ?=
ANKI_PROFILE ?= Ryan
ANKI_MEDIA ?= $(HOME)/Library/Application Support/Anki2/$(ANKI_PROFILE)/collection.media

.PHONY: help generate generate-deu generate-fra test check copy-media refresh-anki

help:
	@printf '%s\n' \
		'make generate             Generate every country' \
		'make generate COUNTRIES=DEU' \
		'                          Generate selected ISO3 countries (space-separated)' \
		'make generate-deu         Generate Germany' \
		'make generate-fra         Generate France' \
		'make test                 Run the test suite' \
		'make check                Generate everything, then run the tests' \
		'make copy-media           Copy all generated media to Anki' \
		'make refresh-anki         Generate, test, and copy media to Anki' \
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

test:
	$(PYTHON) -m unittest discover -s tests

check: generate
	$(PYTHON) -m unittest discover -s tests

copy-media:
	scripts/copy_media_to_anki.sh "$(ANKI_MEDIA)"

refresh-anki: check
	scripts/copy_media_to_anki.sh "$(ANKI_MEDIA)"
