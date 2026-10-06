# RaceStream Lab

Laboratório de Engenharia de Dados e Sistemas Distribuídos para simular uma corrida com 20 carros gerando telemetria em tempo real.

## Objetivo

Construir uma plataforma orientada a eventos capaz de:

- simular 20 carros com estado independente;
- publicar telemetria em Apache Kafka;
- validar contratos com Schema Registry;
- serializar eventos com Avro ou Protobuf;
- processar streams com Apache Flink **ou** Spark Structured Streaming/PySpark;
- expor estado em tempo real via FastAPI + WebSocket;
- mostrar carros em movimento em uma pista no frontend;
- persistir histórico analítico em ClickHouse;
- arquivar telemetria bruta em Parquet no MinIO/S3;
- preparar dados curados em Apache Iceberg em uma etapa futura;
- suportar CDC com Debezium;
- executar inicialmente com Docker Compose e depois Kubernetes;
- aplicar observabilidade com OpenTelemetry, Prometheus e Grafana;
- automatizar testes e deploy com GitHub Actions.

## Princípio de arquitetura

O restante do sistema não deve depender diretamente de Flink ou Spark.

O motor de processamento deverá ser substituível através de contratos estáveis de entrada e saída:

```text
Kafka telemetry.raw
        |
        v
+-----------------------+
| Stream Engine         |
|                       |
| Flink                 |
|        OU             |
| Spark Structured      |
| Streaming / PySpark   |
+-----------+-----------+
            |
            v
Kafka race.state / analytics / events
```

## Documentos

- `AGENTS.md`: regras permanentes para o Codex.
- [Plano de refinamento da corrida](docs/execplan-refinamento-corrida.md): etapas e evidências de telemetria, cronometragem e painel.
- [Regras propostas da corrida v2](docs/planejamento/regras-corrida-v2.md): especificação de frequência, parciais, classificação, acompanhamento e força G.
- `docs/execplan-console.md`: plano de acesso ao Kafka pelo Redpanda Console.
- `docs/execplan-pelotao.md`: identificação dos carros e classificação do pelotão.
- `docs/execplan-controle-corrida.md`: início e parada pelo painel.
- `.agents/`: instruções e planos locais, não versionados.
- `docs/adr/`: decisões arquiteturais aceitas.

## Executar a corrida

Plano da integração analítica: [Spark, PostgreSQL e MinIO](docs/execplan-spark-postgresql-minio.md); decisão arquitetural em [ADR 0011](docs/adr/0011-spark-postgresql-minio.md).
Os cenários e a comparação Spark estão detalhados no
[plano de corrida interativa](docs/execplan-corrida-interativa.md) e na
[ADR 0012](docs/adr/0012-cenarios-de-prova-e-paridade-spark.md).

Pré-requisitos: Docker com Compose. A instalação Python local é necessária apenas para executar testes e ferramentas de desenvolvimento.

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
docker compose up --build
```

O Compose inicia PostgreSQL, Kafka, Schema Registry, Redpanda Console, MinIO, Spark, API, dashboard, simulador e consumer. O simulador aguarda o botão **Iniciar corrida** no painel. A prova termina pela passagem na chegada após 60 voltas do líder; os demais encerram na passagem seguinte. A física usa passos de 20 ms, com reprodução acelerada em 45 vezes por padrão. Cada carro publica um snapshot Avro por segundo real, além dos eventos de passagem. A duração real depende do ritmo e dos boxes; não há encerramento artificial aos 120 segundos.

O painel é uma página desktop (largura mínima de 1.100 px). Antes da largada,
configure chuva (volta inicial e intensidade) e incidentes: furo de pneu agenda
uma parada emergencial para troca; colisão retira os dois carros envolvidos.
Os eventos são reproduzíveis e ocorrem na metade da volta selecionada.

### Links de acesso

Abra os links abaixo no navegador da máquina onde o Docker Compose está executando:

| Serviço | Link | Para que serve |
| --- | --- | --- |
| Painel da corrida | [Ver a corrida ao vivo](http://localhost:5173) | Acompanhar os carros na pista, classificação, telemetria e configurações. |
| Redpanda Console | [Acessar o Kafka](http://localhost:8080) | Consultar tópicos, mensagens, partições, grupos de consumidores e schemas. |
| Documentação da API | [Abrir a documentação OpenAPI](http://localhost:8000/docs) | Consultar e testar os endpoints da API. |
| Schema Registry | [Listar os schemas registrados](http://localhost:8081/subjects) | Consultar os contratos Avro registrados. |
| Console MinIO | [Ver o arquivo da corrida](http://localhost:19001) | Inspecionar o bucket `racestream` (credenciais locais definidas por `MINIO_ROOT_USER` e `MINIO_ROOT_PASSWORD`). |

No Redpanda Console, abra a seção **Topics**, selecione `race.telemetry.raw.v4` e
acesse **Messages** para inspecionar a telemetria dos carros. Para acompanhar a
corrida visualmente, use o link do painel acima.

O Kafka também aceita conexões de clientes locais em `localhost:9092`.

Se os serviços já estiverem rodando, inicie somente o Console com:

```bash
docker compose up -d redpanda-console
```

A configuração do Console segue a
[documentação oficial do Redpanda](https://docs.redpanda.com/streaming/current/console/config/configure-console/).


PostgreSQL fica somente na rede interna do Compose para não conflitar com bancos já instalados no host. A API e o runner salvam configurações, corridas e resultados. O consumer mantém passagens, voltas, projeções e uma outbox operacional. O Spark Structured Streaming arquiva em Parquet no MinIO os envelopes Avro originais recebidos do Kafka, com tópico, partição, offset, chave, cabeçalhos e horário. O checkpoint do Spark também fica no MinIO para retomar após reinício. Spark usa inicialmente os offsets ainda retidos no Kafka, processa até 1.000 eventos por micro-lote de 30 segundos e pode ser pausado com `docker compose stop spark-archive`.

O arquivo analítico usa o bucket `racestream`, nos caminhos `telemetry_raw/` e
`_checkpoints/spark_kafka_archive_v1/`. O checkpoint preserva offsets entre
reinícios. Para acompanhar o processador:

```bash
docker compose logs -f spark-archive
```

Para materializar o agregado de desempenho por carro e comparar voltas válidas,
melhor volta e pior volta com a última análise do consumer arquivada no Kafka,
pause brevemente o arquivador e execute:

```bash
docker compose stop spark-archive
docker compose run --rm --no-deps spark-archive \
  --master 'local[1]' --driver-memory 512m \
  --conf spark.jars.ivy=/opt/spark/work-dir/.ivy2 \
  --packages org.apache.spark:spark-avro_2.13:4.0.1,org.apache.hadoop:hadoop-aws:3.4.1 \
  /opt/racestream/agregar_voltas.py
docker compose up -d spark-archive
```

O resultado fica em `lap_performance/` e `consumer_parity/` no bucket
`racestream`. `paridade=true` indica que a contagem, a melhor volta e a pior
volta calculadas em lote coincidem com o resumo online. A comparação usa os
eventos `race.lap.completed.v1` e `race.analytics.v1` arquivados pelo mesmo job.
O job obtém do Schema Registry os schemas writer de cada ID Avro e usa a versão
compatível mais recente como schema de leitura, incluindo eventos históricos.

MinIO está publicado apenas em `localhost:19000` (S3) e `localhost:19001`
(Console). As credenciais locais padrão são `racestream` e
`racestream-local-only`; substitua por `MINIO_ROOT_USER` e
`MINIO_ROOT_PASSWORD` no ambiente local. PostgreSQL mantém estado operacional,
configurações, resultados e projeções. MinIO mantém telemetria histórica bruta.

Para acompanhar apenas o consumer em outro terminal:

```bash
docker compose logs -f consumer
```

O Schema Registry fica disponível em `http://localhost:8081`; o Kafka para clientes locais em `localhost:9092`. Os tópicos usam seis partições. Fatos de um carro usam `car_id`; controle, estado e análises agregadas usam `race_id`. O Spark lê os tópicos versionados e mantém os envelopes Kafka originais em Parquet no MinIO.

Para validar o código:

```bash
.venv/bin/ruff check src tests
.venv/bin/pytest
.venv/bin/mypy src tests
docker compose config --quiet
RUN_KAFKA_INTEGRATION=1 .venv/bin/pytest tests/integration -q
npm --prefix frontend ci
npm --prefix frontend run build
```

O teste Kafka requer os serviços ativos. Encerre com `Ctrl+C` no terminal do Compose ou execute `docker compose down`; os dados de Kafka, PostgreSQL e MinIO são mantidos nos volumes. `docker compose down -v` remove esses dados. O primeiro build do MinIO compila as versões fonte fixadas pelo projeto; o Spark baixa seus conectores Kafka e S3A no primeiro início.

## Simulação e setup

Os vinte carros recebem configurações distintas de peso do carro, peso do piloto, velocidade máxima e composto. O editor do dashboard salva as mudanças no PostgreSQL; elas passam a valer na corrida seguinte.

No modelo físico v4, os compostos ajustam a aderência lateral: macio `+1%`, médio base e duro `−1%`, configuráveis na pista. Os tempos de volta são medidos nos cruzamentos de linha, sem somar descontos artificiais. O mapa usa `track_progress` normalizado e a fonte do SVG está registrada em `frontend/public/ATTRIBUTION.md`.

O simulador reduz velocidade e marcha ao se aproximar das zonas de curva, mantém a aceleração controlada durante o contorno e volta a acelerar na saída até atingir a velocidade máxima configurada. Os carros têm 3 m de comprimento e mantêm essa separação na mesma faixa; duplas podem disputar ultrapassagens nas retas; a fase atual (`reta`, `frenagem` ou `curva`) aparece no dashboard.

Caches locais do Brave/JetBrains e artefatos `frontend/node_modules`/`frontend/dist` são ignorados pelo Git.

Spark já arquiva o fluxo bruto no MinIO. Flink, Iceberg, ClickHouse, CDC e Kubernetes continuam em etapas futuras.

### Regras atualizadas de corrida

A especificação está em [corrida.md](.agents/corrida.md) e as decisões de interpretação
em [ADR 0007](docs/adr/0007-corrida-rules.md). São 10 equipes (4 A, 4 B e 2 C),
com 2 carros cada, massa seca de 500/510/515 kg e pilotos com altura de 1,60–1,90 m.
O tanque comporta 110 kg. O novo consumo nominal é de 218,9 kg por 60 voltas
(1,99 tanque): a redução de 0,5% permite a estratégia A de uma parada antes da
metade da prova. Com exatamente 220 kg, essa combinação não tinha autonomia.
O serviço leva o maior valor entre os 3–6 segundos configurados e o tempo de
abastecimento a 12 kg/s, além do trânsito dos boxes limitado a 60 km/h.

A telemetria v3 acrescenta pressão dos pneus, número de paradas e faixa de
ultrapassagem, com defaults compatíveis com eventos Avro v1/v2.

**Estratégia C atualizada:** larga com meio tanque e para a 20%. Na primeira
parada, abastece até 50% e troca pneus; na segunda, enche o tanque; na terceira,
abastece somente o necessário para terminar a prova e mais uma volta de reserva.
O cálculo desconta o combustível que ainda está no tanque. Em uma prova de
60 voltas, a reserva atual corresponde a aproximadamente 3,65 kg.

A inicialização da API/runner aplica a migração idempotente em volumes existentes,
substituindo apenas os setups antigos intactos. Configurações personalizadas e
resultados históricos são preservados. Para aplicar manualmente:

```bash
docker compose up -d postgres
docker compose exec -T postgres psql -U racestream -d racestream -v ON_ERROR_STOP=1 -f /docker-entrypoint-initdb.d/002_corrida_rules.sql
```

As duas simulações anteriores à terceira parada (seeds 42 e 7) estão registradas em
[docs/validation/corrida-simulations.json](docs/validation/corrida-simulations.json).

Após incluir a terceira parada, uma nova simulação com semente 42 confirmou
três paradas para todos os carros da estratégia C, nenhum abandono e combustível
para a distância restante mais uma volta de reserva. Os resultados estão em
[docs/validation/corrida-terceira-parada.json](docs/validation/corrida-terceira-parada.json).

### Identificação dos carros e classificação

O mapa mostra um balão compacto para cada carro, com seu identificador e posição
atual, por exemplo `CAR-01 · P1`. No pelotão, cada linha mostra a bandeira do país,
o nome do piloto, a equipe e o carro, em ordem do primeiro ao último colocado.
Os pilotos iniciais são fictícios; nome e país podem ser alterados no painel.

A coluna **DIF. LÍDER** usa uma passagem cronometrada comum a todos os carros,
compatível com a classificação do quadro. Enquanto não existe referência,
mostra `—`. A referência e sua idade aparecem no acompanhamento. Melhor volta
individual não determina posição de corrida. Quadros parciais conservam a ordem
anterior e identificam carros atrasados; análises de outro quadro não fornecem
gaps para a classificação atual.

Selecione carro, piloto ou equipe para ver última, melhor e pior volta, volta
teórica, ritmo das cinco últimas voltas limpas, intervalos e parciais comparadas
com a melhor pessoal, da equipe ou da corrida. O histórico permanece disponível
ao recarregar a página. A força G horizontal deriva da velocidade e dos raios
aproximados da pista; não representa uma medição no corpo de um piloto real.

A migração de identidade é aplicada automaticamente ao iniciar API/simulador;
os nomes e países existentes são preservados. Para validar a apresentação:

```bash
npm --prefix frontend test
npm --prefix frontend run build
```

As decisões estão documentadas na
[ADR 0008](docs/adr/0008-identificacao-e-classificacao-do-pelotao.md).

## Iniciar e parar pelo painel

Acesse o [painel da corrida](http://localhost:5173) e use:

- **Iniciar corrida**: cria uma nova prova com as configurações atuais dos carros.
- **Parar corrida**: encerra a prova atual e salva a classificação parcial. Para
  voltar a correr, inicie outra prova; a corrida encerrada permanece no histórico.

Os botões ficam desabilitados quando a ação não se aplica. Ao terminar ou parar,
o simulador aguarda outro início, sem reiniciar automaticamente. Ao reiniciar o
processo, uma corrida que estava em execução é marcada como parada.

A API também oferece `POST /api/races/start` e
`POST /api/races/{race_id}/stop`, disponíveis no
[Swagger](http://localhost:8000/docs). Pedidos repetidos de início enquanto uma
prova está ativa retornam o mesmo identificador. Uma solicitação pendente pode
ser cancelada antes da largada. O Compose utiliza um único processo de simulação.

A migração `004_race_control.sql` é aplicada na inicialização da API/simulador,
preservando configurações e resultados anteriores. Os estados operacionais são
`queued`, `running`, `stopping`, `stopped`, `finished` e `failed`.

## Tópicos por tipo de informação

Todos podem ser consultados em [Kafka / Redpanda Console](http://localhost:8080/topics).

| Tópico | Conteúdo |
| --- | --- |
| `race.telemetry.raw.v4` | Snapshot de cada carro a 1 Hz, velocidade, posição, combustível e G. |
| `race.telemetry.validated.v4` | Telemetria aceita pelo consumer. |
| `race.timing.crossed.v1` | Passagens nos 15 checkpoints, finais de setor e chegada. |
| `race.lap.completed.v1` | Voltas consolidadas com os três setores. |
| `race.pitstop.v1` | Entrada, serviço, combustível adicionado e saída dos boxes. |
| `race.incident.v1` | Abandono e motivo. |
| `race.control.v1` | Início/fim/parada, escala, participantes e regras congelados. |
| `race.state.v1` | Quadros de classificação usados pelo mapa e pelotão. |
| `race.analytics.v1` | Resumos de voltas, parciais, ritmo e intervalos medidos. |
| `race.dead-letter.v1` | Eventos rejeitados, motivo e tópico/partição/offset de origem. |

Os contratos v1/v2/v3 anteriores continuam no repositório; o painel atual usa os
derivados v4. O tópico legado `race.telemetry.raw` não recebe novas corridas.
A retenção dos novos tópicos é de sete dias. As tabelas operacionais de sessões e
passagens não têm expurgo automático nesta entrega; não substituem o futuro
armazenamento analítico. Debezium não é necessário para este fluxo direto.

Para velocidade de relógio normal, recrie os serviços com a mesma escala:

```bash
RACE_TIME_SCALE=1 docker compose up -d api simulator
```

A configuração está em [config/interlagos-v1.json](config/interlagos-v1.json).
Setores, checkpoints, raios e traçado dos boxes são aproximações do laboratório,
não coordenadas oficiais. As 15 curvas do circuito não são os três setores.
`RACE_DURATION_SECONDS` permanece apenas para compatibilidade com o modelo antigo.

## Sincronização com o Jota local

O código e a documentação reconhecidos pelo indexador são atualizados no
PostgreSQL do Jota a cada dois minutos enquanto a sessão do usuário está ativa.
A API fica restrita a [localhost:8765](http://127.0.0.1:8765/health). A indexação
respeita as exclusões do Jota e do Git; não copia a conversa inteira nem credenciais.
O índice inclui arquivos ainda não commitados: consulte o plano para distinguir
implementação em andamento de comportamento validado. A projeção no Neo4j é
separada; este timer confirma a atualização no PostgreSQL.

As unidades são específicas desta instalação Ubuntu:

```bash
install -Dm644 integrations/systemd/jota-api.service ~/.config/systemd/user/jota-api.service
install -Dm644 integrations/systemd/jota-racestream-sync.service ~/.config/systemd/user/jota-racestream-sync.service
install -Dm644 integrations/systemd/jota-racestream-sync.timer ~/.config/systemd/user/jota-racestream-sync.timer
systemctl --user daemon-reload
systemctl --user enable --now jota-api.service jota-racestream-sync.timer
systemctl --user start jota-racestream-sync.service
journalctl --user -u jota-racestream-sync.service -n 10
```

Atualização manual: `systemctl --user start jota-racestream-sync.service`.
Para desativar a periodicidade: `systemctl --user disable --now jota-racestream-sync.timer`.
Falhas ficam no journal e são repetidas; a API pode levar alguns segundos para
ficar disponível na primeira inicialização.

Para continuar após uma pausa, consulte o [registro de retomada](docs/RETOMADA.md),
com o estado atual, pendências e links para o plano de melhorias.
