.PHONY: access.token
access.token:
	@touch $@
	docker run --rm --env-file .env -v ./$@:/access.token:rw ghcr.io/dmingn/feedly-token-fetcher:latest -v -o /access.token
