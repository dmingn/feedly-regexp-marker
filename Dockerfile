FROM python:3.10-slim AS builder

WORKDIR /feedly_regexp_marker

RUN apt-get update && \
    apt-get install -y build-essential && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN pip install poetry

COPY pyproject.toml poetry.lock ./

RUN poetry config virtualenvs.create false && \
    poetry install --no-dev

FROM python:3.10-slim

WORKDIR /feedly_regexp_marker

COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages

COPY feedly_regexp_marker ./feedly_regexp_marker

ENTRYPOINT ["python", "-m", "feedly_regexp_marker"]
