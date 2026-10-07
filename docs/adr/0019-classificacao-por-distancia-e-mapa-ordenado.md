# ADR 0019: classificação por distância e marcadores ordenados

## Estado

Aceito em 07/10/2026.

## Contexto

Tempos de volta medem o ritmo de uma volta individual; não definem a posição de
corrida. O pelotão precisa refletir o avanço acumulado. No mapa, marcadores
separados por poucos metros ocupavam os mesmos pixels, escondendo carros.

## Decisão

- Ordenar o pelotão pela distância acumulada em metros, decrescente. Em empate,
  usar `race_position`, que contém os critérios de chegada e penalidade. A posição
  visual exibida é a ordem resultante no pelotão; tempo de última volta não muda
  a classificação.
- Ordenar os marcadores do mapa pela posição de corrida e espaçá-los ao longo da
  linha da pista quando a distância real entre eles não comporta o tamanho do
  marcador. Calcular o espaçamento antes de reduzir a distância ao circuito
  circular, mantendo a ordem inclusive quando há carros uma ou mais voltas atrás.
- Quando uma ultrapassagem altera distância e posição oficial, a próxima projeção
  troca a ordem dos carros no mapa e no pelotão.

## Consequências

O mapa aplica apenas um afastamento visual longitudinal para tornar os carros
visíveis. A telemetria física, os tempos e a ordem real do backend não são
modificados.

## Validação

Testes do frontend verificam que distância prevalece sobre o tempo da última
volta, o espaçamento mínimo do mapa e a mudança de ordem após ultrapassagem. Build
TypeScript/Vite, testes frontend, Ruff, mypy e testes físicos selecionados passam.
