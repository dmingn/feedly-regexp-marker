FROM python:3.10-slim

WORKDIR /feedly_regexp_marker

RUN pip install poetry

COPY pyproject.toml poetry.lock ./

RUN poetry install --no-dev

COPY feedly_regexp_marker ./feedly_regexp_marker

ENTRYPOINT ["poetry", "run", "python", "-m", "feedly_regexp_marker"]
