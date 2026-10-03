# Prompt Inicial para o Codex

Copie o conteúdo abaixo para o Codex na raiz do repositório.

---

Quero desenvolver o projeto **RaceStream Lab**.

Antes de alterar qualquer arquivo:

1. leia integralmente `AGENTS.md`;
2. leia `.agent/PLANS.md`;
3. leia `docs/architecture/ARCHITECTURE.md`;
4. leia `docs/architecture/EVENTS.md`;
5. leia `docs/architecture/STREAM_ENGINES.md`;
6. leia `docs/architecture/ROADMAP.md`;
7. leia os ADRs existentes.

O objetivo do projeto é criar um laboratório de Engenharia de Dados e Sistemas Distribuídos que simule uma corrida com 20 carros produzindo telemetria em tempo real.

A arquitetura futura contém:

- Python 3.12+;
- Apache Kafka;
- Schema Registry;
- Avro como formato inicial;
- Protobuf como alternativa futura;
- Apache Flink;
- Spark Structured Streaming/PySpark como engine alternativo;
- FastAPI;
- WebSocket;
- React + TypeScript + SVG;
- PostgreSQL;
- Debezium CDC;
- ClickHouse;
- MinIO/S3;
- Apache Iceberg;
- OpenTelemetry;
- Prometheus;
- Grafana;
- Docker Compose;
- Kubernetes;
- GitHub Actions.

IMPORTANTE:

Não implemente toda essa arquitetura agora.

A evolução deve ser incremental.

A primeira tarefa é revisar a documentação existente e preparar o repositório para o primeiro MVP descrito em:

`.agent/execplan-mvp.md`

O primeiro MVP é somente:

```text
Race Simulator
 -> Avro serializer
 -> Schema Registry
 -> Kafka
 -> Python Consumer
```

O simulador deve manter 20 carros independentes e gerar pelo menos:

- velocidade;
- marcha;
- RPM;
- combustível;
- peso do carro;
- volta;
- setor;
- posição normalizada na pista (`track_progress`);
- posição na corrida;
- acelerador;
- freio;
- composto do pneu;
- idade do pneu;
- estado do pit.

O combustível deve reduzir ao longo do tempo e influenciar o peso.

O simulador precisa aceitar uma seed para comportamento determinístico em testes.

O domínio Python não pode depender diretamente de Kafka, Avro, FastAPI, banco de dados ou frameworks de infraestrutura.

Use arquitetura:

```text
domain/
application/
infrastructure/
interfaces/
```

Requisitos Python:

- type hints completos;
- Pydantic quando fizer sentido nas fronteiras;
- pytest;
- ruff;
- mypy ou equivalente;
- código limpo;
- SOLID quando aplicável;
- dependency injection;
- docstrings compatíveis com Sphinx em todos os módulos, classes, métodos e funções públicas.

Antes de escrever código:

1. examine o estado atual do repositório;
2. atualize `.agent/execplan-mvp.md` se algum detalhe precisar ser refinado;
3. apresente resumidamente o plano que será executado;
4. somente então implemente o primeiro milestone.

Não avance para Flink, Spark, React, Kubernetes, Iceberg, ClickHouse ou CDC durante este MVP.

A meta final desta fase é executar:

```bash
docker compose up --build
```

E observar 20 carros publicando eventos Avro válidos em Kafka e um consumer Python recebendo e desserializando esses eventos.

Ao concluir cada milestone:

- execute os testes;
- execute lint;
- execute type checking;
- registre progresso no ExecPlan;
- não afirme que algo funciona sem validação executada.

Comece analisando o repositório e o ExecPlan. Não comece criando toda a arquitetura futura.
