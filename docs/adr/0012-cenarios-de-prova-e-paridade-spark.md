# ADR 0012: cenários reproduzíveis e paridade analítica com Spark

- Estado: aceita.
- Data: 06/10/2026.

## Contexto

O painel iniciava uma corrida sem controlar clima ou incidentes. A corrida já
arquivava envelopes Avro no MinIO, mas ainda não calculava agregados de domínio
em Spark nem verificava os resultados contra o consumer online.

## Decisão

A configuração da corrida persiste chuva e incidentes determinísticos em JSONB
no PostgreSQL. O worker recupera a configuração ao reservar a largada. Chuva
reduz velocidade máxima e aderência conforme intensidade; furo de pneu agenda
parada emergencial para troca; colisão programada retira os dois carros. Esses
eventos não adicionam campos aos schemas Kafka existentes.

Um job Spark batch lê do MinIO as voltas concluídas e os snapshots de analytics
arquivados. Para cada envelope Confluent, consulta o Schema Registry pelo ID do
schema writer e usa a versão mais recente compatível como reader. Grava
desempenho por carro e uma tabela de paridade em Parquet no mesmo bucket. O
consumer continua autoridade para a projeção ao vivo; Spark não o substitui.

## Consequências

- Corridas com os mesmos parâmetros e seed reproduzem os incidentes no mesmo
  ponto da volta.
- PostgreSQL mantém configuração transacional e MinIO mantém histórico bruto e
  analítico; Kafka permanece transporte e buffer.
- A execução analítica é acionada sob demanda e não aumenta continuamente o
  consumo de RAM do arquivador.
- A comparação depende das versões do Schema Registry ainda disponíveis para os
  IDs presentes nos envelopes arquivados.
- Desaceleração até a vaga, neutralização, bandeiras e penalidades continuam
  sendo etapas futuras.
