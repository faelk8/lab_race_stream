# ADR 0014: Spark como único motor de processamento distribuído

- Estado: aceita.
- Data: 06/10/2026.

## Contexto

A documentação listava motores de processamento alternativos, embora a stack
local já usasse Spark Structured Streaming para arquivar Kafka no MinIO e Spark
batch para gerar agregados. A projeção de estado e as análises do painel em
tempo real são calculadas pelo consumer Python e persistidas no PostgreSQL.

## Decisão

Adotar Apache Spark como o único motor de processamento distribuído deste
projeto. Manter o consumer Python para validação e projeções online enquanto
Spark executa o arquivamento contínuo e as análises batch existentes. Uma
migração dessas projeções para Spark só deve ocorrer com critérios de paridade,
replay e recuperação comprovados.

## Consequências

- A configuração, os planos e o README descrevem apenas Spark como motor de
  processamento distribuído.
- A stack continua local em Docker Compose; a escolha de Spark não implica
  adoção de Kubernetes ou serviços de nuvem.
- PostgreSQL permanece o único banco relacional atual. MinIO guarda objetos
  Parquet; Kafka é o transporte e buffer dos eventos.
- ClickHouse, Iceberg, CDC e observabilidade seguem como incrementos futuros,
  não como capacidades já entregues.
- Os testes comparam os agregados batch do Spark com as projeções do consumer
  usando fixtures e dados arquivados.
