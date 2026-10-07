# ADR 0008: Identificação no mapa e classificação do pelotão

## Status
Aceita.

## Contexto
Rafael solicitou balões pequenos com carro e posição no mapa, nome do piloto,
equipe e bandeira no pelotão e tempos coerentes com a ordem da classificação.
A coluna anterior mostrava a última volta: um carro atrás pode fazer uma volta
mais rápida, sem ganhar imediatamente a posição. Eventos de carros distintos
também chegam por partições diferentes e podem misturar instantes na interface.

## Decisões
- Acrescentar `driver_name` e `driver_country_code` à configuração de carro,
  persistidos no PostgreSQL e expostos na API. Os vinte pilotos iniciais são
  fictícios; os países usam códigos de duas letras, com bandeiras e nomes dos
  países em português do Brasil. Nome e país podem ser editados no painel.
- Migrar volumes existentes e preservar nomes/países já preenchidos. Clientes
  antigos da API preservam esses metadados quando não os enviam na edição.
- Exibir equipe com nome legível, por exemplo `Equipe A1`, mantendo o ID técnico.
- Exibir no mapa os marcadores dos carros sem rótulos ou balões flutuantes para
  reduzir a poluição visual. Os marcadores continuam selecionáveis e a identidade
  permanece disponível no pelotão.
- Montar quadros completos dos carros com o mesmo `event_time` e tempo decorrido.
  Rejeitar quadros antigos, de outra corrida ou com posições duplicadas. Limitar
  o buffer a 32 quadros pendentes e ampliar a fila WebSocket para 256 eventos,
  comportando rajadas dos vinte carros. Eventos Avro e formato WebSocket não mudam.
- Ordenar o pelotão por `race_position`, do primeiro ao último. Exibir na coluna
  `DIF. LÍDER*` a diferença estimada para o líder, com indicação explícita de
  estimativa. Calcular distância atrás em voltas × 90 segundos de referência,
  incluindo voltas completas de diferença. Esse valor não é cronometragem real
  de passagem: ele permite comparar a classificação de forma consistente com
  o modelo comprimido de progresso usado pelo simulador.
- Manter última e melhor volta no painel individual. Não alterar tempos reais
  recebidos para fazer a classificação aparentar uma ordem diferente.

## Validação
Testes do frontend cobrem ordenação, diferença do 15º versus 4º mesmo com última
volta mais rápida, carros em voltas distintas, mensagens fora de ordem, posições
duplicadas, buffer limitado, bandeiras e ausência de balões mantendo a seleção.
Testes da API verificam edição e preservação de nome/país, validação de código e
capacidade da fila WebSocket. Conferência visual com dados controlados verificou
vinte balões e classificação de 1 a 20 em desktop e celular, sem erros JavaScript
ou rolagem horizontal. Nenhuma nova corrida completa foi necessária.
