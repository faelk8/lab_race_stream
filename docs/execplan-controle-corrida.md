# Plano de execução: iniciar e parar a corrida pelo painel

## Objetivo e escopo
Adicionar botões reais de início e parada. O simulador deve aguardar uma ação
no painel, executar uma corrida e voltar a aguardar, sem reiniciar automaticamente.
Parar encerra a corrida atual e salva a classificação parcial; iniciar cria outra.

## Estado atual e arquitetura
O produtor inicia corridas continuamente. API e simulador são processos separados,
com PostgreSQL para estado operacional e Kafka para telemetria.

## Contratos e decisões
- API: POST `/api/races/start` e POST `/api/races/{race_id}/stop`.
- PostgreSQL coordena estados `queued`, `running`, `stopping`, `stopped`,
  `finished`, `failed`. Uma corrida controlada ativa por vez; início idempotente.
- O worker reserva uma corrida pendente atomicamente, usa configurações atuais,
  consulta parada a cada passo e salva os resultados na conclusão/interrupção.
- Telemetria mantém Avro v3; o campo string `race_status` aceita `stopped`.
- Reinício do único runner encerra corridas interrompidas e preserva as pendentes.
- Painel apresenta os estados e desabilita ações incompatíveis/duplicadas.

## Etapas
- [x] Implementar migração, porta de controle e adapter PostgreSQL.
- [x] Implementar worker controlado e parada do domínio.
- [x] Conectar endpoints e botões.
- [x] Testar transições, repetição, reserva, parada e conclusão.
- [x] Validar banco real e botões em navegador; executar uma corrida curta.
- [x] Atualizar README/ADR, disponibilizar serviços e deixar a corrida parada.

## Validação e riscos
Ruff, mypy, pytest, testes frontend, build e Compose. Conferir que início repetido
não cria corridas extras e que parada não altera resultados históricos. A fila
persistente evita perder comandos entre API e runner; falhas devem aparecer como
`failed`. Não iniciar séries de corridas. Operação prevista: um runner no Compose.

## Resultado da validação

Em 03/10/2026, Ruff, mypy, build TypeScript/Vite, 41 testes Python (incluindo
Kafka/Schema Registry) e oito testes frontend passaram. O navegador real confirmou
início, repetição idempotente, vinte balões, parada, ausência de reinício automático
e ausência de rolagem horizontal em 375 px. Uma única corrida curta foi iniciada
e parada; os vinte resultados parciais foram conferidos no PostgreSQL. Quatro
pedidos concorrentes de início no banco retornaram o mesmo ID; a solicitação de
teste foi cancelada antes de executar e removida depois da verificação.

API, painel e simulador foram reconstruídos e iniciados. A última corrida ficou
parada, com o simulador aguardando o botão de início.
