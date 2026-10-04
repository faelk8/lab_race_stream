# Plano de execução: cronometragem e telemetria da corrida

Data: 04/10/2026. Estado: implementação entregue e validada nesta instalação.
Especificação original e decisões finais: [regras propostas da corrida v2](planejamento/regras-corrida-v2.md).

## 1. Objetivo

Refinar o laboratório existente para publicar velocidade e posição de cada carro
uma vez por segundo, registrar passagens cronometradas pelo Kafka, consolidar
voltas/setores/parciais e permitir acompanhar carro, piloto e equipe no painel.
Adicionar força G apenas depois que velocidade, distância e relógio físico forem
consistentes. Entregar incrementalmente, com poucas simulações de validação.

## 2. Escopo

Inclui domínio, contratos Avro, produtores, consumer de projeções, PostgreSQL já
existente, API/WebSocket, frontend e observabilidade mínima. Preserva controles
manuais, IDs, grid, estratégias e terceira parada de C.

Não inclui instalar novos motores de streaming nesta entrega, CDC, Kubernetes,
serviços pagos ou dados externos ao vivo. Flink/Spark continuam alternativas
futuras, apoiadas nos contratos e fixtures produzidos aqui.

## 3. Estado atual verificado no código

| Componente | O que existe | Lacuna relevante |
| --- | --- | --- |
| `domain/simulator.py` | 20 estados, seed, tráfego, pneus, abastecimento e ranking. | `_proposed_progress` usa tempo de volta de referência separado da velocidade; `_advance_progress` atribui tempos estimados e setores de comprimentos iguais. A prova termina por duração de parede. |
| `application/race_worker.py` e `interfaces/producer.py` | Início/parada manual e snapshots pelo Kafka. | Cada passo/publicação usa o intervalo atual de 100 ms; falta agenda de 1 Hz independente da física e eventos por passagem. |
| `application/telemetry.py`, `schemas/telemetry-v3.avsc` | Telemetria versionada, pneus, paradas, velocidade, posição, última/melhor volta. | Não há histórico cronometrado por checkpoint, pior volta, qualidade da medição ou G. |
| `infrastructure/kafka.py` | Avro, Schema Registry, chave por carro. | O consumer confirma offset em `poll()` após desserializar, antes de executar a projeção de negócio. |
| `interfaces/consumer.py` | Consumidor de demonstração com logs. | Não calcula projeções de corrida ou análises. |
| `interfaces/kafka_hub.py` | API consome telemetria bruta e encaminha ao WebSocket. | Não mantém snapshot inicial/histórico durável; a fila pode descartar eventos individuais. |
| `frontend/src/racePresentation.ts` | Ranking, bandeiras, balões e montagem de quadros. | Diferença ao líder estimada com volta de 90 s; quadro exige todos os carros no mesmo instante e pode travar se um faltar. |
| `frontend/src/App.tsx` | Mapa, pelotão, seleção de carro, última/melhor volta e configuração. | Falta seleção dedicada de piloto/equipe, pior volta, setores cronometrados, histórico e comparação. |
| PostgreSQL | Configurações, controle de corrida e resultado por carro. | Faltam histórico de voltas/passagens, versões de projeções e recuperação do estado ao vivo. |
| Testes | Domínio, API, regras, worker, Avro, Kafka e apresentação. | Adicionar invariantes de relógio/física, cronometração, replay, falhas e reconexão. |

Esta avaliação é estática. Nenhuma nova corrida foi executada para elaborar o plano.

## 4. Arquitetura afetada

Simulador publica fatos e telemetria diretamente no Kafka. Um consumer Python
valida os contratos e mantém projeções de estado e análises. Publica tópicos
derivados; a API passa a consumir essas projeções e entrega snapshot + atualizações.
O frontend deixa de calcular resultados de cronometragem.

PostgreSQL continua armazenando estado operacional e passa a guardar as pequenas
projeções necessárias ao replay e ao histórico da sessão. Não armazenar todo o
fluxo bruto de alta frequência ali. Uma outbox transacional do consumer resolve a
publicação confiável de derivados sem exigir Debezium.

## 5. Contratos e decisões propostas

- Um snapshot por carro por segundo real; subpassos físicos e eventos de passagem independentes.
- Três setores, curvas 1–15 e proposta de quinze checkpoints mais chegada, com geometria versionada a mapear.
- Tempo físico monotônico, publicação UTC e escala de reprodução explícitos.
- Família de telemetria v4 separada para a mudança semântica de tempos estimados para medidos; contratos de passagem/controle/estado/análise próprios.
- Corrida, participantes e regras congelados em evento de controle, suficientes para reconstruir a sessão sem consultar cadastros atuais.
- Autoridade da posição no controlador; consumer valida e publica quadros coerentes. Dados individuais atrasados não congelam os demais.
- Confirmação de offsets após transação de processamento, deduplicação, outbox, revisão de análises tardias e snapshot durável.
- API proposta: `GET /api/tracks/{track_id}`, `GET /api/races/{race_id}/state`, `GET /api/races/{race_id}/cars/{car_id}/laps`, `GET /api/races/{race_id}/cars/{car_id}/splits`, `GET /api/races/{race_id}/teams/{team_id}/analytics`; evoluir o WebSocket existente com versão e sequência explícitas.
- Novas entidades de persistência propostas: definição/versionamento de pista, participantes da sessão, passagens, voltas/setores, projeções, eventos processados e outbox. Índices e unicidade seguem corrida/carro/volta/linha, com revisão quando aplicável.
- ADR proposta acompanha este plano; ainda não substitui as ADRs aceitas de contratos, regras e painel.

## 6. Etapas de implementação

### Etapa 1 — Base física, relógio e definição da pista

Implementado em `domain/physical.py` e `domain/track.py`, preservando o simulador legado; acrescentar configuração de
pista e regras versionadas, sem coordenadas de tela. Separar relógio físico,
passo de integração e escala de reprodução. Integrar distância a partir da
velocidade aceita, corrigir largada e término por cruzamento de linha.

Definir os limites reais/referenciados dos setores e os checkpoints simulados.
Estabelecer como o percurso dos boxes cruza as linhas de cronometragem; trechos
não percorridos não podem produzir recordes de parcial.

Aceite: a mesma seed e o mesmo tempo físico produzem resultados equivalentes com
escalas diferentes; distância coincide com velocidade integrada; zerar combustível
impede avanço. Não exigir que resultados numéricos da física antiga permaneçam
iguais, mas preservar as invariantes de estratégia e documentar diferenças.

### Etapa 2 — Contratos e publicação de eventos

Criar schemas e fixtures da família v4 e dos novos fatos. Atualizar portas,
serialização e produtor, preservando v1–v3. Implementar agenda de 1 Hz e detecção
interpolada de todas as linhas cruzadas, com IDs estáveis.

Fila de publicação limitada, confirmação de entrega e política explícita de erro:
se Kafka ficar indisponível além do limite, encerrar a execução como falha em vez
de descartar passagens e continuar uma cronometragem incompleta. Para sobreviver a
reinício do produtor sem perder fatos já calculados, usar um diário/outbox de
publicação durável ou definir a sessão como interrompida e marcar sua incompletude;
não prometer entrega exatamente uma vez sem esse mecanismo.

Aceite: vinte snapshots por segundo de grade para vinte carros ativos, passagem
entre snapshots preservada, várias passagens no mesmo passo, replay legado e
rejeição de contrato inválido. Estado terminal publicado fora da grade.

### Etapa 3 — Consumer de cronometragem e projeções

Extrair cálculos puros para aplicação/domínio; evoluir o adapter de Kafka para
separar leitura e confirmação. Criar transação de projeção + deduplicação + outbox,
publicador dos derivados e recuperação por offsets. Implementar último estado,
voltas, setores, parciais e agregados por participante/equipe.

Aceite: duplicar mensagens ou reiniciar entre persistir/publicar/confirmar não
duplica voltas/recordes; reordenar eventos dentro da janela produz o mesmo
resultado normalizado; um carro atrasado não bloqueia a sessão inteira. Não
substituir dados ausentes por zero. Medir lag e registrar erros estruturados.

### Etapa 4 — API, mapa e classificação confiáveis

Migrar API e navegador para estado derivado, com snapshot inicial, sequência e
recuperação de conexão. Exibir idade/qualidade dos dados, preservar a classificação
autoritativa e implementar interpolação da distância acumulada. Manter balões,
nomes, equipes, bandeiras e botões já entregues.

Aceite: reconectar ou abrir o painel após a chegada recupera estado e resultados;
a falta de um evento não congela o grid; não ocorre movimento para trás na linha
de chegada; um intervalo ao carro da frente nunca é rotulado como diferença ao líder.

### Etapa 5 — Acompanhamento de piloto, carro e equipe

Adicionar seletores e comparação dos dois carros da equipe. Exibir última,
melhor e pior volta, ritmo limpo, volta teórica, histórico e matriz de parciais.
Comparações usam a mesma linha e condições identificadas. Cores têm legenda e
alternativa textual acessível.

Aceite: volta mais rápida não muda a classificação sozinha; voltas com boxes e
neutralização são identificadas; comparação deixa clara a referência escolhida;
melhor parcial pessoal e melhor parcial da corrida são calculadas corretamente.

### Etapa 6 — G e refinamento do comportamento de corrida

Calcular aceleração longitudinal/lateral nos subpassos, usando geometria física,
e publicar valor atual e picos da janela. Acrescentar indicador visual e gráficos
alinhados por distância para comparar voltas. Gráficos de 1 Hz devem indicar sua
resolução; análises mais finas exigem dados adicionais, não interpolação apresentada
como medição.

Validar entrada/percurso/saída dos boxes e recalibrar estratégia A antes de exigir
que o carro alcance fisicamente os boxes com combustível. Introduzir bandeiras e
neutralização em uma entrega posterior à cronometragem, com regras e testes próprios.
Revisões do limite de ultrapassagens, pneus e vazão de abastecimento exigem atualizar
o regulamento proposto antes de substituir as regras atuais.

Aceite: G não muda ao acelerar a reprodução; curva e frenagem têm valores coerentes;
não há pico artificial ao iniciar/parar administrativamente. O painel identifica
valores simulados e não apresenta carga vertical ou fisiologia não modeladas.

## 7. Estratégia de testes e validação

Usar fixtures pequenas e determinísticas como validação principal. Exemplos
obrigatórios:

- Linha cruzada entre amostras; passagem pela chegada com `0,99→0,01`; vários pontos cruzados no mesmo passo; largada de trás da linha sem volta gratuita.
- Três setores totalizam a volta; trecho e acumulado são distintos; empate, primeira volta, volta com boxes e volta incompleta.
- Ranking durante ultrapassagem, entrada nos boxes, retardatário, abandono, chegada e parada administrativa.
- Kafka entrega duplicada, fora de ordem, erro de schema, indisponibilidade e reinício em cada ponto da confirmação de offsets/outbox.
- Replay não depende do cadastro atual; v3 mantém rótulo legado, v4 não fabrica valores ausentes.
- Um carro atrasado, queda do WebSocket, API reiniciada, cliente lento e abertura após encerramento.
- Velocidade constante dá G longitudinal zero; curva de raio conhecido dá `v²/r/g0`; frenagem tem sinal negativo; escalas 1 e acelerada concordam.
- Fronteira entre snapshot inicial e fluxo ao vivo não perde nem duplica atualizações.

Ao final de cada marco, rodar somente as verificações pertinentes. Para a validação
integrada final, executar uma corrida curta e, se necessário para estratégia/chegada,
uma corrida completa acelerada de seed fixa. Repetir apenas para investigar falhas
ou após correções materiais; não fazer séries de simulações sem necessidade.

Comandos existentes para a implementação futura, conforme o componente alterado:

```bash
.venv/bin/ruff check src tests
.venv/bin/mypy src
.venv/bin/pytest tests/unit -q
RUN_KAFKA_INTEGRATION=1 .venv/bin/pytest tests/integration -q
npm --prefix frontend test
npm --prefix frontend run build
docker compose config --quiet
```

Adicionar testes de contratos, replay e ponta a ponta aos comandos/documentação
quando suas fixtures e serviços forem implementados. Os novos testes e evidências estão registrados ao final deste plano.

## 8. Riscos e reversão

- Uma frequência de 1 Hz no modo acelerado pode avançar grande parte da volta entre amostras; preservar passagens e âncoras visuais, sem fabricar precisão.
- Mudar apenas os tempos mantendo a física antiga criaria G e velocidades incoerentes. Por isso a base física é a primeira etapa.
- Gaps tomados em pontos distintos podem contrariar a classificação; o contrato precisa carregar a referência e a idade da medição.
- A outbox aumenta o código operacional, mas evita perder derivados entre gravação PostgreSQL e envio Kafka. Não introduzir CDC só para substituí-la.
- Um modo muito acelerado pode exceder a capacidade de integração; limitar a escala por configuração e medir antes de ampliar.
- Reinício do simulador continua encerrando a corrida ativa; recuperação/reinício do consumer não deve encerrar a corrida.
- Novos contratos/colunas entram de forma aditiva e versionada; migração ocorre entre provas. Rollback exige restaurar a versão anterior do código e Compose entre corridas, sem apagar histórico. Não há seletor de versão em execução.

## 9. Padrões adotados nesta entrega

| Decisão | Proposta para avançar |
| --- | --- |
| Padrão de reprodução | Acelerado em 45 vezes; `RACE_TIME_SCALE=1` habilita relógio normal. Padrão assumido sem resposta à pergunta opcional. |
| Pontos de parcial | P01–P15 mais chegada; quantidade e localização configuráveis após mapear a pista. Não confundir com curvas. |
| Grau de realismo | Categoria própria preservando regras atuais; comportamento físico e apresentação progressivamente mais realistas. |
| Duração | 60 voltas como configuração atual; chegada por distância, duração de parede apenas consequência da escala. |
| Escala, atraso tolerado e retenção | Valores iniciais na especificação; calibrar com métricas locais e registrar as escolhas. |
| Regras antigas artificiais | Revisar teto de ultrapassagens, limiar de pneu e tempo fixo de abastecimento em etapa própria, sem alteração silenciosa. |

## 10. Progresso

- [x] Revisar código, documentação e testes existentes.
- [x] Consultar referências primárias de circuito, cronometragem, G e CDC.
- [x] Especificar regras, lacunas, contratos, critérios de aceite e sequência.
- [x] Registrar proposta de decisão arquitetural e ligar o plano ao README.
- [x] Adotar os padrões documentados; ajuste do consumo explicitado na ADR 0010.
- [x] Implementar etapa 1.
- [x] Implementar etapa 2.
- [x] Implementar etapa 3.
- [x] Implementar etapa 4.
- [x] Implementar etapa 5.
- [x] Implementar etapa 6 e abrir entregas posteriores de realismo.
- [x] Registrar evidências de validação e medir metas de latência.

## 11. Evidências de entrega em 04/10/2026

- Ruff e mypy: aprovados em `src` e `tests` (39 arquivos tipados).
- `RUN_KAFKA_INTEGRATION=1 .venv/bin/pytest -q tests`: 53 testes aprovados.
- Frontend: 8 testes aprovados e build TypeScript/Vite concluído.
- PostgreSQL real: `docker compose exec -T api python < tests/integration/validate_projection_recovery.py`.
  Schema isolado removido ao final; deduplicação por offset/fato/linha, recuperação,
  outbox, rollback de evento inválido e processamento em lote verificados.
- Navegador Brave/Playwright: 20 carros, seleção de equipe com dois participantes,
  parciais restauradas após recarga, controles de início/parada e largura de 375 px
  sem rolagem horizontal da página. Nenhum erro JavaScript nessa verificação.
- Última verificação de latência: 10 amostras em 20 segundos, idade do quadro
  entre 0,884 e 0,972 segundo, sem atraso crescente. É uma medição local da idade
  do snapshot via API, não uma garantia de percentil de latência em produção.
- Replay de 1.500 eventos históricos: de 9,05 para 2,24 segundos após reduzir
  leituras/escritas repetidas da projeção. Não exigiu novas simulações.
- As provas completas usadas no diagnóstico revelaram entrada tardia de A,
  autonomia insuficiente com duas cargas exatas e ordenação de retardatário.
  Essas condições receberam testes específicos. O teste de A confirmou 60 voltas
  com uma parada após a recalibração; o teste de C verifica o cálculo exato da
  terceira parada com reserva e desconto do combustível existente.
- As execuções curtas foram repetidas somente para corrigir o atraso do consumer.
  Não foi feito levantamento estatístico por múltiplas sementes.
- Jota: API local e timer de indexação de dois minutos ativos; contexto do projeto
  registrado na base de conhecimento e código/documentação indexados no PostgreSQL.

## 12. Limites e próximos incrementos

A geometria é aproximada, incluindo os três setores e o corredor visual de boxes.
O gráfico compara tempos medidos nas mesmas posições de checkpoint; não inventa
amostras de velocidade entre as passagens. Neutralização, bandeiras, SC/VSC, chuva,
penalidades e carga vertical permanecem fora desta entrega, conforme o escopo.
O modelo ainda conserva o teto de ultrapassagens e pressão de pneus do laboratório.
Simulações não substituem dados oficiais de pista ou fisiologia do piloto.

Flink/Spark, ClickHouse, Iceberg, CDC e retenção automática do histórico operacional
não foram adicionados. Testes de caos exaustivos e carga contínua ficam para etapa
posterior; os testes realizados cobrem os caminhos de recuperação descritos acima.

## 13. Melhoria incremental: validação da pista

Objetivo: rejeitar parâmetros que tornam a física indefinida antes da largada.
Escopo restrito ao domínio e testes, sem migrações ou alteração das regras atuais.
Foram acrescentadas verificações de números finitos/positivos, quantidades inteiras,
ordem dos boxes, curvas sem sobreposição, raio não nulo e aderência dos três
compostos. Checkpoints não podem coincidir com finais de setor ou chegada: a
coincidência produzia trechos de duração zero no mesmo local.

- [x] Validar a configuração atual sem mudar o comportamento da corrida.
- [x] Preservar números inteiros representados como `double` no controle Avro.
- [x] Verificar configurações inválidas com testes de domínio, sem novas corridas completas.
- [x] Confirmar regressões: 147 testes Python aprovados, Ruff e mypy sem erros.
- [x] Atualizar serviços; endpoint de pista e recuperação PostgreSQL aprovados.
- [x] Incremento pronto para commit independente.

## 14. Melhoria incremental: preservar a geometria do acompanhamento

O gráfico de parciais agora recebe a mesma pista congelada da sessão utilizada
pelo mapa. Consultar a pista atual continua sendo o fallback para sessões sem
metadados, mas essa resposta não substitui a configuração histórica disponível.
A tabela ordena checkpoints e setores pela posição física, em vez de colocar
S1/S2 depois de todos os checkpoints.

- [x] Compartilhar a configuração congelada entre mapa e acompanhamento.
- [x] Ordenar parciais pela distância normalizada na pista da sessão.
- [x] Build e oito testes frontend aprovados.
- [x] Teste de navegador com API de pista deliberadamente diferente: gráfico
  preservou a posição original de P01; tabela apresentou P04, S1, P05 e P12, S2,
  P13 nessa ordem; nenhum erro JavaScript.
- [x] Verificação reutilizou a corrida encerrada; nenhuma nova corrida foi iniciada.
