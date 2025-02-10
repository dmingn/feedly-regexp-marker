.PHONY: lint
lint: flake8 mypy

.PHONY: flake8
flake8:
	@poetry run flake8 feedly_regexp_marker

.PHONY: mypy
mypy:
	@poetry run mypy .

.PHONY: access.token
access.token:
	@touch $@
	docker run --rm --env-file .env -v ./$@:/access.token:rw ghcr.io/dmingn/feedly-token-fetcher:latest -v -o /access.token

DATE := $(shell date +%Y.%m.%d)
EXISTING_TAGS := $(shell gh release list --json tagName -q '.[] | .tagName' | grep '^$(DATE)')

.PHONY: bump-version
bump-version:
	@N=1; \
	while echo "$(EXISTING_TAGS)" | grep -q "^$(DATE).$$$${N}"; do \
		N=$$(($$N + 1)); \
	done; \
	TAG="$(DATE).$$N"; \
	echo "Bumping version to $$TAG"; \
	poetry version $$TAG
