# RaceStream Lab

Laboratório de Engenharia de Dados e Sistemas Distribuídos para simular uma corrida com 20 carros gerando telemetria em tempo real.

## Objetivo

Construir uma plataforma orientada a eventos capaz de:

- simular 20 carros com estado independente;
- publicar telemetria em Apache Kafka;
- validar contratos com Schema Registry;
- serializar eventos com Avro ou Protobuf;
- processar streams com Apache Flink **ou** Spark Structured Streaming/PySpark;
- expor estado em tempo real via FastAPI + WebSocket;
- mostrar carros em movimento em uma pista no frontend;
- persistir histórico analítico em ClickHouse;
- manter dados brutos e curados em MinIO/S3 usando Apache Iceberg;
- suportar CDC com Debezium;
- executar inicialmente com Docker Compose e depois Kubernetes;
- aplicar observabilidade com OpenTelemetry, Prometheus e Grafana;
- automatizar testes e deploy com GitHub Actions.

## Princípio de arquitetura

O restante do sistema não deve depender diretamente de Flink ou Spark.

O motor de processamento deverá ser substituível através de contratos estáveis de entrada e saída:

```text
Kafka telemetry.raw
        |
        v
+-----------------------+
| Stream Engine         |
|                       |
| Flink                 |
|        OU             |
| Spark Structured      |
| Streaming / PySpark   |
+-----------+-----------+
            |
            v
Kafka race.state / analytics / events
```

## Documentos

- `AGENTS.md`: regras permanentes para o Codex.
- `PLANS.md`: padrão para ExecPlans.
- `execplan-mvp.md`: plano do primeiro MVP e checklist de retomada.
- `execplan-streaming.md`: plano futuro para Flink/Spark.
- `CODEX_PROMPT.md`: prompt inicial para desenvolvimento incremental.
- `PHASE_PROMPTS.md`: prompts para fases futuras.
- `docs/adr/`: decisões arquiteturais aceitas.

## Executar o MVP

Pré-requisitos: Docker com Compose e Python 3.12+.

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
docker compose up --build
```

O Compose inicia Kafka, Schema Registry, criação do tópico, simulador e consumer. O simulador publica 20 eventos Avro por segundo em `race.telemetry.raw`; o consumer registra em JSON os eventos desserializados.

Para acompanhar apenas o consumer em outro terminal:

```bash
docker compose logs -f consumer
```

O Schema Registry fica disponível em `http://localhost:8081`; o Kafka para clientes locais em `localhost:9092`. O tópico usa `car_id` como chave e seis partições.

Para validar o código:

```bash
.venv/bin/ruff check src tests
.venv/bin/pytest
.venv/bin/mypy src tests
docker compose config --quiet
RUN_KAFKA_INTEGRATION=1 .venv/bin/pytest tests/integration -q
```

O teste de integração requer os serviços ativos. Encerre com `Ctrl+C` no terminal do Compose ou execute `docker compose down`; os dados do Kafka são mantidos no volume nomeado.

## Fluxo entregue nesta fase

```bash
docker compose up --build
```

Comportamento validado:

1. Kafka e Schema Registry iniciam saudáveis.
2. O tópico `race.telemetry.raw` é criado com seis partições.
3. O simulador cria 20 carros independentes e publica eventos Avro versionados.
4. O consumer desserializa e confirma cada evento após o processamento.
5. Testes unitários, de contrato e round-trip Kafka cobrem o fluxo.

O primeiro MVP **não** deve começar com Kubernetes, Flink, Spark, Iceberg ou frontend.
