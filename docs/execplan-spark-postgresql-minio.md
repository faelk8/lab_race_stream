# Plano de execução: Spark, PostgreSQL e MinIO na corrida

Data: 06/10/2026. Estado: implementação entregue e validada nesta instalação.

## 1. Objetivo

Processar eventos da corrida com Spark Structured Streaming e manter os dados
operacionais no PostgreSQL e o arquivo durável de telemetria em MinIO/S3,
consultável em Parquet. O consumidor existente segue responsável pela projeção
online da API até que a paridade seja demonstrada.

## 2. Escopo

Inclui serviço local Spark, leitura Kafka com offsets recuperáveis, escrita
idempotente/recuperável no MinIO, configuração e inicialização de bucket,
checagem de integridade dos arquivos e documentação em português.
PostgreSQL continua registrando corridas, configurações, resultados e projeções.

A primeira etapa arquiva os envelopes Avro originais em Parquet preservando
payload binário e metadados Kafka. O Spark não substitui o consumer da API nesta
etapa. Iceberg, Debezium, cluster distribuído e migração da projeção online ficam
para incrementos posteriores. Outras melhorias de realismo serão planejadas
como incrementos separados após estabilizar persistência e processamento.

## 3. Estado anterior ao plano

Antes desta entrega, Kafka retinha eventos por sete dias e PostgreSQL guardava
metadados, resultados, passagens, voltas, projeções e outbox. Ainda não existiam
MinIO nem implementação Spark. As seções de progresso e validação registram o
estado entregue ao final do plano.

## 4. Arquitetura alvo

```text
Simulador -> Kafka -> consumer Python -> projeções/API e PostgreSQL
                    \-> Spark Structured Streaming -> Parquet -> MinIO
```

Spark lê Kafka com seu conector oficial e salva as mensagens Avro brutas junto
com tópico, chave, partição, offset e timestamp. A gravação Parquet usa
checkpoint persistente no MinIO para retomar micro-lotes sem duplicar arquivos.
A inicialização local cria o bucket necessário. Credenciais são configuração
local; endpoint S3 e caminho de checkpoint também são configuráveis.

## 5. Contratos

- Fonte atual: `telemetry`, `validated`, `timing`, `lap_completed`, `pitstop`,
  `incident`, `control`, `state`, `analytics` e `dead_letter`, com envelopes
  Kafka Avro. A mudança posterior de nomes está registrada na ADR 0013.
- Arquivo `telemetry_raw`: timestamp Kafka, tópico, partição, offset, chave e valor binário.
- Particionamento Parquet por tópico e data UTC do timestamp Kafka.
- Checkpoint dedicado ao consumidor de arquivo; offset inicial configurável apenas
  na primeira execução. Reinício normal restaura do checkpoint.
- PostgreSQL preserva seus contratos/migrações atuais e permanece autoridade para
  configuração, estado operacional, resultados e projeções de consulta.
- Retenção de Kafka continua sendo buffer; o MinIO passa a ser arquivo durável.

## 6. Etapas

1. Registrar decisão, topologia, riscos, execução e critérios de aceite.
2. Criar MinIO, bucket privado `racestream`, persistência local e health check.
3. Implementar job Spark com leitura de tópicos, arquivo Parquet e checkpoint S3A.
4. Ativar ingestão em Compose e fornecer limites modestos de memória/CPU.
5. Validar início, reinício com checkpoint, leitura Parquet e isolamento dos dados
   operacionais no PostgreSQL com uma pequena fixture, sem prova completa.
6. Documentar acessos, dados gravados, configuração, retomada e limitações.
7. Entrega seguinte: decodificar versões Avro registradas, agregar desempenho
   por carro e comparar com o analytics do consumer; melhorias de realismo ficam
   registradas no [plano interativo](execplan-corrida-interativa.md).

## 7. Testes e validação

- Testes de contrato da projeção Kafka para o esquema de arquivo.
- Checagem Compose e configuração sem subir serviços desnecessários.
- Integração local: publicar poucos eventos de fixture, verificar Parquet e metadados.
- Reiniciar Spark e confirmar uso do checkpoint sem duplicação.
- Confirmar PostgreSQL saudável e projeções existentes.
- Ruff, mypy e pytest pertinentes.

## 8. Riscos

- S3A e conectores precisam de versões compatíveis com Spark/Hadoop/Kafka.
- Falha ou perda do checkpoint pode exigir replay e gerar nova partição/arquivo;
  os dados incluem offsets para deduplicação analítica.
- Micro-lotes pequenos podem gerar arquivos pequenos; trigger configurável e
  compactação analítica ficam para fase seguinte.
- Spark consome mais RAM que o consumer atual; serviço terá execução local e
  limites reduzidos, podendo ser pausado com `docker compose stop spark-archive`.
- MinIO Community teve seu repositório arquivado em 2026. A imagem local compila
  tags fonte fixadas; manter o endpoint S3 como fronteira facilita troca futura.
- O uso e redistribuição do MinIO seguem a licença AGPLv3 e exigem avaliação
  apropriada para distribuição fora deste laboratório local.

## 9. Comandos de validação

```bash
docker compose config --quiet
.venv/bin/ruff check src tests stream-processing/spark
.venv/bin/mypy src tests
# Execute com Kafka e MinIO ativos; pausa o arquivador para respeitar o limite de memória.
docker compose stop spark-archive
docker compose run --rm --no-deps spark-archive --master 'local[1]' --driver-memory 512m --conf spark.jars.ivy=/opt/spark/work-dir/.ivy2 --packages org.apache.spark:spark-sql-kafka-0-10_2.13:4.0.1,org.apache.hadoop:hadoop-aws:3.4.1 /opt/racestream/validar_arquivo.py
docker compose up -d spark-archive
```

O agregado de voltas e a paridade com o consumer são executados conforme os
comandos do README. A execução validada em 06/10/2026 comparou 80 pares
corrida/carro e encontrou paridade em todos.

- O fluxo Kafka conserva eventos por sete dias. Se Spark ficar parado além dessa
  retenção, o checkpoint antigo poderá referir offsets removidos; `failOnDataLoss`
  encerra a consulta para exigir recuperação explícita, em vez de esconder a lacuna.

## 10. Decisões

- PostgreSQL não receberá cada amostra de alta frequência; armazena estado
  operacional e resultados. MinIO guarda o fluxo bruto completo.
- Avro bruto será preservado no arquivo para manter fidelidade e permitir reprocessar
  sem impor o Schema Registry aos consumidores analíticos já no primeiro passo.
- O Spark roda ao lado do consumer atual; substituir a projeção exige testes de
  paridade, replay e recuperação próprios.
- Versão inicial de Spark: 4.0.1, com conector Kafka 4.0.1 e S3A 3.4.1,
  confirmados com a imagem oficial `apache/spark:4.0.1-python3`.
- MinIO compilado das tags upstream `RELEASE.2025-10-15T17-29-55Z` e
  `RELEASE.2025-08-13T08-35-41Z` para o cliente `mc`, pois as imagens públicas
  foram removidas; compilação de fonte é o caminho atualmente indicado pelo projeto.

## 11. Progresso

- [x] Inspecionar serviços, contratos e plano vigente.
- [x] Registrar ADR e plano versionado.
- [x] Subir MinIO (porta S3 19000, Console 19001) e criar bucket persistente.
- [x] Implementar ingestão Spark Kafka para Parquet com checkpoint em S3A.
- [x] Validar leitura de 7.960 registros em 8 tópicos, sem offsets duplicados;
      o fluxo continua recebendo mensagens, então a contagem é uma amostra temporal.
- [x] Confirmar leitura do checkpoint e continuidade após reinício do serviço.
- [x] Atualizar README, retomada, plano mestre e ADR.
- [x] Criar agregado Spark de voltas e comparação com o analytics do consumer.
- [x] Verificar schemas writer por ID do Schema Registry para eventos históricos.
- [x] Confirmar 80/80 pares corrida/carro coincidentes no MinIO.


Validação de 06/10/2026: imagem oficial Spark 4.0.1 com Hadoop 3.4.1; MinIO
compilado das tags upstream fixadas e saudável; bucket `racestream` criado; job
Kafka→Parquet ativo. A validação leu 3.980 registros inicialmente e 7.960
depois do avanço do fluxo, em 8 tópicos e sem offsets duplicados. API, PostgreSQL,
Kafka e consumer ficaram ativos; Spark reiniciou usando o checkpoint S3A. Ruff,
mypy e `docker compose config --quiet` aprovados.
