# Operação do laboratório local

## Serviços e métricas

```bash
docker compose up -d --build api consumer spark-archive
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml \
  --profile observabilidade up -d
```

Grafana fica em `http://localhost:3000` e Prometheus em
`http://localhost:9090`; ambas as portas estão vinculadas ao loopback. A
credencial anônima do Grafana tem somente permissão de leitura. API expõe
`/live`, `/ready` e `/metrics`. As métricas do consumer (9101) e Spark (9102)
permanecem na rede Compose.

`/live` mede se o servidor HTTP responde. `/ready` usa sondagens recentes de
PostgreSQL, Kafka e fanout WebSocket na API; o consumer testa PostgreSQL e
atribuição/alcance Kafka. O Spark consulta o estado da Structured Streaming e a
saúde do endpoint MinIO. Uma query ociosa é válida; um micro-lote ativo por mais
do que `SPARK_STALL_TIMEOUT_SECONDS` é considerado travado. O limite padrão é
300 segundos. Os serviços de processamento usam `/ready` no healthcheck Compose.

## Backup e restauração

O backup precisa de espaço temporário igual ou maior ao PostgreSQL, MinIO e Kafka.
A tarefa cria um diretório de permissão privada, verifica SHA-256 e inclui o dump
customizado PostgreSQL e cópias frias dos volumes MinIO e Kafka. Ela para os
serviços escritores e dependências antes dos snapshots e os reinicia na saída.
Recusa uma corrida queued, running, paused ou stopping. Não chame o procedimento
com Compose diferentes dos que iniciaram a stack.

```bash
poetry run python scripts/backup_local.py create
poetry run python scripts/backup_local.py verify backups/PASTA_DO_BACKUP
```

Para o teste diário, o temporizador systemd local pode ser instalado em nível de
usuário. Confira o `WorkingDirectory`, o caminho de `poetry` e a disponibilidade
da stack na unidade antes de habilitá-lo. `--prune` remove snapshots íntegros
com mais de sete dias e preserva pelo menos os três mais recentes.

A restauração cria um projeto Compose novo sem portas públicas. Use um prefixo
`race-restore-` e mantenha esse projeto apenas enquanto inspeciona a recuperação:

```bash
poetry run python scripts/backup_local.py restore backups/PASTA_DO_BACKUP \
  --project race-restore-validacao
# Após validar os dados isolados:
docker compose -f docker-compose.yml -f docker-compose.recovery.yml \
  -p race-restore-validacao down --volumes --remove-orphans
```

O backup está no mesmo computador. Copiar o diretório a outro disco permanece
responsabilidade do operador, e não é feito pelo script.

## Retenção

Kafka limita os tópicos a sete dias. Por padrão, o PostgreSQL mantém todos os
recibos/offsets e chaves `stream_events`; a expiração de conteúdo é simulada:

```bash
docker compose exec -T api python -m racestream.infrastructure.retention --days 30
```

Para aplicar em lotes pequenos depois de revisar a quantidade:

```bash
docker compose exec -T api python -m racestream.infrastructure.retention \
  --days 30 --limit 10000 --apply
```

São elegíveis somente payloads antigos de corridas encerradas, diferentes da
corrida mais recente e sem itens pendentes na outbox. Os IDs e `logical_key` são
mantidos para que replay e duplicatas continuem reconhecíveis. O histórico de
payloads expirados deixa de aparecer na API. Redução geral de `stream_receipts`
é deliberadamente evitada porque offsets reprocessados não podem reaplicar fatos.

MinIO não tem lifecycle automático: arquivo Parquet e `_checkpoints` são
mantidos juntos indefinidamente. Expurgar apenas parte do conjunto pode quebrar
a recuperação e o replay da query Spark.

## Validação operacional

```bash
poetry run python tests/integration/validate_backup.py
docker compose up -d api
docker compose exec -T api python < tests/integration/validate_retention.py
```

O primeiro comando cria projetos e volumes aleatórios dedicados e os remove ao
terminar. O segundo usa schema PostgreSQL temporário e faz rollback antes de sair.
Não executam nem iniciam uma corrida.
