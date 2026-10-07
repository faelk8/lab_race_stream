# ADR 0015 — Grid em duas colunas e contexto nos eventos de corrida

- Estado: aceito
- Data: 06/10/2026

## Contexto

A largada precisa representar as vinte posições em duas colunas. Os consumidores
também precisam descobrir diretamente em qual volta e posição ocorreu uma volta
concluída e quanto tempo uma passagem pelos boxes consumiu.

## Decisão

O domínio inicializa dois carros por distância longitudinal, diferenciados por
`overtaking_lane`. O evento `timing` passa a carregar `race_position`; a projeção
usa esse valor para incluir `race_position` e `current_lap` em `lap_completed`.

Cada carro mantém o instante e a volta de entrada no pit lane. Todos os eventos
de `pitstop` carregam `lap`, `pit_stop_time_ms` e `tire_compound`. A duração é
cumulativa desde a entrada, e a fase `exit` contém o tempo total da passagem.

Os campos são acrescentados ao fim dos schemas Avro com valores padrão, mantendo
leitura retrocompatível de eventos anteriores.

## Consequências

- consumidores deixam de reconstruir volta, posição e duração do pit stop a
  partir de múltiplos tópicos;
- o grid inicial pode ser desenhado em duas colunas sem coordenadas de pixel no
  contrato central;
- a posição do evento de volta é o último ranking físico consolidado no instante
  da passagem;
- as fases intermediárias do pit stop contêm duração parcial, enquanto `exit`
  contém a duração total.
