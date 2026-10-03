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
- `execplan-race-dashboard.md`: plano da corrida configurável e painel Interlagos.
- `execplan-streaming.md`: plano futuro para Flink/Spark.
- `CODEX_PROMPT.md`: prompt inicial para desenvolvimento incremental.
- `PHASE_PROMPTS.md`: prompts para fases futuras.
- `docs/adr/`: decisões arquiteturais aceitas.

## Executar a corrida

Pré-requisitos: Docker com Compose. A instalação Python local é necessária apenas para executar testes e ferramentas de desenvolvimento.

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
docker compose up --build
```

O Compose inicia PostgreSQL, Kafka, Schema Registry, API, dashboard, simulador e consumer. Cada corrida dura 120 segundos e representa 60 voltas de referência em Interlagos; o producer publica snapshots Avro a cada 100 ms.

- Dashboard: `http://localhost:5173`
- API e documentação OpenAPI: `http://localhost:8000/docs`
- Schema Registry: `http://localhost:8081`
- Kafka para clientes locais: `localhost:9092`

PostgreSQL fica somente na rede interna do Compose para não conflitar com bancos já instalados no host. A API e o runner salvam configurações, corridas e resultados; o fluxo detalhado de telemetria permanece no Kafka.

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
npm --prefix frontend ci
npm --prefix frontend run build
```

O teste Kafka requer os serviços ativos. Encerre com `Ctrl+C` no terminal do Compose ou execute `docker compose down`; os dados de Kafka e PostgreSQL são mantidos nos volumes. `docker compose down -v` remove esses dados.

## Simulação e setup

Os vinte carros recebem configurações distintas de peso do carro, peso do piloto, velocidade máxima e composto. O editor do dashboard salva as mudanças no PostgreSQL; elas passam a valer na corrida seguinte.

Os compostos alteram o tempo estimado por volta: macio `−250 ms`, médio `0 ms` e duro `+300 ms`. A telemetria v2 inclui tempo atual, última volta, melhor volta e estado da corrida. O mapa usa `track_progress` normalizado e a fonte do SVG está registrada em `frontend/public/ATTRIBUTION.md`.

O simulador reduz velocidade e marcha ao se aproximar das zonas de curva, mantém a aceleração controlada durante o contorno e volta a acelerar na saída até atingir a velocidade máxima configurada. Os carros mantêm no mínimo 60 m de separação na linha de corrida; a fase atual (`reta`, `frenagem` ou `curva`) aparece no dashboard.

Caches locais do Brave/JetBrains e artefatos `frontend/node_modules`/`frontend/dist` são ignorados pelo Git.

Flink, Spark, ClickHouse, Iceberg, CDC e Kubernetes continuam fora desta fase.
