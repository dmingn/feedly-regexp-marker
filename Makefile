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
