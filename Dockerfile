FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .
COPY config ./config

CMD ["python", "-c", "from smarttrading.config import load_settings; print(load_settings().model_dump_json(indent=2))"]

FROM runtime AS test
COPY tests ./tests
RUN pip install --no-cache-dir '.[dev]'
CMD ["sh", "-c", "pytest && ruff check . && ruff format --check . && mypy"]
