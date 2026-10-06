# Logs e observabilidade

## Logs estruturados

Os serviços Python chamam `configure_logging()` e escrevem um objeto JSON por
linha em stdout. Cada registro contém timestamp UTC, nível, logger e mensagem.
Quando presentes, também são incluídos:

- `race_id`;
- `car_id`;
- `event_id`;
- `topic`, `partition` e `offset`;
- `car_count`, `lap` e `race_position`;
- `error` e stack trace.

O nível é controlado por `LOG_LEVEL`. O código evita registrar continuamente o
payload completo da telemetria.

Exemplos de inspeção:

```bash
docker compose logs --tail=200 simulator
docker compose logs --tail=200 consumer
docker compose logs --tail=200 api
docker compose logs --tail=200 spark-archive
```

Kafka, Schema Registry, PostgreSQL, MinIO, Spark e Vite usam seus próprios
formatos de log; a configuração JSON Python não se aplica a eles.

## Saúde

| Serviço | Verificação configurada |
| --- | --- |
| PostgreSQL | `pg_isready`. |
| Kafka | listagem de tópicos pelo CLI. |
| Schema Registry | `GET /subjects`. |
| MinIO | endpoint `/minio/health/ready`. |
| API | `GET /health`. |

O endpoint da API é apenas liveness e não verifica PostgreSQL, Kafka ou Schema
Registry durante a chamada.

## Ferramentas operacionais

- Redpanda Console permite inspecionar tópicos, mensagens, grupos e subjects.
- MinIO Console permite inspecionar bucket e objetos.
- `/api/streaming` mostra o catálogo usado pela aplicação.
- `docker compose ps` mostra health e estado dos containers.

## Métricas e traces

OpenTelemetry, Prometheus e Grafana:

> Não identificado no repositório.

Não há métricas de aplicação, exporters, traces distribuídos, dashboards,
alertas ou objetivos de nível de serviço. A latência registrada em documentos
históricos foi uma medição manual e não constitui monitoramento contínuo.

## Lacunas operacionais

- consumer, simulator, dashboard e Spark não têm endpoint de saúde próprio;
- não há correlação obrigatória entre todos os logs;
- não há coleta centralizada ou retenção de logs;
- não há alerta para crescimento da outbox, atraso do Spark, DLQ ou esgotamento
  da retenção Kafka;
- o painel exibe conexão WebSocket, mas essa informação não é exportada como
  métrica.

