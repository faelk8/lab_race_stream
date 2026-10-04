# Plano de execução: identificação no mapa e classificação do pelotão

## Objetivo e escopo
Mostrar balões compactos com carro e posição no mapa. Exibir nome do piloto,
equipe e bandeira no pelotão, do primeiro ao último, com tempos coerentes com
essa ordem. Não executar séries de simulações.

## Estado atual e arquitetura
Mapa mostra marcadores sem identificação visível. Pelotão mostra IDs e última
volta, que não representa o atraso na corrida. Configurações passam do domínio
pelo PostgreSQL e API ao React; WebSocket entrega eventos individuais.

## Contratos e decisões
- Acrescentar `driver_name` e `driver_country_code` às configurações; pilotos
  fictícios, país ISO de duas letras, nomes editáveis. Preservar setups existentes.
- Avro e IDs técnicos permanecem iguais; identidade é metadado de configuração.
- Ordenar por posição recebida em quadros completos do mesmo instante, evitando
  misturar posições de passos distintos durante a chegada das mensagens.
- Exibir diferença estimada para o líder: distância atrás em voltas multiplicada
  por 90 segundos de referência. Identificar a coluna como estimativa. Tempos de
  última/melhor volta continuam no painel individual.
- Dispor balões no SVG sem coordenadas de tela no domínio ou na telemetria.

## Etapas
- [x] Persistir identidade e migrar configurações existentes.
- [x] Atualizar API e editor para nome e país.
- [x] Atualizar mapa e classificação, incluindo quadros coerentes.
- [x] Validar testes, tipagem, build, banco real e visual desktop/mobile.

## Validação
Ruff, mypy, pytest, build frontend, Compose; testes de identidade e preservação
da configuração. Verificar ordem e diferenças sem diminuir ao percorrer as
posições, quadros fora de ordem e disposição dos balões.

## Riscos e decisões operacionais
Eventos Kafka chegam por partições diferentes. Usar buffer limitado de quadros
no navegador e aumentar a fila WebSocket para comportar a rajada de 20 carros.
Balões próximos precisam evitar sobreposição e permanecer dentro do mapa.
Retornar à interface anterior removendo somente as novas representações.

## Evidências e conclusão
- 37 testes Python passaram, incluindo integração Kafka; 7 testes do frontend
  passaram, incluindo a diferença do 15º versus 4º e quadros fora de ordem.
- Ruff, mypy, build frontend e imagens Docker de API/dashboard passaram.
- Adapter PostgreSQL real confirmou vinte identidades completas, edição e
  preservação dos nomes/países. Alteração temporária de teste foi restaurada.
- Navegador com dados controlados: vinte balões, ordem 1–20, bandeiras e equipes;
  quarto atraso +0:12.857, décimo quinto +1:00.000. Desktop 1440 px e celular
  375 px sem erros JavaScript ou rolagem horizontal.
- API e dashboard atualizados iniciados; nenhuma nova corrida completa executada.
- Decisões documentadas na ADR 0008 e instruções atualizadas no README.
