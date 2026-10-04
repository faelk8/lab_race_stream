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
- manter dados brutos e curados em MinIO/S3 usando Apache Iceberg;
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
- `docs/execplan-console.md`: plano de acesso ao Kafka pelo Redpanda Console.
- `docs/execplan-pelotao.md`: identificação dos carros e classificação do pelotão.
- `docs/execplan-controle-corrida.md`: início e parada pelo painel.
- `.agents/`: instruções e planos locais, não versionados.
- `docs/adr/`: decisões arquiteturais aceitas.

## Executar a corrida

Pré-requisitos: Docker com Compose. A instalação Python local é necessária apenas para executar testes e ferramentas de desenvolvimento.

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
docker compose up --build
```

O Compose inicia PostgreSQL, Kafka, Schema Registry, Redpanda Console, API, dashboard, simulador e consumer. O simulador aguarda o botão **Iniciar corrida** no painel. Cada corrida dura 120 segundos e representa 60 voltas de referência em Interlagos; durante a prova, o producer publica snapshots Avro a cada 100 ms.

### Links de acesso

Abra os links abaixo no navegador da máquina onde o Docker Compose está executando:

| Serviço | Link | Para que serve |
| --- | --- | --- |
| Painel da corrida | [Ver a corrida ao vivo](http://localhost:5173) | Acompanhar os carros na pista, classificação, telemetria e configurações. |
| Redpanda Console | [Acessar o Kafka](http://localhost:8080) | Consultar tópicos, mensagens, partições, grupos de consumidores e schemas. |
| Documentação da API | [Abrir a documentação OpenAPI](http://localhost:8000/docs) | Consultar e testar os endpoints da API. |
| Schema Registry | [Listar os schemas registrados](http://localhost:8081/subjects) | Consultar os contratos Avro registrados. |

No Redpanda Console, abra a seção **Topics**, selecione `race.telemetry.raw` e
acesse **Messages** para inspecionar a telemetria dos carros. Para acompanhar a
corrida visualmente, use o link do painel acima.

O Kafka também aceita conexões de clientes locais em `localhost:9092`.

Se os serviços já estiverem rodando, inicie somente o Console com:

```bash
docker compose up -d redpanda-console
```

A configuração do Console segue a
[documentação oficial do Redpanda](https://docs.redpanda.com/streaming/current/console/config/configure-console/).


PostgreSQL fica somente na rede interna do Compose para não conflitar com bancos já instalados no host. A API e o runner salvam configurações, corridas e resultados; o fluxo detalhado de telemetria permanece no Kafka.

Para acompanhar apenas o consumer em outro terminal:

```bash
docker compose logs -f consumer
```

O Schema Registry fica disponível em `http://localhost:8081`; o Kafka para clientes locais em `localhost:9092`. O tópico usa `car_id` como chave e seis partições.

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

O teste Kafka requer os serviços ativos. Encerre com `Ctrl+C` no terminal do Compose ou execute `docker compose down`; os dados de Kafka e PostgreSQL são mantidos nos volumes. `docker compose down -v` remove esses dados.

## Simulação e setup

Os vinte carros recebem configurações distintas de peso do carro, peso do piloto, velocidade máxima e composto. O editor do dashboard salva as mudanças no PostgreSQL; elas passam a valer na corrida seguinte.

Os compostos alteram o tempo estimado por volta: macio `−250 ms`, médio `0 ms` e duro `+300 ms`. A telemetria v2 inclui tempo atual, última volta, melhor volta e estado da corrida. O mapa usa `track_progress` normalizado e a fonte do SVG está registrada em `frontend/public/ATTRIBUTION.md`.

O simulador reduz velocidade e marcha ao se aproximar das zonas de curva, mantém a aceleração controlada durante o contorno e volta a acelerar na saída até atingir a velocidade máxima configurada. Os carros têm 3 m de comprimento e mantêm essa separação na mesma faixa; duplas podem disputar ultrapassagens nas retas; a fase atual (`reta`, `frenagem` ou `curva`) aparece no dashboard.

Caches locais do Brave/JetBrains e artefatos `frontend/node_modules`/`frontend/dist` são ignorados pelo Git.

Flink, Spark, ClickHouse, Iceberg, CDC e Kubernetes continuam fora desta fase.

### Regras atualizadas de corrida

A especificação está em [corrida.md](.agents/corrida.md) e as decisões de interpretação
em [ADR 0007](docs/adr/0007-corrida-rules.md). São 10 equipes (4 A, 4 B e 2 C),
com 2 carros cada, massa seca de 500/510/515 kg e pilotos com altura de 1,60–1,90 m.
O consumo nominal equivale a dois tanques de 110 kg em 60 voltas. Boxes duram
3–6 segundos físicos; o simulador converte para o relógio comprimido.

A telemetria v3 acrescenta pressão dos pneus, número de paradas e faixa de
ultrapassagem, com defaults compatíveis com eventos Avro v1/v2.

**Estratégia C atualizada:** larga com meio tanque e para a 20%. Na primeira
parada, abastece até 50% e troca pneus; na segunda, enche o tanque; na terceira,
abastece somente o necessário para terminar a prova e mais uma volta de reserva.
O cálculo desconta o combustível que ainda está no tanque. Em uma prova de
60 voltas, a reserva corresponde a aproximadamente 3,67 kg.

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

A coluna **DIF. LÍDER*** mostra o atraso estimado pela distância para o líder,
usando o tempo de referência de 90 segundos por volta. Ela inclui diferenças de
voltas completas e acompanha a ordem da classificação. A última e a melhor volta
ficam no painel individual: fazer uma volta mais rápida não significa estar à
frente na corrida. O navegador atualiza o pelotão com quadros completos do mesmo
instante para evitar posições duplicadas durante a chegada da telemetria.

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
