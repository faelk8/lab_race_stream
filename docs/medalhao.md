# Camadas medalhão no MinIO

O Spark materializa resultados por corrida usando o arquivo Avro que já está em
`telemetry_raw`. O histórico original permanece intacto; cada corrida ganha um
prefixo próprio no mesmo bucket.

```text
s3://racestream/corridas/{race_id}/
├── bronze/eventos/             # envelopes Avro e metadados Kafka originais
├── prata/voltas/               # voltas concluídas
├── prata/pit_stops/            # eventos de parada
├── prata/telemetria_final/     # último quadro completo da prova
└── ouro/
    ├── classificacao/          # tabela Parquet para análise/dashboard
    └── resumo.json             # resposta consumida pela API
```

O arquivador verifica eventos `control` com `status=finished`. A transformação
aguarda até que o quadro completo da corrida mostre todos os carros finalizados,
então grava cada camada com substituição idempotente e escreve `resumo.json` por
último. Se o processo falhar antes do marcador, a varredura seguinte tenta
novamente.

Embora o arquivo bruto em `telemetry_raw` seja alimentado continuamente, as
camadas abaixo são materializadas após o encerramento da corrida; elas não são
calculadas a cada volta hoje.

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

## Evolução planejada: agregação incremental por volta

Uma evolução possível é preparar agregados em janelas por volta enquanto a
corrida acontece. A camada Bronze continuaria preservando os eventos brutos; as
camadas tratadas poderiam receber fatos e agregados de voltas concluídas. No
encerramento, Ouro consolidaria classificação e pódio a partir desses dados,
potencialmente reduzindo o tempo de geração do resultado. Isso ainda não está
implementado. A estratégia precisa definir reprocessamento de eventos atrasados,
idempotência, corridas pausadas/retomadas e correções de classificação por
penalidades antes de substituir o batch atual.

Os testes das regras Spark rodam sem Kafka, PostgreSQL ou MinIO:

```bash
docker compose --profile test run --rm spark-tests
```
