FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
COPY schemas ./schemas
COPY postgres/initdb/002_corrida_rules.sql postgres/initdb/003_driver_identity.sql postgres/initdb/004_race_control.sql ./postgres/initdb/
RUN pip install --no-cache-dir .

CMD ["python", "-m", "racestream.interfaces.producer"]