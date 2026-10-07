# Decisões arquiteturais

Os ADRs preservam o contexto histórico. Quando uma decisão mudou, o documento
novo prevalece para a arquitetura atual.

## Decisões vigentes

| ADR | Decisão atual |
| --- | --- |
| [0001](adr/0001-clean-architecture-and-dependency-inversion.md) | Camadas e inversão de dependência no Python. |
| [0004](adr/0004-configurable-race-and-postgres.md) | Configuração e estado operacional em PostgreSQL. |
| [0005](adr/0005-interlagos-dashboard-and-websocket.md) | Dashboard React e fanout WebSocket. |
| [0006](adr/0006-track-aware-driving-and-car-spacing.md) | Condução orientada pela pista e espaçamento. |
| [0008](adr/0008-identificacao-e-classificacao-do-pelotao.md) | Identidade, balões e classificação coerente. |
| [0009](adr/0009-controle-manual-da-corrida.md) | Início e parada persistidos. |
| [0010](adr/0010-cronometragem-e-projecoes-de-corrida.md) | Cronometragem por passagem, projeções e outbox. |
| [0011](adr/0011-spark-postgresql-minio.md) | PostgreSQL operacional e arquivo Spark/MinIO. |
| [0012](adr/0012-cenarios-de-prova-e-paridade-spark.md) | Chuva/incidentes reproduzíveis e paridade batch. |
| [0013](adr/0013-nomes-curtos-topicos-kafka.md) | Tópicos Kafka curtos. |
| [0014](adr/0014-spark-como-motor-unico.md) | Spark como único motor distribuído. |
| [0015](adr/0015-grid-e-contexto-de-volta-e-pit-stop.md) | Grid em duas colunas e contexto de volta e pit stop nos eventos. |

## Decisões substituídas ou ampliadas

- [ADR 0002](adr/0002-avro-telemetry-contract.md) continua válida quanto a Avro,
  versionamento e chave por carro, mas seu tópico `race.telemetry.raw` foi
  substituído por `telemetry` na ADR 0013.
- [ADR 0003](adr/0003-local-kafka-compose-topology.md) continua válida quanto à
  topologia local, mas os tópicos atuais são os dez nomes curtos.
- [ADR 0007](adr/0007-corrida-rules.md) documenta o modelo anterior de pit stop;
  a simulação física e o limite de 60 km/h foram ampliados pela ADR 0010.
- A proposta de múltiplos motores distribuídos foi encerrada pela ADR 0014.

## Decisões operacionais observadas no código

- Producer Kafka idempotente, `acks=all` e confirmação explícita.
- Consumer com auto commit desligado e confirmação depois da transação.
- PostgreSQL como fonte de verdade das projeções online.
- Outbox transacional para eventos derivados.
- Quadros parciais após três segundos, preservando a classificação anterior.
- Evento time e relógio simulado nos contratos; o Spark arquiva pelo timestamp
  Kafka e não implementa watermark de domínio.
- `track_progress` normalizado é o contrato de posição; pixels ficam no frontend.
- Configuração do carro vale para a próxima corrida, porque participantes e pista
  são congelados no evento de controle da sessão.

## Decisões ainda necessárias

Ainda não existem ADRs aceitos para autenticação, produção em cluster, backup,
Iceberg, ClickHouse, CDC, métricas/traces ou CI/CD.

> Não identificado no repositório.
