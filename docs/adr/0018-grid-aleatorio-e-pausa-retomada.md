# ADR 0018: grid aleatório e pausa da corrida

## Estado

Aceito em 07/10/2026.

## Contexto

O grid fixo fazia todos os inícios repetirem a mesma ordem. O painel também
precisa permitir congelar temporariamente a corrida e continuar do mesmo estado.

## Decisão

- Embaralhar os carros na criação da simulação, usando semente derivada do ID da
  corrida. A ordem é reproduzível para o mesmo ID e muda entre corridas.
- Manter o grid em duas colunas e dez linhas; posição e faixa são atribuídas de
  acordo com a ordem sorteada.
- Persistir `paused` como estado de controle e incluir esse estado no índice que
  impede criar outra corrida controlada enquanto ela estiver ativa.
- O worker conserva em memória toda a física, congela relógio e distância, publica
  um quadro com os carros parados e retoma a integração após o comando explícito.
- `POST /api/races/{race_id}/pause` pausa e
  `POST /api/races/{race_id}/resume` retoma. A pausa não grava resultados finais;
  parar continua encerrando a prova.
- Remover os balões de identificação do mapa. Os marcadores permanecem clicáveis
  e os nomes/posições estão no pelotão.

## Consequências e limites

A retomada funciona enquanto o processo simulador mantém a corrida em memória.
Se o processo reiniciar, o estado físico por carro não é restaurado; a rotina
existente marca corridas interrompidas como paradas. O sorteio não exige alteração
de schema Kafka.

## Validação

Testes verificam grid 2×10 com ordem dependente da semente, congelamento e retomada
do relógio/distância e ausência de balões com seleção ainda disponível. Ruff,
mypy, testes Python selecionados, testes frontend e build Vite passaram. Não foi
iniciada uma corrida completa.
