# ADR 0017 — Penalidade de tempo configurável

- Estado: aceito
- Data: 07/10/2026

## Contexto

O projeto permite programar clima e incidentes, mas ainda não possui uma sanção
capaz de alterar o resultado sem retirar o carro da prova. A penalidade precisa
ser determinística, visível e auditável nos eventos.

## Decisão

Adicionar o cenário `time_penalty`, configurado com carro, volta e duração entre
1 e 60 segundos. A interface oferece inicialmente 5, 10 e 20 segundos. O evento
é aplicado quando o carro alcança a metade da volta escolhida e publicado em
`incident` com volta, duração, carro sancionado e estado `applied`.

A penalidade é acumulada em `time_penalty_seconds`, publicado em `telemetry` e
propagado para `state`. Durante a corrida, a ordem continua física. Depois que os
carros terminam a mesma distância, a classificação usa
`finished_at + time_penalty_seconds`, permitindo que uma penalidade altere o
pódio e o resultado persistido.

Os campos Avro são aditivos e possuem valores padrão.

## Consequências

- o painel mostra a sanção no pelotão e no cartão do carro;
- o resultado final já contém a posição após a penalidade;
- a duração fica preservada nos eventos e na projeção final, mas não possui uma
  coluna própria em `race_results`;
- esta versão não implementa drive-through, stop-and-go, cumprimento durante o
  pit stop ou recurso contra a decisão.
