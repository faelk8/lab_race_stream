# Testes e validação

## Camadas existentes

| Camada | Evidência |
| --- | --- |
| Unidade de domínio | Física, combustível, pneus, tráfego, chuva, incidentes, posições e pista. |
| Aplicação | Workers, controle de corrida, publicação e persistência de resultados. |
| Contrato | Pydantic, campos Avro, round-trip dos schemas ativos e compatibilidade v1/v2/v3. |
| API | Validação e atualização de carros com adapters em memória. |
| Frontend | Apresentação, ordenação, quadros, balões e mensagens de erro. |
| Integração Kafka | Producer/consumer Avro com broker e Schema Registry reais, opt-in. |
| Integração PostgreSQL | Script manual isolado para replay, outbox, rollback e DLQ. |
| Spark | Scripts manuais de integridade do arquivo e paridade batch. |

Testes end-to-end automatizados em navegador:

> Não identificado no repositório.

Testes de carga e resiliência automatizados:

> Não identificado no repositório.

## Python

Instale as dependências de desenvolvimento e execute:

```bash
.venv/bin/ruff check src tests stream-processing/spark
.venv/bin/mypy src tests
.venv/bin/pytest -q
```

O pytest procura arquivos em `tests/`. O teste Kafka é ignorado por padrão e só
é executado quando `RUN_KAFKA_INTEGRATION=1`.

Com Kafka e Schema Registry disponíveis no host:

```bash
RUN_KAFKA_INTEGRATION=1 \
KAFKA_BOOTSTRAP_SERVERS=localhost:9092 \
SCHEMA_REGISTRY_URL=http://localhost:8081 \
.venv/bin/pytest tests/integration/test_kafka_roundtrip.py -q
```

Esse teste cria um tópico temporário, publica um evento Avro, valida a leitura e
remove o tópico ao terminar.

## PostgreSQL

`tests/integration/validate_projection_recovery.py` é um script manual, não um
teste coletado pelo pytest. Ele cria um schema temporário, verifica deduplicação,
reabertura, outbox, DLQ e rollback, e remove o schema no final.

O diretório `tests/` não é copiado para a imagem Python. Monte-o explicitamente
ao executar a validação com a stack ativa:

```bash
docker compose run --rm --no-deps \
  -v "$PWD/tests:/app/tests:ro" \
  api python tests/integration/validate_projection_recovery.py
```

## Frontend

```bash
cd frontend
npm test
npm run typecheck
npm run build
```

Os testes usam o runner nativo do Node e transpilações TypeScript em memória.
Eles não montam o React em um DOM e não substituem uma validação visual real.

## Docker Compose

```bash
docker compose config --quiet
docker compose ps
curl -fsS http://localhost:8000/health
```

`docker compose config --quiet` valida a composição sem iniciar containers.

## Spark

Os jobs de validação e agregação estão documentados em [Spark](spark.md). Eles
dependem da stack, do arquivo no MinIO e dos schemas históricos no Registry.

## Limites da cobertura

- Não há cobertura configurada nem meta mínima.
- Não há fixture compartilhada automatizada entre Spark e consumer; a paridade
  é executada sobre o arquivo real.
- Não há teste automatizado dos Dockerfiles.
- Não há pipeline de CI que execute os comandos.
- Os números de testes registrados nos planos são evidências datadas e podem
  mudar conforme a suíte evolui.
