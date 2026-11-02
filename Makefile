# mr-comic-smith developer commands. TypeScript targets run only for packages that exist.
UV ?= uv
PY_EXTRAS ?= --all-extras
TS_PACKAGES := $(wildcard web/studio/package-lock.json reader/package-lock.json integrations/pi/package-lock.json)

.PHONY: install lint format typecheck test test-int visual coverage smoke e2e check-versions build \
        studio-build studio-dev package licenses docs clean record-fixtures update-goldens

install:
	$(UV) sync $(PY_EXTRAS)
	@for p in $(dir $(TS_PACKAGES)); do (cd $$p && npm ci) || exit 1; done

lint:
	$(UV) run ruff check .
	$(UV) run ruff format --check .
	$(UV) run python scripts/check_em_dash.py
	$(UV) run lint-imports
	@for p in $(dir $(TS_PACKAGES)); do (cd $$p && npm run --if-present lint) || exit 1; done

format:
	$(UV) run ruff format .
	$(UV) run ruff check --fix .

typecheck:
	$(UV) run mypy
	@for p in $(dir $(TS_PACKAGES)); do (cd $$p && npm run --if-present typecheck) || exit 1; done

test:
	$(UV) run pytest
	@for p in $(dir $(TS_PACKAGES)); do (cd $$p && npm run --if-present test) || exit 1; done

test-int:
	$(UV) run pytest -m integration -o addopts="-ra --strict-markers"

visual:
	$(UV) run pytest tests/visual -o addopts="-ra --strict-markers"

coverage:
	$(UV) run pytest --cov --cov-report=term --cov-report=json:coverage.json --cov-report=xml
	$(UV) run python scripts/check-coverage.py coverage.json .coverage-thresholds.toml
	@for p in $(dir $(TS_PACKAGES)); do (cd $$p && npm run --if-present coverage) || exit 1; done

smoke:
	bash tests/smoke/smoke.sh

e2e: studio-build
	cd tests/e2e && npm ci && npx playwright test

check-versions:
	./scripts/check-versions.sh

studio-build:
	cd web/studio && npm ci && npm run build
	find comic_smith/server/static -mindepth 1 ! -name .gitkeep -delete
	cp -R web/studio/dist/. comic_smith/server/static/

studio-dev:
	COMIC_SMITH_ENV=dev COMIC_SMITH_LLM=fake COMIC_SMITH_VISION=fake COMIC_SMITH_IMAGE_BACKEND=mock \
	  $(UV) run mr-comic-smith studio --no-browser & \
	  (cd web/studio && npm run dev)

build:
	$(UV) build
	@for p in $(dir $(TS_PACKAGES)); do (cd $$p && npm run --if-present build) || exit 1; done

package: studio-build
	$(UV) build

licenses:
	$(UV) run python scripts/check-licenses.py

docs:
	$(UV) run mkdocs build --strict

record-fixtures:
	$(UV) run python scripts/record-fixtures.py

update-goldens:
	./scripts/update-goldens.sh

clean:
	rm -rf dist build .pytest_cache .mypy_cache .ruff_cache htmlcov coverage.json coverage.xml
