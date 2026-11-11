SHELL := /bin/bash
UV ?= uv
PNPM ?= pnpm
PORT ?= 3000

.PHONY: demo install scrape export dev build preview test test-python test-web typecheck e2e clean-build

# One command: scrape + export + build + serve + open the browser.
demo:
	PORT=$(PORT) ./scripts/demo.sh

install:
	$(UV) sync
	$(PNPM) --dir web install --frozen-lockfile

scrape:
	$(UV) run price-monitor scrape --simulate --ensure-history 14

export:
	$(UV) run price-monitor export

dev:
	$(PNPM) --dir web dev

build:
	$(PNPM) --dir web build

preview:
	$(PNPM) --dir web preview

test: test-python test-web

test-python:
	$(UV) run pytest

test-web:
	$(PNPM) --dir web test

typecheck:
	$(PNPM) --dir web typecheck

e2e:
	PLAYWRIGHT_CHANNEL=$${PLAYWRIGHT_CHANNEL:-chrome} $(PNPM) --dir web e2e

clean-build:
	rm -rf web/.next web/out
