# Persistência de dados

## Responsabilidades

| Tecnologia | Dados | Retenção/vida útil |
| --- | --- | --- |
| PostgreSQL | Configuração, ciclo da corrida, resultados, projeções e outbox. | Persistente no volume `postgres-data`; sem expurgo automático. |
| Kafka | Eventos fonte e derivados. | Sete dias por tópico no Compose. |
| MinIO | Envelopes Kafka em Parquet, checkpoints e agregados Spark. | Persistente no volume `minio-data`; sem política de expiração configurada. |
| Volume Spark | Cache Ivy dos pacotes. | Persistente em `spark-work`. |

## PostgreSQL

### Tabelas

| Tabela | Finalidade |
| --- | --- |
| `cars` | Cadastro e setup atual dos vinte carros. |
| `races` | Configuração, cenários e ciclo de vida da prova. |
| `race_results` | Resultado final/parcial e snapshot do setup por carro. |
| `stream_sessions` | Projeção recuperável, último `state` e último `analytics`. |
| `stream_receipts` | Deduplicação por tópico, partição e offset. |
| `stream_events` | Eventos discretos, como timing e voltas derivadas. |
| `stream_outbox` | Eventos derivados ainda não confirmados pelo Kafka. |

`stream_events` não armazena cada snapshot de telemetria. A telemetria de alta
frequência segue para o arquivo Parquet.

### Transações e consistência

O consumer cria um recibo de offset, aplica o evento, atualiza a projeção e
insere a outbox dentro da transação. Eventos `timing` também têm chave lógica
por corrida, carro, volta e linha. A outbox só é removida depois que o producer
Kafka confirma o lote.

Há um índice parcial que permite apenas uma corrida controlada nos estados
`queued`, `running` ou `stopping`. O início usa advisory lock; a reserva usa
`FOR UPDATE SKIP LOCKED`.

### Inicialização e migrações

Os arquivos em `postgres/initdb/` são executados automaticamente apenas na
criação de um volume PostgreSQL vazio. Ao iniciar, `seed_default_cars()` reaplica
os scripts idempotentes `002` a `009` e insere carros ausentes. A imagem da API
inclui esses scripts. O script `009` atualiza o nome padrão do piloto `DRV-01`
quando o valor persistido ainda é o anterior, preservando outros nomes editados.

Não há tabela de versões/checksums nem ferramenta dedicada, como Alembic. A ordem
dos scripts está codificada no repositório; alterações devem manter idempotência
e atualizar também o `Dockerfile` para copiar qualquer novo script para a imagem.

> Não identificado no repositório.

## Kafka

Os tópicos `telemetry`, `validated`, `timing`, `lap_completed`, `pitstop`,
`incident`, `control`, `state`, `analytics` e `dead_letter` são criados com:

- seis partições;
- fator de replicação 1;
- retenção de 604.800.000 ms, equivalente a sete dias.

O ambiente tem um único broker, sem alta disponibilidade. Tópicos com nomes
anteriores não são removidos automaticamente.

## MinIO e Parquet

O bucket padrão é `racestream`:

```text
racestream/
├── telemetry_raw/
│   └── topic=<tópico>/event_date_utc=<data>/
├── _checkpoints/
│   └── spark_kafka_archive_v2/
├── lap_performance/
└── consumer_parity/
```

`telemetry_raw` preserva o envelope Avro Confluent sem decodificá-lo. Isso exige
que os schemas writer referenciados pelos IDs continuem disponíveis no Schema
Registry para análises posteriores.

Não há tabela Iceberg, catálogo lakehouse, compactação, vacuum ou lifecycle
configurado.

> Não identificado no repositório.

## Backup e recuperação

O checkpoint Spark permite continuar a leitura de offsets. O consumer Python
recupera projeções e deduplica replays. Não há scripts de backup, restauração,
replicação ou disaster recovery dos volumes.

> Não identificado no repositório.
