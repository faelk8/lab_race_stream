# Troubleshooting

## A corrida não inicia

1. Verifique a mensagem mostrada pelo dashboard. A API retorna o motivo de
   validação, inclusive chuva iniciada tarde demais.
2. Confira a corrida mais recente:

   ```bash
   curl -fsS http://localhost:8000/api/races/latest
   ```

3. Confira logs e estado:

   ```bash
   docker compose ps
   docker compose logs --tail=200 api simulator postgres
   ```

Só pode existir uma corrida controlada ativa. Uma chamada repetida de início
retorna essa corrida em vez de criar outra.

## Configuração de chuva rejeitada

Todos os vinte carros recebem trocas separadas por duas a seis voltas. Com 60
voltas, a volta inicial máxima é 21. Reduza `rain_start_lap`, desative a chuva ou
aumente o total de voltas por configuração de ambiente antes de subir a stack.

## Dashboard sem atualização ao vivo

- confirme `api`, `consumer`, `kafka` e `schema-registry` ativos;
- abra o estado persistido em `/api/races/{race_id}/state`;
- verifique logs do consumer por falha de decodificação ou PostgreSQL;
- confirme `VITE_API_BASE_URL` no build/container do dashboard;
- observe no navegador se o WebSocket reconecta.

O WebSocket envia dados apenas da corrida indicada no caminho. Uma página aberta
em uma corrida encerrada não muda automaticamente para outro `race_id` sem que o
frontend atualize a corrida mais recente.

## Tópicos antigos ainda aparecem

Kafka não renomeia tópicos. A alteração para nomes curtos preservou os tópicos
anteriores e seus dados. Os serviços atuais usam os nomes retornados por:

```bash
curl -fsS http://localhost:8000/api/streaming
```

Não exclua tópicos históricos sem uma decisão explícita de retenção.

## Spark falha ao iniciar

Confira os logs:

```bash
docker compose logs --tail=300 spark-archive minio kafka schema-registry
```

Causas previstas:

- falha ao baixar pacotes Maven no primeiro início;
- limite de memória local;
- MinIO ou bucket indisponível;
- offsets Kafka removidos com `failOnDataLoss=true`;
- checkpoint incompatível após mudança do conjunto de tópicos.

O diretório Ivy fica no volume `spark-work`. O arquivador pode ser pausado sem
interromper API e consumer, desde que a parada não ultrapasse a retenção Kafka.

## Agregação Spark não encontra eventos

O job exige `lap_completed` e `analytics` já arquivados. Confirme que houve uma
corrida com voltas concluídas, que o arquivador processou os microbatches e que
os subjects/IDs continuam no Schema Registry.

## MinIO não abre nas portas 9000/9001

O projeto publica o serviço em `127.0.0.1:19000` e o Console em
`127.0.0.1:19001`. As portas 9000/9001 são internas ao Compose.

## PostgreSQL não aceita conexão no host

O serviço não publica a porta 5432. Essa escolha permite que apenas os
containers da rede Compose o acessem. Para diagnósticos, use o próprio container:

```bash
docker compose exec postgres \
  sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

## Volume antigo não aceita pneu `wet`

Os scripts `initdb` só rodam automaticamente em volume vazio, e o bootstrap
Python não reaplica o script `007`. Faça backup antes de qualquer intervenção e
verifique a constraint atual. Para aplicar a alteração aditiva existente:

```bash
docker compose exec -T postgres \
  sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
  < postgres/initdb/007_pneu_chuva.sql
```

## Serviços `topic-init` e `minio-init` aparecem como encerrados

Eles são tarefas one-shot. O estado encerrado com código zero é esperado. Falha
é indicada por código diferente de zero ou pela ausência dos tópicos/bucket.

## Reinício interrompeu uma corrida

O producer marca corridas controladas interrompidas como `stopped` no startup.
Não há recuperação do estado físico de uma corrida parcial. Inicie uma nova
sessão.

