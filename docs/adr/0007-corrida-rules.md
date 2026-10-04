# ADR 0007: Regras de corrida.md

## Status
Aceita; estratégia C atualizada com terceira parada por solicitação de Rafael.

## Contexto
`corrida.md` substitui os perfis de massa e velocidade anteriores e especifica
estratégias, pilotos, pneus, boxes e poucas ultrapassagens.

## Decisões
- Interpretar “AC” como categoria C, conforme o resumo final do arquivo.
- Usar 4 equipes A, 4 B e 2 C; cada equipe possui dois carros. Categorias A/B/C
  têm pesos secos 500/510/515 kg e velocidades finais 290–320/280–310/260–290 km/h.
- Distribuir estratégias A/B/C entre os carros independentemente da categoria.
- Alturas determinísticas entre 1,60 e 1,90 m e peso calculado com IMC 22.
  IMC é uma aproximação educacional; não representa fisiologia individual.
- Capacidade de referência 110 kg; consumir 220 kg ao percorrer 60 voltas,
  contabilizando somente o movimento aceito após resolver o tráfego.
- Serviço de boxes de 3–6 segundos físicos, convertido pela compressão temporal
  da corrida. A primeira parada também troca pneus; as seguintes abastecem.
  O modelo ainda não representa o percurso físico da pista de boxes.
- A para ao esvaziar o tanque; B para a 10%, reabastece primeiro até 100% e,
  na segunda, coloca o necessário para terminar, limitado à capacidade.
- C para a 20%, reabastece primeiro até 50% e troca pneus; a segunda parada
  enche o tanque. Por solicitação explícita de Rafael, a terceira parada abastece
  somente o necessário para a distância restante mais uma volta de reserva.
  A quantidade adicionada desconta o combustível ainda presente; o total fica
  limitado à capacidade de 110 kg. A terceira parada não troca pneus.
- A reserva de C é configurável em `RaceRules.strategy_c_reserve_laps`, com
  padrão de uma volta. Para 60 voltas e consumo de 220 kg, equivale a 3,67 kg.
  A configuração antiga continua disponível com `strategy_c_extra_stop=False`.
- Pressão assumida em psi: inicia em 38, aumenta 0,02 por volta e estoura em 40.
  A taxa é uma aproximação configurável em `RaceRules`, não um modelo térmico.
- Comprimento dos carros 3 m; substituir a separação visual anterior de 60 m
  por separação física de 3 m na mesma faixa. Duplas em ultrapassagem usam uma
  segunda faixa lógica; somente duplas disjuntas disputam simultaneamente.
- Iniciar tentativas nas retas, com velocidade superior; permitir no máximo
  12 ultrapassagens em pista por corrida. Ganhos nos boxes não contam. Esse
  limite é uma simplificação educacional, sem garantia de pelo menos um passe.
- Manter tempo por volta estimado separado de velocidade física; usar subpassos
  de até 10 ms de relógio comprimido para boxes e tráfego. Deltas antigos de
  massa/velocidade continuam compatíveis com configurações personalizadas.
- Telemetria v3 adiciona pressão, contagem de paradas e faixa lógica, com defaults
  Avro para ler v1/v2. Nome e namespace do record permanecem iguais. Valores
  `out_of_fuel` e `tire_burst` usam o campo string existente `pit_status`.
- Migração idempotente altera apenas perfis que correspondem exatamente aos
  valores originais de fábrica; mantém configurações editadas. Resultados de
  corridas anteriores não são reescritos.

## Consequências e validação
O dashboard recebe a faixa lógica e mostra equipe, estratégia, pressão e boxes.
A API preserva metadados quando clientes antigos enviam apenas os seis campos
originais. O runner recarrega configurações antes de cada nova corrida.

Testes verificam perfis, consumo, thresholds, tempo de serviço, troca de pneus,
retirada, restrição de ultrapassagem e resolução Avro real de v1/v2 para v3.
Antes da inclusão da terceira parada, foram executadas duas corridas completas
de validação, seeds 42 e 7: ambas
atingiram 12 ultrapassagens, com 14 carros percorrendo aproximadamente 60 voltas
e 6 carros de estratégia C sem combustível após 48 voltas. Os detalhes estão
em `docs/validation/corrida-simulations.json`.

### Validação da terceira parada

Foi executada uma nova corrida completa, com semente 42. Os seis carros da
estratégia C fizeram três paradas e percorreram entre 59,253 e 59,898 voltas
nos 120 segundos. Nenhum carro abandonou por falta de combustível. Após descontar
o combustível necessário para a distância ainda restante, todos os carros C
mantiveram 3,667 kg de reserva, equivalentes a uma volta. A evidência está em
`docs/validation/corrida-terceira-parada.json`.

Os testes verificam a quantidade da terceira reposição descontando o combustível
presente, a reserva em provas com outra quantidade de voltas, o abastecimento da
segunda parada e a preservação dos pneus na terceira. A suíte com integração
Kafka passou com 34 testes; Ruff e verificação de tipos também passaram.
