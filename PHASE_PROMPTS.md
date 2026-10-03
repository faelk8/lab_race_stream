# Prompts Incrementais para o Codex

Use estes prompts somente depois que a fase anterior estiver funcionando.

---

## Prompt — Adicionar Protobuf como alternativa

Leia `AGENTS.md`, os ADRs e o ExecPlan atual.

Quero adicionar Protobuf como segunda estratégia de serialização sem alterar o domínio.

Requisitos:

- manter Avro como padrão;
- criar/usar uma porta `EventSerializer` e `EventDeserializer`;
- implementar adapters Avro e Protobuf;
- manter schemas versionados;
- não misturar formatos implicitamente no mesmo tópico;
- adicionar testes de contrato;
- documentar como selecionar o formato;
- criar ADR se alguma decisão arquitetural adicional for necessária.

Antes de implementar, produza/atualize um ExecPlan específico.

---

## Prompt — Implementar Flink

Leia `AGENTS.md`, `docs/architecture/STREAM_ENGINES.md` e `.agent/execplan-streaming.md`.

Quero implementar a primeira versão do processamento com Apache Flink.

Use os contratos Kafka existentes.

Implemente inicialmente:

- latest state por carro;
- média móvel de velocidade;
- taxa de consumo de combustível;
- detecção de volta completada;
- snapshot de `race.state`.

Use event time e defina explicitamente watermarks/allowed lateness.

Publique resultados em contratos de saída independentes do Flink.

Não altere consumidores downstream para depender de APIs Flink.

Crie testes com fixture determinística compartilhável futuramente com Spark.

Atualize o ExecPlan conforme o progresso.

---

## Prompt — Implementar Spark Structured Streaming / PySpark

Leia `AGENTS.md`, `docs/architecture/STREAM_ENGINES.md` e `.agent/execplan-streaming.md`.

Já existe ou existirá uma implementação Flink. Quero adicionar uma implementação equivalente usando Spark Structured Streaming/PySpark.

Use exatamente os mesmos contratos Kafka de entrada e saída para as transformações equivalentes.

Implemente:

- latest state por carro;
- média móvel de velocidade;
- taxa de consumo de combustível;
- detecção de volta completada;
- snapshot de `race.state`.

Use watermarking e checkpointing adequados ao Spark.

Reutilize a fixture determinística de contratos.

Crie testes de paridade de saída normalizada onde a semântica deve ser equivalente.

Documente diferenças inevitáveis entre Spark e Flink.

Não tente esconder as APIs Spark atrás de uma abstração genérica universal.

---

## Prompt — Adicionar FastAPI + WebSocket

Quero criar o gateway de tempo real.

Fluxo:

```text
Kafka race.state
 -> FastAPI consumer
 -> WebSocket
 -> navegador
```

Requisitos:

- conexão WebSocket por race_id;
- compactar estado enviado ao frontend;
- suportar reconexão;
- evitar enviar histórico bruto pelo WebSocket;
- testes unitários e integração;
- métricas básicas de conexões e mensagens.

Crie ExecPlan antes da implementação.

---

## Prompt — Criar frontend da pista

Quero implementar React + TypeScript + SVG.

Cada carro recebe `track_progress` entre 0.0 e 1.0.

O frontend deve converter esse valor em posição ao longo de um path SVG.

Requisitos:

- 20 marcadores visualmente distintos;
- interpolação suave entre atualizações;
- leaderboard lateral;
- painel de carro selecionado;
- velocidade;
- marcha;
- combustível;
- peso;
- volta;
- último tempo;
- melhor tempo;
- pit stops;
- fuel added;
- estado da conexão WebSocket.

Não mova lógica de domínio para o frontend.

---

## Prompt — PostgreSQL + Debezium CDC

Quero adicionar PostgreSQL para metadados operacionais e Debezium CDC.

Comece apenas com:

- race configuration;
- drivers;
- teams;
- cars.

Fluxo:

```text
PostgreSQL
 -> Debezium
 -> Kafka CDC topics
```

Não use CDC para a telemetria de alta frequência.

Defina schemas e estratégia de tombstones/deletes.

Adicione testes de integração.

---

## Prompt — ClickHouse

Quero adicionar ClickHouse para consultas analíticas interativas.

Persistir inicialmente:

- telemetry;
- laps;
- pit stops;
- race state history.

Defina schemas e estratégias de ordenação/particionamento baseadas nas consultas planejadas.

Não copie automaticamente todos os campos sem justificar o modelo.

Crie consultas exemplo para:

- melhor volta;
- velocidade média por volta;
- consumo por volta;
- comparação de pit stops;
- evolução de posição.

---

## Prompt — MinIO/S3 + Apache Iceberg

Quero adicionar uma camada lakehouse local usando MinIO e Apache Iceberg.

Objetivos:

- armazenamento durável de telemetria;
- tabelas Iceberg;
- schema evolution;
- partition evolution;
- time travel;
- leitura tanto por Spark quanto por Flink quando suportado pelo stack escolhido.

Comece com:

- `telemetry_raw`;
- `telemetry_enriched`;
- `lap_performance`.

Escolha e documente como os eventos chegarão às tabelas Iceberg.

Não assuma automaticamente que Kafka Connect é a melhor opção; compare com Flink sink e Spark streaming write conforme o estado atual do projeto.

Registre a decisão em ADR.

---

## Prompt — Kubernetes

Somente execute esta fase quando Docker Compose estiver estável.

Quero migrar os serviços stateless e depois avaliar os stateful services.

Ambiente local alvo:

- kind ou k3d.

Requisitos:

- namespaces;
- ConfigMaps;
- Secrets;
- requests/limits;
- readiness/liveness/startup probes;
- Helm quando fizer sentido;
- documentação reproduzível.

Avalie operadores existentes antes de escrever manifests complexos para Kafka, Flink ou Spark.

---

## Prompt — Observabilidade

Adicionar:

- OpenTelemetry;
- Prometheus;
- Grafana.

Métricas desejadas:

- events/sec;
- producer errors;
- consumer lag;
- processing latency;
- late events;
- invalid schema events;
- WebSocket clients;
- Flink checkpoint metrics OU Spark query/checkpoint metrics;
- ClickHouse ingestion latency.

Crie dashboards úteis, não apenas gráficos decorativos.
