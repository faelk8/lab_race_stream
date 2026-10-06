# Plano de execução: Spark, PostgreSQL e MinIO na corrida

Data: 06/10/2026. Estado: em implementação incremental.

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

## 3. Estado atual

Kafka retém eventos por sete dias. PostgreSQL guarda metadados, resultados,
passagens, voltas, projeções e outbox. Não existe MinIO nem implementação Spark.
A telemetria Avro é publicada em tópicos versionados e consumida pelo serviço
Python.

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

- Fonte: tópicos `race.*` com envelopes Kafka Avro já existentes; sem mudar schemas.
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
7. Próximos incrementos: decodificação/tabelas refinadas, agregados Spark,
   comparação de comportamento com o consumer atual e melhorias de realismo.

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
  limites reduzidos, além de poder ser desativado por perfil Compose.
- MinIO Community teve seu repositório arquivado em 2026. Fixar uma versão
  disponível e registrar a limitação; manter o endpoint S3 como fronteira facilita
  troca futura por outro armazenamento compatível.

## 9. Decisões

- PostgreSQL não receberá cada amostra de alta frequência; armazena estado
  operacional e resultados. MinIO guarda o fluxo bruto completo.
- Avro bruto será preservado no arquivo para manter fidelidade e permitir reprocessar
  sem impor o Schema Registry aos consumidores analíticos já no primeiro passo.
- O Spark roda ao lado do consumer atual; substituir a projeção exige testes de
  paridade, replay e recuperação próprios.
- Versão inicial de Spark: 4.0.1, com conector Kafka 4.0.1 e S3A alinhado ao
  Hadoop da imagem; confirmar dependências na construção da imagem.

## 10. Progresso

- [x] Inspecionar serviços, contratos e plano vigente.
- [ ] Registrar ADR e plano versionado.
- [ ] Subir MinIO e criar bucket persistente.
- [ ] Implementar ingestão Spark Kafka para Parquet com checkpoint.
- [ ] Validar integração e reinício.
- [ ] Atualizar README, retomada e Jota.
