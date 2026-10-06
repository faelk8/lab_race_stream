# ADR 0013: nomes curtos para tópicos Kafka

- Estado: aceita.
- Data: 06/10/2026.

## Contexto

Os tópicos incluíam domínio e versão no nome, por exemplo
`race.analytics.v1`. Isso tornava os endereços do Console e a operação local
menos diretos. A versão já é registrada nos contratos Avro e nos próprios
eventos.

## Decisão

Novas publicações usam os nomes `telemetry`, `validated`, `timing`,
`lap_completed`, `pitstop`, `incident`, `control`, `state`, `analytics` e
`dead_letter`. O catálogo central `application/event_contracts.py` é a fonte dos
nomes usados pelos produtores e consumidores. O arquivador Spark e o job batch
usam os mesmos nomes. A versão dos dados permanece no schema e no evento.

Tópicos antigos não são apagados nem renomeados automaticamente: Kafka não
renomeia um tópico e sua exclusão removeria histórico. Eles podem continuar
visíveis para leitura; os serviços atualizados publicam e consomem os nomes
curtos.

## Consequências

- Os links do Redpanda Console ficam diretos e simples.
- A atualização simultânea dos produtores, consumers e Spark é necessária para
  manter o fluxo de eventos.
- O Schema Registry passa a registrar subjects sob os novos nomes de tópico; os
  schemas continuam versionados e compatíveis conforme as regras existentes.
- Em uma instalação que já arquiva tópicos antigos, a mudança de assinatura do
  Spark pode exigir recriação controlada do checkpoint para acompanhar os novos
  nomes, preservando os Parquet anteriores.
