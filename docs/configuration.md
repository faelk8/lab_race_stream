# Configuração

## Fontes de configuração

O projeto usa três mecanismos:

1. variáveis interpoladas pelo Docker Compose a partir do ambiente ou `.env`;
2. variáveis definidas diretamente em cada serviço do Compose;
3. arquivos versionados, principalmente `config/interlagos-v1.json` e os schemas
   em `schemas/`.

Não existe um objeto central de settings. Cada entrypoint lê apenas as variáveis
de que precisa.

## Variáveis interpoladas pelo Compose

| Variável | Padrão | Uso |
| --- | --- | --- |
| `POSTGRES_DB` | `racestream` | Banco criado e usado pelas aplicações. |
| `POSTGRES_USER` | `racestream` | Usuário PostgreSQL. |
| `POSTGRES_PASSWORD` | `racestream` | Senha PostgreSQL local. |
| `MINIO_ROOT_USER` | `racestream` | Usuário administrador do MinIO. |
| `MINIO_ROOT_PASSWORD` | `racestream-local-only` | Senha local do MinIO. |
| `MINIO_BUCKET` | `racestream` | Bucket criado pelo `minio-init`. |
| `RACE_SEED` | `42` | Semente determinística do simulador ativo. |
| `RACE_TIME_SCALE` | `45` | Segundos simulados por segundo real; aceita até 90. |
| `RACE_DURATION_SECONDS` | `120` | Duração de referência persistida na configuração. |
| `RACE_TARGET_LAPS` | `60` | Total de voltas. |
| `SIMULATION_INTERVAL_SECONDS` | `0.1` | Intervalo do loop do producer. |
| `LOG_LEVEL` | `INFO` | Nível dos logs Python. |
| `KAFKA_CONSUMER_GROUP` | `racestream-local-consumer` | Grupo do consumer legado; o consumer online ativo usa grupo fixo. |
| `VITE_API_BASE_URL` | `http://localhost:8000` | Base REST e WebSocket do dashboard. |
| `VITE_KAFKA_CONSOLE_URL` | `http://localhost:8080` | Destino do botão para o Console. |
| `SPARK_STARTING_OFFSETS` | `earliest` | Offset inicial quando não existe checkpoint. |
| `SPARK_MAX_OFFSETS_PER_TRIGGER` | `1000` | Limite por microbatch. |
| `SPARK_TRIGGER_INTERVAL` | `30 seconds` | Frequência do arquivamento. |

`RACE_DURATION_SECONDS` não encerra o `PhysicalRace` por tempo. O caminho ativo
termina por total de voltas, comando de parada ou prazo de chegada após o líder.

## Variáveis internas dos serviços

| Variável | Valor no Compose | Observação |
| --- | --- | --- |
| `KAFKA_BOOTSTRAP_SERVERS` | `kafka:29092` | URL interna; no host use `localhost:9092`. |
| `SCHEMA_REGISTRY_URL` | `http://schema-registry:8081` | URL interna; no host use `http://localhost:8081`. |
| `KAFKA_TOPIC` | `telemetry` | Mantida para adapters legados; `EventStream` usa o catálogo de tópicos. |
| `DATABASE_URL` | URI montada com as variáveis PostgreSQL | Usada por API, producer e consumer. |
| `KAFKA_DASHBOARD_GROUP` | `racestream-dashboard` | A API acrescenta `-derived`. |
| `MINIO_ENDPOINT` | `http://minio:9000` | Endpoint S3 interno do Spark. |
| `SPARK_LOG_LEVEL` | `WARN` | Nível do SparkContext. |

O consumer online usa o grupo fixo `racestream-projections-v1`; alterar
`KAFKA_CONSUMER_GROUP` no `.env` não muda esse serviço.

## Variáveis suportadas pelo código fora do Compose

| Variável | Padrão no código | Situação |
| --- | --- | --- |
| `RACE_TRACK_CONFIG` | `config/interlagos-v1.json` | Lida pelo loader, mas não repassada pelo Compose. |
| `TELEMETRY_SCHEMA_PATH` | `schemas/telemetry-v3.avsc` | Usada pelo adapter histórico de telemetria. |
| `SPARK_KAFKA_TOPICS` | lista dos dez tópicos | Lida pelo job, mas não interpolada no Compose. |

Para usar essas opções no Compose é necessário repassá-las ao serviço ou usar
`docker compose run -e NOME=valor ...`. Um valor apenas no `.env` não é enviado
automaticamente quando a variável não aparece no bloco `environment`.

## Pista e regras físicas

`config/interlagos-v1.json` é a fonte da pista ativa. Apesar do nome do arquivo,
sua propriedade `version` é `interlagos-lab-v2`. O arquivo contém:

- extensão de 4.309 m;
- offset do mapa;
- três setores e quinze checkpoints;
- zonas de curva aproximadas;
- entrada, box e saída do pit lane;
- limite de 60 km/h nos boxes;
- passo físico, aceleração, frenagem e limite lateral;
- tanque, consumo de referência e vazão de abastecimento;
- aderência dos compostos `soft`, `medium`, `hard` e `wet`.

A geometria é aproximada e validada na criação do objeto `Track`. Ela não é uma
medição oficial de Interlagos.

## Segurança da configuração

As credenciais padrão são locais e aparecem no Compose e `.env.example`. Não há
TLS, autenticação da API ou autenticação Kafka configurada. Para outro ambiente,
segredos e políticas de rede precisam ser definidos fora do que existe hoje.

Gerenciamento de segredos para produção:

> Não identificado no repositório.

