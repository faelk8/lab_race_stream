# RaceStream Lab — Codex Engineering Instructions

## 1. Project Purpose

RaceStream Lab is an educational and portfolio-grade distributed systems and data engineering laboratory.

The platform simulates a motorsport race with 20 cars producing continuous telemetry.

The project must demonstrate realistic engineering practices while remaining reproducible on a local Ubuntu 24.04 LTS development environment.

## 2. Main Architecture

Arquitetura executada localmente:

```text
Fluxo ao vivo
Simulador -> Kafka + Schema Registry -> consumer Python -> PostgreSQL
                                      -> Kafka derivado -> FastAPI/WebSocket -> React

Fluxo histórico e analítico
Kafka -> Spark Structured Streaming -> Parquet no MinIO -> agregações Spark batch
```

Spark é o único motor de processamento distribuído adotado. O consumer Python
continua responsável pelas projeções online. ClickHouse, Iceberg, Debezium,
Kubernetes e observabilidade completa são possibilidades futuras, não serviços
presentes na stack atual.

## 3. Engineering Principles

Always prioritize:

1. correctness;
2. readability;
3. explicit contracts;
4. testability;
5. maintainability;
6. observability;
7. loose coupling;
8. reproducibility;
9. idempotency where event replay is possible;
10. incremental delivery.

Do not introduce unnecessary abstractions.

Do not claim code works without running the relevant available checks.

Do not rewrite unrelated working code.

## 4. Development Environment

Primary environment:

- Ubuntu 24.04 LTS;
- Python 3.12+;
- Docker;
- Docker Compose;
- Git;
- GitHub;
- Kubernetes in later phases.

The local environment must not require a cloud account.

## 5. Core Technologies

### Python

- Python 3.12+
- Pydantic
- FastAPI
- pytest
- asyncio
- mypy or pyright
- ruff

### Event Streaming

- Apache Kafka
- Schema Registry
- Avro as default event serialization
- Protobuf como alternativa futura, ainda não implementada

### Processamento de streams

Apache Spark Structured Streaming/PySpark é o único motor distribuído adotado.
O consumer Python mantém as projeções online da corrida. Spark arquiva o fluxo
Kafka e executa agregações batch; compare seus resultados com o consumer.

### Armazenamento de dados

- PostgreSQL: único banco relacional atualmente configurado; guarda metadados e estado operacional.
- MinIO/S3: armazenamento de objetos atualmente usado para Parquet e checkpoints Spark.
- ClickHouse: ainda não instalado ou configurado.
- Apache Iceberg: ainda não instalado ou configurado.

### Captura de alterações

- Debezium não está configurado. Os eventos da corrida são publicados diretamente pelo simulador no Kafka.

### Frontend

- React
- TypeScript
- SVG
- WebSocket

### Infrastructure

- Docker Compose first
- Kubernetes later
- Helm later

### Observability

- OpenTelemetry
- Prometheus
- Grafana

### CI/CD

- GitHub Actions

## 6. Domain Model

Main domain concepts:

- Race
- Track
- Car
- Driver
- Team
- CarState
- RaceState
- TelemetryEvent
- Lap
- Sector
- PitStop
- TireState
- FuelState
- RaceStrategy
- Incident

Each car must maintain independent state.

Simulation must support deterministic random seeds where practical.

## 7. Telemetry

Typical telemetry fields:

- event_id
- event_type
- schema_version
- event_time
- produced_at
- race_id
- car_id
- driver_id
- speed_kmh
- gear
- rpm
- fuel_kg
- car_weight_kg
- lap
- sector
- lap_distance_m
- track_progress
- race_position
- throttle
- brake
- tire_compound
- tire_age_laps
- pit_status

Track position must primarily be represented by normalized `track_progress` from 0.0 to 1.0.

Do not put frontend pixel coordinates into the core telemetry contract.

## 8. Kafka Rules

Tópicos Kafka atuais:

- `telemetry`
- `validated`
- `timing`
- `lap_completed`
- `pitstop`
- `incident`
- `control`
- `state`
- `analytics`
- `dead_letter`

Use `car_id` as key for car-specific topics where ordering is required.

Use `race_id` where aggregation by race is more appropriate.

Producers and consumers must not depend directly on one another.

## 9. Schema Registry

Every event schema must be versioned.

Default format: Avro.

Protobuf não está implementado. Só deve ser adicionado após decisão documentada sobre contrato, compatibilidade e migração; Avro é o formato atualmente utilizado.

Compatibility mode should initially be backward compatible unless a documented ADR changes that decision.

Schema evolution must be tested.

Breaking schema changes require an ADR and migration plan.

## 10. Serialization Abstraction

Business/domain code must not depend directly on Avro or Protobuf libraries.

Create serialization ports/interfaces such as:

```text
EventSerializer
EventDeserializer
SchemaRegistryClient
```

Infrastructure adapters may implement:

```text
AvroEventSerializer
ProtobufEventSerializer
```

## 11. Processamento com Spark

Apache Spark Structured Streaming/PySpark é o único motor distribuído do projeto.
Ele lê os contratos Kafka existentes e arquiva envelopes em Parquet no MinIO. Jobs
batch do Spark calculam agregados e os comparam com as projeções do consumer Python.

A projeção da corrida ao vivo continua no consumer Python e PostgreSQL. Cálculos de
domínio devem permanecer testáveis sem dependência direta das APIs do Spark sempre
que isso não exigir abstrações desnecessárias.

Os contratos de eventos ficam em `schemas/` e suas verificações em `tests/`. Os jobs
Spark ficam em `stream-processing/spark/`. Não introduza outro motor sem atualizar
o plano e as decisões do projeto.

## 12. Event Time

Streaming logic must prefer event time for race calculations.

Define:

- event-time semantics;
- allowed lateness;
- watermark policy;
- replay behavior;
- duplicate handling.

Documente regras de tempo de evento, tolerância a atraso, watermark, replay e deduplicação para o uso de Spark.

## 13. CDC

Use Debezium for changes originating from PostgreSQL when CDC becomes necessary.

Examples:

- race configuration changes;
- driver metadata updates;
- team configuration updates;
- strategy configuration changes.

CDC must not be introduced into the first MVP.

## 14. Iceberg and Object Storage

Use MinIO locally as an S3-compatible object store.

Apache Iceberg will provide analytical tables for raw, refined, and curated data.

Suggested logical layers:

```text
bronze / raw
silver / refined
gold / analytics
```

Prefer names based on semantics in the implementation, for example:

- `telemetry_raw`
- `telemetry_enriched`
- `lap_performance`
- `pitstop_analysis`

Do not make the architecture depend on the terms bronze/silver/gold.

## 15. Storage Responsibilities

PostgreSQL:

- race metadata;
- tracks;
- drivers;
- teams;
- configuration;
- operational state that requires transactions.

ClickHouse:

- recent/historical telemetry analytics;
- fast aggregate dashboard queries;
- time-series-like analytical queries.

Iceberg:

- durable analytical history;
- replay and batch analysis;
- schema evolution;
- partition evolution;
- interoperabilidade entre jobs batch e streaming do Spark.

Kafka is not the long-term analytical database.

## 16. Python Architecture

Python services should generally follow:

```text
domain/
application/
infrastructure/
interfaces/
```

Domain code must not import Kafka, FastAPI, SQLAlchemy, ClickHouse clients, Avro clients, or infrastructure frameworks.

Prefer dependency injection through constructors.

Prefer composition over inheritance.

Avoid service locators and global mutable state.

## 17. Python Quality Standards

All Python code must use:

- PEP 8;
- type hints;
- clear names;
- small cohesive functions/classes;
- SOLID where it improves maintainability;
- clean architecture boundaries.

Every public module, class, method, and function must contain Sphinx-compatible docstrings.

Example:

```python
def calculate_fuel_consumption(speed_kmh: float, throttle: float) -> float:
    """Calculate fuel consumption for one simulation step.

    :param speed_kmh: Current vehicle speed in kilometers per hour.
    :param throttle: Throttle ratio from 0.0 to 1.0.
    :return: Fuel consumed during the simulation step in kilograms.
    """
```

## 18. Testing

Required testing layers:

- unit tests;
- contract tests;
- schema compatibility tests;
- integration tests;
- end-to-end tests;
- stream engine parity tests where equivalent behavior is expected;
- load tests in later phases.

Important domain calculations requiring unit tests:

- fuel consumption;
- car weight;
- lap completion;
- sector completion;
- pit transitions;
- ranking;
- track progress;
- race position.

## 19. Paridade entre Spark e consumer

Mantenha fixtures determinísticas para comparar os agregados batch do Spark com
as análises publicadas pelo consumer Python. Compare saídas normalizadas para as
mesmas corridas e carros, e documente diferenças semânticas quando existirem.

## 20. Configuration

No important configuration should be hardcoded.

Use environment variables and versioned configuration files.

Provide `.env.example`.

Never commit secrets.

## 21. Logging and Observability

Use structured logs.

Useful context fields include:

- race_id;
- car_id;
- event_id;
- topic;
- partition;
- offset.

Do not continuously log complete telemetry payloads except in explicit debug mode.

Add traces and metrics when operationally useful.

## 22. Error Handling

Never silently suppress exceptions.

Consider Kafka at-least-once behavior and event replay.

Design consumers to tolerate duplicates whenever practical.

Use dead-letter handling for malformed or non-processable events after explicit policy decisions.

## 23. Docker

Every deployable service should eventually have a Dockerfile.

Docker Compose is the first orchestration target.

Use health checks where appropriate.

## 24. Kubernetes

Do not introduce Kubernetes before Docker Compose is reliable.

Later Kubernetes resources should include:

- readiness probes;
- liveness probes;
- startup probes where useful;
- resource requests;
- resource limits;
- ConfigMaps;
- Secrets;
- PodDisruptionBudgets where appropriate.

## 25. Documentation

Architecture changes must be documented.

Use ADRs under `docs/adr/` for major decisions.

Keep README commands current and executable.

## 26. Plans

Before significant work, read `.agent/PLANS.md`.

For multi-service features, major infrastructure, migrations, or large refactors, create/update an ExecPlan.

ExecPlans must include:

- objective;
- current state;
- affected architecture;
- implementation steps;
- validation;
- tests;
- risks;
- decisions;
- progress.

## 27. Etapas atuais e evolução

Capacidades que já compõem a stack local:

1. simulador de 20 carros e regras da corrida;
2. Kafka, Schema Registry e contratos Avro;
3. consumer Python para validação e projeções online;
4. FastAPI, WebSocket e dashboard React;
5. PostgreSQL para estado operacional e resultados;
6. Spark Structured Streaming e jobs batch com arquivo em MinIO.

As próximas fases dependem de ExecPlan e critérios de validação próprios. ClickHouse,
Iceberg, CDC quando houver fonte que exija captura de alterações, observabilidade,
Kubernetes e CI/CD ainda não fazem parte da stack executada localmente.

## 28. Codex Working Rules

Before changing code:

1. inspect the repository;
2. read `.agents/AGENTS.md`;
3. read the active ExecPlan;
4. inspect relevant tests;
5. identify affected components.

After changes:

1. format;
2. lint;
3. type-check;
4. run unit tests;
5. run relevant integration tests;
6. update documentation/plan.

Do not proceed to a later architecture phase merely because it appears in this document.

Implement only the current requested phase.


## 29. Idioma dos textos gerados

Toda documentação, mensagens, comentários e docstrings gerados devem estar em
português do Brasil. Preserve identificadores técnicos de código, contratos,
comandos e nomes de tecnologias quando necessário para compatibilidade.
