FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
COPY schemas ./schemas
RUN pip install --no-cache-dir .

CMD ["python", "-m", "racestream.interfaces.producer"]