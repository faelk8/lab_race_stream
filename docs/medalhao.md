# Camadas medalhão no MinIO

O Spark materializa resultados por corrida usando o arquivo Avro que já está em
`telemetry_raw`. O histórico original permanece intacto; cada corrida ganha um
prefixo próprio no mesmo bucket.

```text
s3://racestream/corridas/{race_id}/
├── bronze/eventos/             # envelopes Avro e metadados Kafka originais
├── bronze/janelas_volta/       # envelopes lap_completed agrupados por micro-lote
├── prata/voltas_incrementais/  # fatos de volta normalizados durante a prova
├── prata/agregados_volta/      # resumos por corrida/carro e micro-lote
├── prata/voltas/               # voltas concluídas
├── prata/pit_stops/            # eventos de parada
├── prata/telemetria_final/     # último quadro completo da prova
└── ouro/
    ├── classificacao/          # tabela Parquet para análise/dashboard
    └── resumo.json             # resposta consumida pela API
```

O arquivo bruto `telemetry_raw` continua recebendo eventos Kafka. Uma segunda
consulta Structured Streaming consome `lap_completed` e, em cada micro-lote,
grava o envelope em Bronze e os fatos e agregados em Prata. Os caminhos usam o
ID estável do micro-lote e são sobrescritos em caso de repetição; o checkpoint
separado permite retomar o consumo.

Quando chega um controle `finished`, o materializador aguarda um quadro completo
em que todos os carros estejam finalizados. Se a soma de voltas incrementais
coincidir com `laps_completed` de cada carro, usa os fatos e agregados preparados
para montar a classificação Ouro sem decodificar novamente todas as voltas. Se
a consulta estiver atrasada ou a cobertura não fechar, usa os eventos brutos
arquivados como fallback. As camadas consolidadas são gravadas idempotentemente e
`resumo.json` é escrito por último; se a transformação falhar antes do marcador,
a varredura seguinte tenta novamente.

A classificação ouro é ordenada por posição e contém piloto, país, equipe,
melhor e pior volta, média de voltas válidas, quantidade de paradas concluídas,
quantidade de voltas válidas, troféu e medalha de pódio. Eventos de box nas fases
`entry`, `service_started` e `service_finished` não são contados como paradas
adicionais; a saída da vaga identifica a conclusão. O total também é comparado
ao contador final da telemetria.

O endpoint `GET /api/races/{race_id}/medalhao` lê `ouro/resumo.json`. Até o Spark
concluir as camadas, responde `404`; o painel tenta novamente a cada dois
segundos e abre a janela assim que o resultado estiver disponível. O fundo da
janela tem 50% de opacidade e o painel permanece opaco para manter o texto nítido.
O único controle da janela é o botão de fechar no canto superior esquerdo.

## Comportamento e limites da agregação incremental

As janelas são micro-lotes de eventos `lap_completed` recebidos pelo Kafka, não
uma janela fixa de tempo nem processamento de todos os tipos de telemetria.
Paradas, estado final e Bronze completo por corrida ainda são consolidados no
encerramento. O caminho rápido de Ouro depende da igualdade entre voltas
processadas e `laps_completed`; divergências preservam o fallback batch.

Os testes das regras Spark rodam sem Kafka, PostgreSQL ou MinIO:

```bash
docker compose --profile test run --rm spark-tests
```
