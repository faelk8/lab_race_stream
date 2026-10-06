# Apache Spark

## Papel na arquitetura

Spark 4.0.1 é o único motor de processamento distribuído adotado. Ele tem duas
responsabilidades implementadas:

1. arquivar continuamente os dez tópicos Kafka em Parquet no MinIO;
2. executar, sob demanda, agregações de voltas e comparação com o consumer.

O consumer Python continua responsável pela validação e pelas projeções que
alimentam o dashboard.

## Structured Streaming

`stream-processing/spark/arquivo_telemetria.py` usa o source Kafka oficial. O
job grava em append, particiona por `topic` e `event_date_utc` e usa trigger de
30 segundos por padrão. `failOnDataLoss=true` faz o job falhar se os offsets
necessários deixarem de existir.

O Compose limita o processo a uma CPU, 1.200 MiB de memória do container e 512
MiB de driver. O paralelismo local é `local[1]` e há duas partições de shuffle.

Dependências baixadas pelo `spark-submit`:

- `spark-sql-kafka-0-10_2.13:4.0.1`;
- `spark-avro_2.13:4.0.1`;
- `hadoop-aws:3.4.1`.

## Validação do arquivo

O job `validar_arquivo.py` confirma colunas obrigatórias, valores essenciais,
ausência de duplicidade por tópico/partição/offset e presença de registros.

Com a stack ativa, pause o arquivador para reduzir a disputa de memória:

```bash
docker compose stop spark-archive
docker compose run --rm --no-deps spark-archive \
  --master 'local[1]' --driver-memory 512m \
  --conf spark.jars.ivy=/opt/spark/work-dir/.ivy2 \
  --packages org.apache.hadoop:hadoop-aws:3.4.1 \
  /opt/racestream/validar_arquivo.py
docker compose up -d spark-archive
```

O script lê Parquet e S3A, portanto não precisa do conector Kafka nessa execução.

## Agregações e paridade

`agregar_voltas.py`:

- lê o arquivo bruto;
- extrai o ID do schema no envelope Confluent;
- busca cada schema writer e o reader mais recente no Schema Registry;
- decodifica `lap_completed` e `analytics`;
- remove duplicatas por `event_id`;
- calcula voltas válidas, melhor, pior e média por corrida/carro;
- compara contagem, melhor e pior volta com a revisão online mais recente;
- grava `lap_performance` e `consumer_parity` em modo overwrite.

Execução comprovada pelo projeto:

```bash
docker compose stop spark-archive
docker compose run --rm --no-deps spark-archive \
  --master 'local[1]' --driver-memory 512m \
  --conf spark.jars.ivy=/opt/spark/work-dir/.ivy2 \
  --packages org.apache.spark:spark-avro_2.13:4.0.1,org.apache.hadoop:hadoop-aws:3.4.1 \
  /opt/racestream/agregar_voltas.py
docker compose up -d spark-archive
```

O registro histórico do repositório documenta 80 pares corrida/carro
coincidentes em uma execução de 06/10/2026. Esse resultado não é uma garantia
automática para dados produzidos depois daquela validação.

## Limitações

- Não há teste pytest dos jobs Spark.
- A análise depende do Schema Registry ainda conter os IDs históricos.
- As saídas batch são sobrescritas a cada execução.
- Não há Iceberg, catálogo, compactação nem camada curada.
- Não há publicação de agregados Spark no Kafka ou na API.
- O checkpoint é único para o conjunto configurado de tópicos; mudanças de
  assinatura precisam de operação controlada.
