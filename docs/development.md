# Desenvolvimento

## Pacote Python

O projeto é empacotado com `setuptools` a partir de `src/` e requer Python
3.12+. Não existem `requirements.txt`, `setup.py` ou `setup.cfg`; a fonte de
dependências é `pyproject.toml`.

Dependências de execução:

| Dependência | Faixa | Uso |
| --- | --- | --- |
| `confluent-kafka[avro]` | `>=2.6,<3` | Kafka, Avro e Schema Registry. |
| `fastapi` | `>=0.115,<1` | API REST e WebSocket. |
| `pydantic` | `>=2.8,<3` | Validação da API e do contrato histórico. |
| `psycopg[binary]` | `>=3.2,<4` | PostgreSQL. |
| `uvicorn[standard]` | `>=0.30,<1` | Servidor ASGI. |

Dependências opcionais de desenvolvimento: pytest 8, mypy 1 e Ruff.

## Tipagem e docstrings

O `pyproject.toml` configura mypy em modo `strict` e Ruff para Python 3.12. Os
módulos usam tipos nas APIs públicas e Protocols para as portas principais. A
auditoria sintática encontrou docstrings nas classes e funções públicas, exceto
a função interna de lifespan da API. Alguns módulos e docstrings históricos
permanecem em inglês; não há regra Ruff `D` ou outra ferramenta configurada para
validar presença e formato Sphinx das docstrings.

Portanto, a exigência de docstrings públicas existe nas instruções do projeto,
mas não é aplicada automaticamente pelo pipeline local.

## Entrypoints

| Comando | Uso |
| --- | --- |
| `python -m racestream.interfaces.producer` | Producer e simulador ativo. |
| `python -m racestream.interfaces.stream_processor` | Consumer online ativo. |
| `uvicorn racestream.interfaces.api:app` | API REST/WebSocket. |
| `python -m racestream.interfaces.consumer` | Consumer de logging do contrato histórico. |
| `spark-submit arquivo_telemetria.py` | Arquivador contínuo. |
| `spark-submit validar_arquivo.py` | Validação manual do Parquet. |
| `spark-submit agregar_voltas.py` | Agregação e paridade batch. |

Não há scripts declarados em `[project.scripts]`; os módulos são chamados
diretamente.

## Frontend

O frontend usa React 19, TypeScript 5.7, Vite 6 e `lucide-react`. O TypeScript
está em modo `strict`, sem emissão, com verificação de símbolos e parâmetros não
usados. O Dockerfile executa o servidor de desenvolvimento Vite; não existe
imagem de produção que sirva o conteúdo compilado.

Comandos disponíveis:

```bash
cd frontend
npm run dev
npm run typecheck
npm test
npm run build
```

## Contratos e evolução

Os contratos ativos ficam em `schemas/*-stream.avsc`. `telemetry-v1.avsc`,
`telemetry-v2.avsc` e `telemetry-v3.avsc` são contratos históricos usados pelo
adapter e pelos testes de compatibilidade. O `EventStream` registra os schemas
ativos por tópico com compatibilidade backward.

Mudanças incompatíveis exigem uma decisão arquitetural e uma estratégia de
migração. Os nomes dos tópicos não carregam versão; a versão permanece no
schema, namespace e campo `schema_version`.

## Fluxo recomendado de alteração

1. Leia `.agents/AGENTS.md`, o plano relacionado e as ADRs vigentes.
2. Altere primeiro regras puras e contratos, quando aplicável.
3. Atualize adapters, API e frontend conforme a fronteira afetada.
4. Execute Ruff, mypy, testes Python e verificações do frontend.
5. Valide o Compose e apenas as integrações necessárias.
6. Atualize plano, ADR e documentação conforme o resultado comprovado.

Não há gerador de código para Avro, OpenAPI ou clientes TypeScript. Os tipos do
frontend são mantidos manualmente.

