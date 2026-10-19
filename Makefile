PYTHON ?= python3.12
OUTPUT ?=
OWNED_PORT ?=
.PHONY: help setup-public setup-maintainer check-sources console-build console-test core-test test public-build benchmark-check dv02-check db-health
help:
	$(PYTHON) tools/dev.py --help
setup-public:
	$(PYTHON) -m pip install -e aevora_core -e console
setup-maintainer: setup-public
	ORDERFLOW_BUILD_PROFILE=MAINTAINER_ONLY $(PYTHON) -m pip install -e .
check-sources:
	$(PYTHON) tools/dev.py check-sources
console-build:
	$(PYTHON) tools/dev.py build-console
console-test:
	$(PYTHON) tools/dev.py test-console
core-test:
	$(PYTHON) tools/dev.py test-core --output "$(OUTPUT)"
test:
	$(PYTHON) tools/dev.py test-maintainer --output "$(OUTPUT)" --owned-port "$(OWNED_PORT)"
public-build:
	$(PYTHON) tools/dev.py public-build --output "$(OUTPUT)"
benchmark-check:
	$(PYTHON) tools/dev.py benchmark-check --output "$(OUTPUT)"
dv02-check:
	$(PYTHON) tools/dev.py dv02-check --output "$(OUTPUT)"
db-health:
	$(PYTHON) tools/dev.py db-health
