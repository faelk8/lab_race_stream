# ExecPlan: operação, recuperação e acesso

Data de início: 08/10/2026.

## Objetivo e escopo

Executar `to-do.md` para o laboratório local. Em 08/10/2026 o usuário confirmou
que produção, domínio público e backup externo estão fora do escopo.

## Estado atual e arquitetura afetada

API, consumer e Spark usam Compose. A API tem liveness/readiness e métricas;
consumer e Spark têm sondagens internas. Prometheus/Grafana são optativos. Há
backup local verificado e retenção PostgreSQL simulável. Produção pública,
autenticação externa e backup fora da máquina não fazem parte do laboratório.

## Etapas e progresso

- [x] Endpoints de saúde e métricas para API, consumer e Spark, com testes.
- [x] Rotina de backup local e verificação de restauração isolada.
- [x] Retenção configurável com simulação antes do expurgo e proteção do replay.
- [x] Visualização local de métricas por perfil opcional.
- [x] Validar o backup e a restauração end to end em containers descartáveis.
- [x] Documentar e automatizar validações operacionais no CI.
- [x] Delimitar escopo: somente laboratório local; sem deploy público.

## Contratos e decisões

Saúde operacional usa `/live`, `/ready` e `/metrics`; `/health` permanece compatível.
Métricas não incluem identificadores de corrida ou carro como labels. Corrida
pausada ou sem eventos não representa falha por si só. Liveness observa o loop;
readiness considera dependências e capacidade de progresso.

Backups mantêm o dump PostgreSQL e volumes MinIO/Kafka juntos; isso conserva os
arquivos Spark, checkpoints, schemas Avro e offsets. Checkpoints e metadados Spark
não sofrem expurgo separado dos Parquet. A retenção de payloads é explícita.

## Validação

Validado: `poetry run ruff check src tests stream-processing/spark scripts/backup_local.py`,
`poetry run mypy src`, `poetry run pytest -q`, teste Spark Compose, testes Node e
build frontend; configurações Compose local, de observabilidade e recuperação;
backup/restauração PostgreSQL, MinIO e schemas em projetos descartáveis; teste de
retenção e reexecução das migrações em schema temporário com rollback.

## Riscos e reversão

Timeouts curtos demais geram alarmes falsos; expurgo incorreto destrói deduplicação.
Backup no mesmo host não protege contra perda da máquina. O perfil de métricas é
optativo. Não habilite o `--apply` sem revisar a quantidade simulada.
