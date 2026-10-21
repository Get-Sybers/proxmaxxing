SHELL := /usr/bin/env bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := conform
MAKEFLAGS += --warn-undefined-variables --no-builtin-rules
SANITY_ENV ?= sanity-py3.13-2.21
.PHONY: help
help:
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-12s %s\n", $$1, $$2}'
.PHONY: config
config: ## copy the configuration template into place (never overwrites)
	cd inventory/example && find . -type f | while read -r f; do \
	[ -e "../$$f" ] || { mkdir -p "../$$(dirname "$$f")" && cp "$$f" "../$$f" && echo "config: created inventory/$${f#./}"; }; \
	done
	@echo "config: edit inventory/hosts.yml and inventory/group_vars/all/*.yml — replace every CHANGE-ME"
.PHONY: deps
deps:
	python3 -m pip install --quiet -r test-requirements.txt
	ansible-galaxy collection install -r requirements.yml
.PHONY: lint
lint:
	prek run --all-files --show-diff-on-failure
.PHONY: pins
pins:
	python3 scripts/check_pins.py --resolve-git
.PHONY: sanity
sanity:
	tox --ansible -e $(SANITY_ENV) --conf tox-ansible.ini
.PHONY: unit
unit:
	tox --ansible -e $(subst sanity,unit,$(SANITY_ENV)) --conf tox-ansible.ini
.PHONY: molecule
molecule:
	molecule test --all
.PHONY: changelog
changelog:
	antsibull-changelog lint
.PHONY: build
build:
	ansible-galaxy collection build --force --output-path dist/
.PHONY: conform
conform: lint pins sanity molecule changelog build
	@echo "conform: OK"
.PHONY: upgrade
upgrade:
	python3 scripts/upgrade_pins.py
	$(MAKE) conform
