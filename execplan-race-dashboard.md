# ExecPlan: Corrida Configurável e Painel de Interlagos

## 1. Objetivo

Entregar uma interface web ao vivo para acompanhar 20 carros em uma representação visual do Autódromo José Carlos Pace (Interlagos), com leaderboard, tempos de volta e configuração individual dos carros.

Uma corrida deve durar 120 segundos de relógio e representar 60 voltas de Interlagos (4.309 m por volta). O tempo comprimido do simulador deve ser separado dos valores físicos de telemetria. A conclusão será demonstrada por testes do domínio e por uma execução local com Docker Compose.

## 2. Escopo

Inclui:

- configuração independente por carro: peso seco, peso do piloto, velocidade máxima e composto de pneu;
- cálculo explícito de delta de tempo por volta em milissegundos;
- duração de corrida de 120 segundos e alvo de 60 voltas;
- telemetria v2 com tempo da volta atual, última volta, melhor volta e tempo decorrido;
- PostgreSQL para configuração dos carros, metadados da corrida e resultados finais;
- FastAPI/WebSocket para disponibilizar estado ao navegador;
- aplicação React + TypeScript com pista SVG de Interlagos, carros, classificação e painel de configuração;
- testes unitários, de contrato, integração e smoke test end-to-end conforme viabilidade local.

Não inclui Flink, Spark, ClickHouse, Iceberg, CDC, Kubernetes ou telemetria histórica completa no PostgreSQL.

## 3. Estado Atual

- MVP Kafka + Schema Registry + Avro + consumer entregue e executando.
- `RaceSimulator` mantém 20 carros iguais e avança a distância a partir de segundos e velocidade instantânea; não tem duração de corrida nem configuração de desempenho.
- `TelemetryEvent` v1 não contém tempos de volta.
- Compose tem Kafka, Schema Registry, simulador e consumer, mas não PostgreSQL, API ou frontend.
- O domínio e a aplicação já estão separados dos adapters de Kafka; `EventPublisher` é uma porta injetável.

## 4. Arquitetura Alvo

```text
React + TypeScript
  | REST: configurações / corrida atual
  | WebSocket: snapshots de telemetria
FastAPI gateway
  |                         |
  | Kafka consumer          | PostgreSQL repository
  v                         v
race.telemetry.raw       cars / races / race_results
  ^
  | Kafka producer
Race application service
  |                 |
  v                 v
Race domain      Car/Race repository port
```

O domínio calcula desempenho e progresso sem conhecer Kafka, PostgreSQL, FastAPI ou React. PostgreSQL guarda metadados operacionais e configurações; Kafka continua sendo o transporte de telemetria de alta frequência.

## 5. Contratos

- Circuito: `Autódromo José Carlos Pace`, Interlagos, comprimento de referência `4309 m`.
- Corrida: duração de relógio `120 s`; distância-alvo `60 voltas`; intervalo de publicação inicial `100 ms`.
- Configuração de carro: `car_id`, `driver_id`, `car_weight_kg`, `driver_weight_kg`, `top_speed_kmh`, `tire_compound`.
- Pilotagem: aproximações de curva por zonas de progresso, fase de frenagem, velocidade-alvo na curva, downshift derivado da velocidade e aceleração limitada por `top_speed_kmh`.
- Separação do pelotão: distância mínima de referência de `60 m`, aplicada no progresso normalizado e mantida sem alterar coordenadas no contrato.
- Compostos iniciais: macio `-250 ms/volta`, médio `0 ms/volta`, duro `+300 ms/volta`; valores documentados e ajustáveis.
- Tempo-base de volta: `90000 ms`; massa, peso do piloto e velocidade máxima contribuem com deltas determinísticos e testáveis.
- Telemetria v2 adiciona `driving_phase`, `current_lap_time_ms`, `last_lap_time_ms`, `best_lap_time_ms`, `elapsed_race_seconds`, `target_laps` e `race_status`. Campos novos usam defaults para eventos v1 já registrados.
- PostgreSQL armazena carros configurados, corridas e resultados por carro. Não armazenar cada amostra de telemetria nele.
- API: REST para listar/alterar carros e obter a corrida; WebSocket por `race_id` para snapshots.
- Frontend usa `track_progress` normalizado para posicionar marcadores ao longo do path da pista SVG; pixels não entram no evento.

## 6. Etapas de Implementação

1. Modelar configurações, pneus, fórmula de tempo de volta e relógio/progresso de corrida no domínio.
2. Adicionar testes: seed determinística, deltas em milissegundos, 60 voltas de referência em 120 s e diferenças entre carros.
3. Evoluir contrato para Avro v2 com defaults e teste de compatibilidade.
4. Definir portas de repositório; adicionar migration SQL, adapter PostgreSQL e persistência idempotente de configurações/resultados.
5. Adicionar API FastAPI, REST de configuração e hub WebSocket para consumir telemetria Kafka.
6. Implementar dashboard React/TypeScript com pista SVG de Interlagos, posição interpolada, classificação, tempos e formulário de configuração.
7. Integrar PostgreSQL/API/frontend no Compose, health checks e instruções de execução.
8. Rodar testes, lint, type-check, integração PostgreSQL/Kafka e validar dashboard em desktop e mobile; atualizar este plano e ADRs.

## 7. Estratégia de Testes

- Unitários do domínio: peso total, influência de top speed, massas e pneus, limite de progresso, conclusão em 120 s e 60 voltas na configuração de referência.
- Contrato: Avro v2 registra sob o subject existente e é backward-compatible com v1; validar campos e defaults.
- Aplicação: persistência por portas substituíveis e conclusão salva uma única vez.
- Integração: PostgreSQL real no Compose, API REST, fluxo Kafka -> WebSocket.
- Frontend: conversão `track_progress` -> coordenada SVG, leaderboard e estados de conexão; screenshots desktop/mobile quando Playwright estiver disponível.
- Gate de execução: `docker compose up --build`, com serviços healthy e carros visíveis movendo-se na pista.

## 8. Comandos de Validação

```bash
.venv/bin/pytest -q
.venv/bin/ruff check src tests
.venv/bin/mypy src tests
docker compose config --quiet
docker compose up --build
```

Adicionar comandos de frontend e integração após definir a estrutura Vite e os serviços Compose.

## 9. Riscos

- Compressão temporal não pode inflar a velocidade física exibida; usar relógios separados para progresso de corrida e telemetria física.
- Uma variação de tempo de volta pequena acumula ao longo de 60 voltas; manter fórmula e limites em testes.
- O progresso visual pode pular entre mensagens; interpolar no navegador sem alterar o evento de domínio.
- Inicialização do PostgreSQL e Schema Registry é assíncrona; health checks e migrations idempotentes são necessários.
- Mudança Avro precisa preservar leitura de eventos v1 existentes no tópico.
- Coordenadas de pista são uma representação de visualização e devem seguir o traçado publicado de Interlagos; nunca são parte do contrato de telemetria.

## 10. Decisões

- PostgreSQL é necessário para persistir configurações editáveis e resultados de corrida, não para cada mensagem de telemetria.
- Duração de relógio e tempo de volta são dimensões distintas: a corrida é acelerada para 120 s enquanto tempos de volta mantêm unidade real em milissegundos.
- A configuração inicial é mantida no PostgreSQL e aplicada no início da próxima corrida; alterações durante corrida não mudam retrospectivamente seus parâmetros.
- O frontend é o primeiro consumidor visual do WebSocket e não recebe histórico bruto completo.

## 11. Progresso

- [x] Documentar escopo, contratos propostos, arquitetura e riscos.
- [x] Implementar domínio de corrida e carros configuráveis.
- [x] Evoluir Avro para v2 com defaults para leitura de v1.
- [x] Adicionar persistência PostgreSQL para carros, corridas e resultados.
- [x] Adicionar FastAPI REST/WebSocket.
- [x] Adicionar dashboard Interlagos, leaderboard e editor de setup.
- [x] Controlar frenagem, downshift, saída de curva, velocidade máxima e espaçamento visual dos carros.
- [x] Ignorar caches locais de navegador/IDE e artefatos de build frontend.
- [x] Validar stack completa, API, persistência e layout desktop/mobile.
- [x] Atualizar README e ADRs da fase.

### Evidências de Validação

- Configuração-base: 60 voltas, 4.309 m por volta, 90.000 ms por volta e 120 s no relógio da corrida.
- Carros padrão: 20 perfis; 9 pesos distintos, 20 velocidades finais distintas e 3 compostos de pneu.
- Pneu macio: `-250 ms`; médio: `0 ms`; duro: `+300 ms`; desgaste acrescenta `15 ms` por volta.
- Compose: PostgreSQL, Kafka, Schema Registry, API, runner, consumer e Vite iniciaram; health checks de PostgreSQL, Kafka, Schema Registry e API passaram.
- PostgreSQL: migration criou `cars`, `races` e `race_results`; uma corrida finalizada persistiu 20 resultados.
- Schema Registry: subject `race.telemetry.raw-value` serviu schemas v1 e v2; produtor registrou v2.
- API: testes REST de edição/validação passaram; alterações de setup foram salvas e depois restauradas.
- Browser: WebSocket atualizou classificação/telemetria; desktop capturado; viewport 375 px sem overflow horizontal.
- `.venv/bin/pytest -q`: 16 passed, 1 integração Kafka opt-in skipped.
- Após testes de curva e espaçamento: `.venv/bin/pytest -q`: 19 passed, 1 integração Kafka opt-in skipped.
- `.venv/bin/ruff check src tests`: passed.
- `.venv/bin/mypy src tests`: passed.
- `git check-ignore -v` confirmou os exemplos Brave/PyCharm e os diretórios `frontend/node_modules` e `frontend/dist`.
- `npm run build` em `frontend/`: passed.
- `docker compose config --quiet`: passed; stack permaneceu ativa após a validação.

## 12. Retomada

Esta fase está implementada e executando localmente. Não há milestones pendentes neste ExecPlan.

Ao retomar:

1. Leia `AGENTS.md`, `PLANS.md`, este ExecPlan e `docs/adr/`.
2. Confira `git status --short --branch` e execute os testes, lint, type-check e build do frontend.
3. Use `http://localhost:5173` para o dashboard e `http://localhost:8000/docs` para a API.
4. Para inspecionar os dados, use `docker compose exec postgres psql -U racestream -d racestream`.
5. Antes de iniciar Flink, Spark, ClickHouse, Iceberg, CDC ou Kubernetes, crie um ExecPlan específico e aguarde escopo explícito.