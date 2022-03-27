FROM python:3.10-slim

WORKDIR /feedly_regexp_marker

RUN apt-get update && \
    apt-get install -y build-essential && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN pip install poetry

COPY pyproject.toml poetry.lock ./

RUN poetry install --no-dev

COPY feedly_regexp_marker ./feedly_regexp_marker

ENTRYPOINT ["poetry", "run", "python", "-m", "feedly_regexp_marker"]
