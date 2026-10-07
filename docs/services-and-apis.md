# Serviços, APIs, producers e consumers

## Serviços do Docker Compose

| Serviço | Imagem ou entrypoint | Papel | Porta no host |
| --- | --- | --- | --- |
| `postgres` | `postgres:16-alpine` | Estado operacional e projeções. | Não exposta. |
| `minio` | build local com MinIO fixado | Objetos S3 compatíveis. | `19000` e `19001`, somente loopback. |
| `minio-init` | mesma imagem local | Criação idempotente do bucket. | Nenhuma. |
| `kafka` | `confluentinc/cp-kafka:7.7.1` | Broker KRaft de nó único. | `9092`. |
| `schema-registry` | `cp-schema-registry:7.7.1` | Contratos Avro. | `8081`. |
| `redpanda-console` | `console:v3.12.0` | Inspeção de Kafka e schemas. | `8080`. |
| `topic-init` | `cp-kafka:7.7.1` | Criação dos dez tópicos. | Nenhuma. |
| `simulator` | imagem Python local | Producer e worker da corrida. | Nenhuma. |
| `consumer` | imagem Python local | Projeções online e outbox. | Nenhuma. |
| `api` | imagem Python local/Uvicorn | REST e WebSocket. | `8000`. |
| `dashboard` | imagem Node local/Vite | Interface web. | `5173`. |
| `spark-archive` | `apache/spark:4.0.1-python3` | Kafka para Parquet no MinIO. | Nenhuma. |

`topic-init` e `minio-init` são serviços de inicialização e terminam após cumprir
sua tarefa. Isso é esperado e não representa falha.

## API REST

O FastAPI expõe os endpoints abaixo. Os corpos e respostas são JSON.

| Método e caminho | Responsabilidade |
| --- | --- |
| `GET /health` | Liveness simples da API. |
| `GET /api/cars` | Lista as configurações persistidas dos carros. |
| `PUT /api/cars/{car_id}` | Atualiza o setup usado na próxima corrida. |
| `POST /api/races/start` | Solicita uma corrida com clima e incidentes. |
| `POST /api/races/{race_id}/stop` | Solicita a parada e preserva o resultado parcial. |
| `GET /api/races/latest` | Retorna o ciclo de vida da corrida mais recente. |
| `GET /api/streaming` | Retorna catálogo de tópicos, frequência e escala. |
| `GET /api/tracks/{track_id}` | Retorna a definição física configurada da pista. |
| `GET /api/races/{race_id}/state` | Retorna snapshot, analytics e participantes. |
| `GET /api/races/{race_id}/cars/{car_id}/laps` | Lista voltas derivadas e persistidas. |
| `GET /api/races/{race_id}/cars/{car_id}/splits` | Lista passagens cronometradas. |
| `GET /api/races/{race_id}/teams/{team_id}/analytics` | Filtra analytics pela equipe. |

FastAPI também fornece `/docs`, `/redoc` e `/openapi.json` por comportamento
padrão do framework. O CORS aceita apenas o dashboard em `localhost:5173` e
`127.0.0.1:5173`, com métodos `GET`, `PUT` e `POST`.

### Configuração de largada

`POST /api/races/start` aceita:

```json
{
  "rain_enabled": true,
  "rain_start_lap": 10,
  "rain_intensity": 0.7,
  "incidents": [
    {
      "incident_type": "tire_puncture",
      "lap": 8,
      "car_id": "CAR-03",
      "second_car_id": "",
      "penalty_seconds": 0
    }
  ]
}
```

`incident_type` aceita `tire_puncture`, `collision` ou `time_penalty`. Uma colisão
exige dois carros distintos. A penalidade exige de 1 a 60 segundos e não aceita
segundo carro. Com vinte carros e sessenta voltas, a chuva precisa começar
até a volta 21 para que todas as trocas sejam escalonadas em intervalos mínimos
de duas voltas.

## WebSocket

`WS /ws/races/{race_id}` envia um objeto `snapshot` inicial, quando disponível,
e depois eventos `state`, `analytics` e `control`. Não há protocolo de comando
no WebSocket; início, parada e alterações de setup usam REST.

## Producers

O producer ativo é `python -m racestream.interfaces.producer`, definido como
`CMD` da imagem Python. Ele usa `EventStream`, registra os schemas dos tópicos e
publica com producer idempotente, `acks=all` e confirmação no fechamento.

`AvroKafkaPublisher`, em `infrastructure/kafka.py`, atende o contrato histórico
`TelemetryEvent` v3 e é usado pelo teste de integração e pelo entrypoint legado
`racestream.interfaces.consumer`. Ele não é o caminho do serviço `simulator` no
Compose atual.

## Consumers

- `python -m racestream.interfaces.stream_processor`: consumer ativo do Compose;
  lê fatos fonte, valida, projeta, persiste e publica derivados.
- `KafkaTelemetryHub`: consumer embutido na API para o fanout WebSocket.
- `python -m racestream.interfaces.consumer`: consumer de logging do contrato
  histórico; existe no código, mas não é iniciado pelo Compose.
- `spark-archive`: consumer Kafka do Spark, independente dos grupos Python.

## Integrações externas e locais

- Schema Registry, Kafka, PostgreSQL e MinIO são serviços da própria stack.
- O frontend referencia Google Fonts pela rede. Se a rede estiver indisponível,
  a aplicação continua carregando, mas usa fontes alternativas do navegador.
- O SVG de Interlagos é armazenado localmente e tem atribuição em
  `frontend/public/ATTRIBUTION.md`.
- As unidades systemd e automações auxiliares em `integrations/` e `scripts/`
  não fazem parte do Compose da corrida.

Integrações com serviços públicos de AWS, Azure ou GCP:

> Não identificado no repositório.
