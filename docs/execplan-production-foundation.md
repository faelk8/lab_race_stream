# ExecPlan: persistência, testes e preparação operacional

Data: 07/10/2026. Estado: fundação implementada; produção irrestrita permanece
bloqueada pelas pendências de segurança e operação listadas no plano operacional.

## 1. Objetivo

Entregar os cinco itens priorizados pelo usuário: persistência do rascunho de
eventos, testes automatizados Spark/paridade, controle de versões de migração,
plano de CI/observabilidade/backup e artefatos iniciais para deploy de produção.

## 2. Entregas

- [x] Salvar chuva e incidentes em `localStorage` com validação e versão; permitir
  limpar o rascunho e restaurar o formulário após recarga.
- [x] Extrair agregação Spark e comparação com o consumer para transformações
  testáveis e executar fixtures com Spark local, sem dados operacionais.
- [x] Registrar migrações aplicadas em `schema_migrations` com versão, arquivo,
  checksum e instante; recusar mudança retroativa do SQL.
- [x] Adicionar workflow GitHub Actions para Ruff, mypy, pytest, frontend, Spark e
  validação Compose.
- [x] Documentar readiness, métricas, backup, restauração e retenção com o estado
  atual e critérios propostos.
- [x] Criar build estático Nginx, proxy de API/WebSocket same-origin e overlay
  Compose com Caddy TLS/autenticação básica e portas internas fechadas.
- [x] Documentar limites; não declarar a instalação de nó único pronta para
  exposição irrestrita.

## 3. Verificação

- Frontend: testes Node e build TypeScript/Vite.
- Python: Ruff, mypy e suíte pytest completa.
- Spark: script de teste em `stream-processing/spark/tests/`, via perfil Compose
  `test`, usando fixtures e `local[1]`.
- Compose: validação da topologia local, perfil de teste e overlay de produção.
- Imagem estática: build do `frontend/Dockerfile.prod`.
- Migrações: testes unitários de ordenação, idempotência e checksum; API local
  recriada e saudável, com as versões 001 a 009 registradas no PostgreSQL.

## 4. Pendências antes de produção

- Teste ponta a ponta que leia envelopes Avro reais, Parquet e Schema Registry.
- Exercitar upgrade e falha/rollback de migração em PostgreSQL isolado.
- Implementar endpoints/checagens de readiness e métricas para consumer e Spark.
- Escolher RPO/RTO, automatizar backup PostgreSQL/MinIO e testar restauração.
- Revisar autenticação individual, segurança interna Kafka, redundância e
  operação com domínio/segredos reais antes de exposição externa.
