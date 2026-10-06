# ADR 0011: Spark, PostgreSQL e MinIO para dados da corrida

- Estado: aceito para implementação incremental
- Data: 06/10/2026

## Contexto

A corrida já publica eventos Avro no Kafka. PostgreSQL guarda configuração,
estado operacional, resultados e projeções de consulta. É necessário manter o
histórico de alta frequência além da retenção do Kafka e introduzir Spark sem
acoplar os serviços da API ao motor.

## Decisão

Manter PostgreSQL para dados transacionais/operacionais e usar Spark Structured
Streaming para copiar o fluxo Kafka para arquivos Parquet duráveis em MinIO via
S3A. O arquivo inicial preserva valor Avro binário, tópico, chave, partição,
offset e timestamp Kafka. A consulta online segue no consumer Python e PostgreSQL
até haver provas de paridade para uma eventual substituição.

## Consequências

- O arquivo MinIO é recuperável e particionado para análise; Kafka deixa de ser a
  única fonte histórica de telemetria.
- Checkpoint S3A permite retomada do Spark. Eventos incluem offsets Kafka para
  auditoria e deduplicação se houver recuperação manual.
- Dados de cadastro e estado transacional não são duplicados no objeto Parquet.
- Spark aumenta consumo de memória; o perfil local limita paralelismo e permite
  desligar a ingestão quando não for necessária.
- MinIO Community foi arquivado em 2026 e as imagens/binários públicos foram
  removidos. A imagem local compila tags fonte fixadas, sob AGPLv3. A integração usa API S3
  para permitir substituição futura sem alterar contratos de evento.
- Iceberg e tabelas refinadas ficam para etapa própria após validação do arquivo.

## Alternativas consideradas

- Gravar toda telemetria em PostgreSQL: aumenta custo e carga operacional sem
  oferecer armazenamento de objetos adequado para arquivo histórico.
- Spark substituir imediatamente o consumer Python: risco de interromper a API
  sem paridade demonstrada.
- Manter apenas Kafka: retenção limitada não atende ao arquivo de longo prazo.
