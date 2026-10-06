# Dicionário de dados da corrida

Este documento descreve os eventos publicados no Kafka e os campos dos contratos
Avro atuais. Os arquivos Avro em `schemas/` são a fonte normativa dos tipos,
campos opcionais e valores padrão. A versão do contrato permanece em
`schema_version`, no namespace Avro e na evolução do schema; ela não faz parte do
nome curto do tópico.

## Convenções comuns

Todos os eventos carregam os campos abaixo, salvo indicação do próprio schema.

| Campo | Tipo Avro | Significado |
| --- | --- | --- |
| `kind` | string | Categoria do evento, como `telemetry`, `lap` ou `analytics`. |
| `event_id` | string | Identificador único do evento, usado para deduplicação. |
| `race_id` | string | Identificador da corrida a que o evento pertence. |
| `event_time` | string | Instante UTC representado pelo evento. |
| `produced_at` | string | Instante UTC em que o produtor publicou/preparou o evento. |
| `simulation_time_us` | long | Relógio monotônico da simulação, em microssegundos. |
| `source_sequence` | long | Sequência crescente na origem para ordenar eventos. |
| `track_version` | string | Versão da definição de pista usada na corrida. |
| `rules_version` | string | Versão das regras usadas na corrida. |
| `schema_version` | int | Versão semântica do contrato do evento. |
| `car_id` | string | Identificador do carro; pode estar vazio em evento coletivo. |

Nos tópicos por carro, a chave Kafka é `car_id`, preservando a ordem dentro da
partição. Eventos agregados ou de controle usam `race_id`. O tópico `dead_letter`
mantém a chave original. Todos os tópicos locais são criados com seis partições,
uma réplica e retenção de sete dias.

## Tópicos Kafka

| Tópico | Schema Avro | Chave | Conteúdo |
| --- | --- | --- | --- |
| `telemetry` | `telemetry-stream.avsc` | `car_id` | Snapshot do carro, posição, velocidade, combustível, pneus e força G. |
| `validated` | `validated-stream.avsc` | `car_id` | Snapshot aceito na validação; mantém o contrato da telemetria. |
| `timing` | `timing-stream.avsc` | `car_id` | Passagem por checkpoint, setor e linha de chegada com tempos medidos. |
| `lap_completed` | `lap-stream.avsc` | `car_id` | Volta concluída, setores, validade e indicação de passagem pelos boxes. |
| `pitstop` | `pitstop-stream.avsc` | `car_id` | Fases de entrada, serviço e saída; número da parada e combustível adicionado. |
| `incident` | `incident-stream.avsc` | `car_id` | Incidente e motivo associado ao carro. |
| `control` | `control-stream.avsc` | `race_id` | Estado da sessão, participantes, pista, distância e escala da corrida. |
| `state` | `state-stream.avsc` | `race_id` | Quadro de estado e classificação dos carros. |
| `analytics` | `analytics-stream.avsc` | `race_id` | Revisão dos agregados analíticos por carro. |
| `dead_letter` | `dead_letter-stream.avsc` | chave original | Evento recusado, motivo e localização no tópico de origem. |

## Campos por contrato

As tabelas listam os campos específicos além dos campos comuns acima. O tipo
exato (incluindo `null`, arrays e registros aninhados) está no schema indicado.

### `telemetry` e `validated`

Os dois tópicos têm os mesmos campos de domínio. `validated` contém eventos que
passaram pela validação.

| Campo | Significado |
| --- | --- |
| `driver_id`, `driver_name`, `driver_country_code`, `team_id` | Identidade do piloto e da equipe; o país usa código ISO. |
| `race_status`, `car_status`, `pit_status`, `driving_phase` | Situação da corrida, carro, parada e fase de condução. |
| `tire_compound`, `tire_age_laps`, `tire_pressure_psi` | Composto montado, idade em voltas e pressão em PSI. |
| `snapshot_id`, `sample_sequence` | Identificadores do quadro e da amostra de telemetria. |
| `current_lap_time_ms`, `last_lap_time_ms`, `best_lap_time_ms`, `worst_lap_time_ms` | Tempos da volta atual, última, melhor e pior, em milissegundos; alguns podem ser nulos. |
| `race_position`, `lap`, `laps_completed`, `target_laps`, `sector` | Posição, volta atual/concluída, total previsto e setor. |
| `gear`, `rpm`, `overtaking_lane` | Marcha, rotação do motor e faixa de ultrapassagem. |
| `speed_kmh`, `distance_m`, `track_progress`, `lap_distance_m` | Velocidade, distância acumulada, progresso normalizado de 0 a 1 e distância na volta. |
| `fuel_kg`, `car_weight_kg`, `throttle`, `brake` | Combustível, massa do carro e comandos normalizados de acelerador/freio. |
| `elapsed_race_seconds`, `pit_stops` | Tempo decorrido da corrida e número de paradas. |
| `g_longitudinal`, `g_lateral`, `g_horizontal`, `g_peak` | Aceleração longitudinal, lateral, horizontal e pico, expressos em força G; componentes instantâneos podem ser nulos. |

### `timing`

| Campo | Significado |
| --- | --- |
| `driver_id`, `team_id` | Piloto e equipe no momento da passagem. |
| `lap`, `checkpoint_id`, `sector` | Volta, identificador do ponto cronometrado e setor. |
| `speed_kmh` | Velocidade no ponto de cronometragem. |
| `lap_elapsed_ms`, `segment_time_ms`, `sector_time_ms` | Tempo acumulado da volta, do trecho e do setor, em milissegundos. |
| `pit_lap`, `valid` | Indica volta com passagem pelos boxes e validade da medição. |

### `lap_completed`

| Campo | Significado |
| --- | --- |
| `driver_id`, `team_id` | Piloto e equipe. |
| `lap`, `lap_time_ms` | Número e duração total da volta, em milissegundos. |
| `sectors_ms` | Lista dos tempos dos três setores, em milissegundos. |
| `pit_lap`, `valid` | Indica volta com passagem pelos boxes e validade para recordes. |

### `pitstop`

| Campo | Significado |
| --- | --- |
| `phase` | Fase do evento de parada (por exemplo, entrada, serviço ou saída). |
| `stop_number` | Número sequencial da parada do carro. |
| `fuel_added_kg` | Massa de combustível adicionada durante o serviço. |

### `incident`

| Campo | Significado |
| --- | --- |
| `reason` | Motivo ou descrição categórica do incidente. |

### `control`

| Campo | Significado |
| --- | --- |
| `status` | Estado de controle da sessão, como início, pausa ou encerramento. |
| `target_laps` | Distância da prova em voltas. |
| `participants` | Participantes congelados para a sessão, com seus dados de inscrição. |
| `track` | Definição da pista usada pela sessão. |
| `time_scale` | Escala entre o relógio simulado e o relógio de execução. |

### `state`

| Campo | Significado |
| --- | --- |
| `state_sequence` | Número sequencial do quadro de estado. |
| `snapshot_id` | Quadro de telemetria que originou a projeção. |
| `complete` | Informa se o quadro contém todos os estados esperados. |
| `cars` | Lista de estados individuais usada pelo mapa e pela classificação. |

### `analytics`

| Campo | Significado |
| --- | --- |
| `revision` | Revisão crescente dos agregados da corrida. |
| `cars` | Lista de métricas por carro, incluindo voltas, tempos e parciais conforme o schema. |
| `snapshot_id` | Quadro que serve de referência às métricas publicadas. |

### `dead_letter`

| Campo | Significado |
| --- | --- |
| `source_topic` | Tópico de origem do evento recusado. |
| `source_partition`, `source_offset` | Partição e offset Kafka da mensagem de origem. |
| `reason` | Motivo da rejeição ou falha de processamento. |

## Persistência analítica

O arquivador Spark guarda envelopes Kafka em Parquet no MinIO, em
`s3a://racestream/telemetry_raw`, particionados por tópico e data UTC. O job
analítico produz `lap_performance/` (agregados de voltas válidas por corrida e
carro) e `consumer_parity/` (comparação dos agregados Spark com o consumer). As
configurações e projeções operacionais ficam no PostgreSQL; as tabelas e colunas
relacionais são definidas pelas migrações SQL em `migrations/`.

## Alterações de nomes

Os tópicos `race.*.vN` foram substituídos para novas publicações pelos nomes
curtos desta página. O Kafka não oferece renomeação: tópicos antigos podem
continuar visíveis com seus dados históricos. Nenhuma rotina de limpeza os apaga.
