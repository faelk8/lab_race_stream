# Plano de execução: documentação técnica baseada no repositório

Data: 06/10/2026. Estado: concluído.

## 1. Objetivo

Documentar a implementação comprovada do RaceStream Lab, transformar o
`README.md` em uma página inicial concisa e corrigir referências obsoletas sem
alterar o comportamento funcional da aplicação.

## 2. Escopo

Inclui código Python, frontend, schemas Avro, SQL, Dockerfiles, Docker Compose,
Spark, testes, configurações, integrações locais, ADRs e planos existentes.
Inclui a validação dos comandos publicados. Não inclui novas funcionalidades,
mudanças de contrato, migrações de dados ou serviços de infraestrutura.

## 3. Estado encontrado

- A stack executável usa simulador Python, Kafka, Schema Registry, consumer
  Python, PostgreSQL, FastAPI, WebSocket, React, Spark e MinIO.
- Spark arquiva os envelopes Kafka e executa agregações batch; o consumer Python
  mantém as projeções online.
- Não há implementação de Protobuf, ClickHouse, Iceberg, Debezium, Kubernetes,
  OpenTelemetry, Prometheus, Grafana ou GitHub Actions.
- O repositório contém documentação histórica correta, mas também referências
  anteriores aos nomes curtos dos tópicos e à entrega de Spark/MinIO.
- `.env.example` ainda aponta `KAFKA_TOPIC` para o nome antigo.

## 4. Arquitetura afetada

Nenhum componente de execução será alterado. A documentação passa a refletir os
seguintes fluxos:

```text
simulator -> Kafka -> consumer Python -> PostgreSQL/Kafka derivado
Kafka derivado -> FastAPI/WebSocket -> dashboard
Kafka -> Spark Structured Streaming -> Parquet no MinIO
MinIO -> Spark batch -> agregados Parquet
```

## 5. Etapas

1. Inventariar arquivos, dependências, entrypoints, serviços e contratos.
2. Conferir API, persistência, observabilidade, testes e deploy no código.
3. Registrar inconsistências entre README, planos, ADRs e implementação.
4. Criar a documentação técnica navegável em `docs/`.
5. Atualizar o README e corrigir documentos/configurações obsoletos.
6. Validar links, comandos, formatação, testes e configuração Compose.

## 6. Estratégia de validação

- conferir links Markdown locais;
- executar Ruff e mypy sobre o código Python;
- executar pytest, incluindo a integração Kafka quando a stack estiver ativa;
- executar testes, typecheck e build do frontend;
- validar `docker compose config --quiet`;
- confirmar que nenhum componente ausente passou a ser apresentado como pronto.

## 7. Riscos

- Documentar como atual uma decisão que era apenas histórica. Mitigação: usar o
  código e a configuração executável como fonte de verdade e marcar ADRs
  substituídas.
- Publicar um comando que depende de infraestrutura não exposta ao host.
  Mitigação: distinguir execução integral pelo Compose de desenvolvimento local.
- Ocultar limitações de migração e operação. Mitigação: manter uma seção própria
  de limitações e troubleshooting.

## 8. Decisões

- O README será uma página inicial; detalhes ficarão nos documentos temáticos.
- Docker Compose será apresentado como o único modo integral de execução
  comprovado no repositório.
- Ausências de implementação serão marcadas com a frase solicitada pelo usuário.
- ADRs antigas serão preservadas como histórico e ligadas às decisões que as
  substituíram.

## 9. Progresso

- [x] Inventário completo do repositório.
- [x] Auditoria de arquitetura, contratos, dependências, testes e entrypoints.
- [x] Levantamento das inconsistências documentais.
- [x] Criar documentação temática.
- [x] Atualizar README e documentos obsoletos.
- [x] Executar validações e registrar os resultados.

## 10. Resultado das validações

- `ruff check src tests`: aprovado.
- `npm test`, `npm run typecheck` e `npm run build`: aprovados no frontend.
- `docker compose config --quiet`: aprovado.
- verificação dos links Markdown locais: aprovada.
- busca por referências documentais removidas: nenhuma ocorrência encontrada.
- `mypy src tests`: não aprovado por quatro erros preexistentes de tipagem em
  `tests/unit/test_physical_stream.py`.
- `pytest tests/unit -q`: não concluiu dentro do limite de dez minutos e foi
  interrompido sem apresentar falha. As mudanças funcionais posteriores devem
  usar testes direcionados para evitar simulações excessivas.
