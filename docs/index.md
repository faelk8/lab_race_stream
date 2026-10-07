# Documentação técnica do RaceStream Lab

O RaceStream Lab é um laboratório local de sistemas orientados a eventos. Ele
simula uma corrida com vinte carros, publica fatos tipados no Apache Kafka,
mantém projeções operacionais no PostgreSQL, entrega atualizações ao painel por
WebSocket e arquiva o fluxo em Parquet no MinIO com Apache Spark.

Esta documentação foi produzida após a leitura do código, dos contratos Avro,
dos scripts SQL, dos Dockerfiles, do Docker Compose, dos testes, do frontend, dos
jobs Spark e dos documentos de decisão existentes em 06/10/2026. O README foi
usado como índice inicial, não como fonte de verdade.

## Objetivo e problema resolvido

O projeto fornece um cenário compreensível para estudar produção, ordenação,
validação, consumo, projeção, recuperação e arquivamento de eventos. A corrida
gera entidades independentes e situações observáveis, como voltas, parciais,
chuva, incidentes e pit stops, que tornam o comportamento distribuído visível no
painel e nos dados persistidos.

O resultado atual é um ambiente educacional e de portfólio executável em uma
máquina local. Ele não é uma plataforma de automobilismo de produção nem usa
medições oficiais de pista ou de veículos reais.

## Situação comprovada

| Capacidade | Situação |
| --- | --- |
| Simulação física e configurável de 20 carros | Implementada no serviço `simulator`, com grid inicial em duas colunas. |
| Eventos Kafka com contratos Avro | Implementados com Schema Registry. |
| Projeções online e histórico discreto | Implementados no consumer Python e PostgreSQL. |
| API REST e WebSocket | Implementados com FastAPI. |
| Painel de corrida | Implementado em React, TypeScript e SVG. |
| Arquivo histórico | Implementado em Parquet no MinIO por Spark Structured Streaming. |
| Agregados de volta e comparação de paridade | Implementados como job Spark batch sob demanda. |
| Protobuf, ClickHouse, Iceberg e Debezium | Não implementados. |
| Kubernetes, observabilidade completa e CI/CD | Não implementados. |

## Navegação

1. [Arquitetura](architecture.md) — componentes, tecnologias e estrutura.
2. [Fluxo de dados](data-flow.md) — comandos, eventos, projeções e arquivo.
3. [Serviços e APIs](services-and-apis.md) — processos, endpoints e entrypoints.
4. [Primeiros passos](getting-started.md) — instalação e execução.
5. [Configuração](configuration.md) — variáveis, portas e parâmetros.
6. [Persistência](persistence.md) — PostgreSQL, Kafka e MinIO.
7. [Spark](spark.md) — arquivamento, agregações e validação.
8. [Desenvolvimento](development.md) — organização, dependências e padrões.
9. [Testes](testing.md) — camadas, comandos e cobertura funcional.
10. [Deploy e CI/CD](deployment.md) — Compose e ausências atuais.
11. [Logs e observabilidade](observability.md) — logs, saúde e lacunas.
12. [Troubleshooting](troubleshooting.md) — falhas frequentes e diagnóstico.
13. [Decisões](decisions.md) — ADRs e decisões vigentes.
14. [Limitações e próximos passos](limitations.md) — limites comprovados e evolução.
15. [Dicionário de dados](dicionario-de-dados.md) — tópicos e contratos Avro.

Os planos de execução registram a evolução e as evidências históricas. Para
entender o estado atual, use primeiro os documentos desta página e depois os
[ADRs](decisions.md).
