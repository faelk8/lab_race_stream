# Plano de execução: grid, pelotão e eventos enriquecidos

Data: 06/10/2026. Estado: concluído.

## 1. Objetivo

Representar a largada em duas colunas de dez carros, tornar o pelotão mais
informativo e acrescentar contexto operacional aos eventos de volta e pit stop.

## 2. Estado atual

- os 20 carros são criados em uma única fila longitudinal;
- o pelotão mostra sempre um troféu apenas para o líder;
- abandonos e posições de pódio não possuem estados visuais próprios;
- a força G existe na telemetria e no contrato, mas não aparece no cartão do carro;
- `lap_completed` não informa a volta corrente nem a posição da corrida;
- `pitstop` não informa a volta nem o tempo transcorrido da passagem pelos boxes.

## 3. Componentes afetados

- domínio físico e projeção em `src/racestream/`;
- contratos Avro em `schemas/`;
- painel React em `frontend/src/`;
- testes unitários direcionados;
- dicionário de dados, ADR e documentação de retomada.

## 4. Etapas

1. Criar o grid inicial com duas colunas e dez linhas.
2. Medir a passagem pelo pit lane da entrada à saída e publicar volta e duração.
3. Propagar posição e volta corrente para `lap_completed`.
4. Exibir força G, abandono e pódio conforme o estado da corrida.
5. Atualizar contratos, documentação e testes.
6. Executar lint, typecheck, build e testes direcionados.

## 5. Validação

- verificar as dez distâncias longitudinais, cada uma ocupada por dois carros;
- serializar eventos reais de volta e pit stop com os schemas Avro;
- comprovar volta, posição e tempos de pit stop com testes unitários;
- validar o frontend com testes, TypeScript e build de produção;
- executar Ruff e a seleção de testes Python afetada.

## 6. Riscos e decisões

- Campos novos serão acrescentados ao fim dos schemas com valores padrão para
  manter evolução retrocompatível.
- `pit_stop_time_ms` será cumulativo desde a entrada no pit lane. Na fase
  `exit`, representa a duração total da passagem pelos boxes.
- O pódio em verde será usado somente durante a corrida. Após a chegada, ouro,
  prata e bronze identificarão as três primeiras posições.

## 7. Progresso

- [x] Inspecionar domínio, projeção, contratos, frontend e testes.
- [x] Implementar domínio e contratos.
- [x] Implementar apresentação no frontend.
- [x] Atualizar documentação.
- [x] Validar e registrar o resultado.

## 8. Resultado da validação

- Ruff: aprovado em `src` e `tests`.
- mypy estrito: aprovado em 41 arquivos-fonte.
- pytest direcionado: quatro testes aprovados para grid, voltas, Avro e pit stop.
- frontend: dois arquivos de teste, typecheck e build de produção aprovados.
- schemas alterados: JSON válido e registro aceito pelo Schema Registry.
- Compose: configuração válida; API saudável e simulador, consumer e dashboard
  reconstruídos e em execução sem erro nos logs de inicialização.
- Não foi iniciada uma corrida completa. A validação física usou somente fixtures
  curtas e o trecho controlado de pit lane.
