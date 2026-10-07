# ADR 0016 — Safety car e voltas neutralizadas

- Estado: aceito
- Data: 07/10/2026

## Contexto

Colisões já retiravam os carros envolvidos, mas os demais continuavam em ritmo
normal e podiam ultrapassar. As voltas medidas durante esse período também
continuavam concorrendo a recordes, o que não representa uma neutralização.

## Decisão

Uma colisão programada aciona automaticamente `safety_car`. A neutralização dura
até o líder completar a volta seguinte à volta do incidente, limita todos os
carros a 120 km/h e bloqueia ultrapassagens em pista. Novas colisões podem
estender a distância final da neutralização.

O simulador publica `safety_car_started` e `safety_car_ended` no tópico
`incident`. `track_status` é publicado em `telemetry` e propagado para `state`.
Passagens carregam `neutralized`; se qualquer passagem da volta ocorrer durante
a neutralização, `lap_completed.neutralized` fica verdadeiro e a volta não é
válida para recordes e ritmo.

Os novos campos Avro são aditivos e possuem valores padrão para leitura de
eventos anteriores.

## Consequências

- o painel informa bandeira amarela e safety car a partir do quadro de estado;
- colisões configuráveis também configuram indiretamente o início da
  neutralização;
- a primeira versão usa duração e limite fixos no domínio; configuração direta
  desses valores fica para uma evolução posterior;
- o modelo não simula a posição física de um veículo de segurança.
