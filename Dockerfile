FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
COPY schemas ./schemas
COPY config ./config
COPY postgres/initdb/002_corrida_rules.sql postgres/initdb/003_driver_identity.sql postgres/initdb/004_race_control.sql postgres/initdb/005_stream_projections.sql postgres/initdb/006_race_scenarios.sql postgres/initdb/007_pneu_chuva.sql postgres/initdb/008_pause_race.sql postgres/initdb/009_renomear_piloto_rafael_batista.sql ./postgres/initdb/
RUN pip install --no-cache-dir .

CMD ["python", "-m", "racestream.interfaces.producer"]
