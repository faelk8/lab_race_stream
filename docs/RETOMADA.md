# Retomada do RaceStream

Atualizado em 07/10/2026. Este arquivo é o ponto de entrada após pausa por crédito,
fechamento do chat ou troca de modelo. O repositório e seus planos guardam o
estado; não é necessário copiar toda a conversa.

## Auditoria da arquitetura e atualização do README (06/10/2026)

O usuário solicitou usar apenas Spark, registrar com clareza o que está e o que
não está implementado, reorganizar o menu do README e remover sua seção de links
de acesso. A verificação do Compose encontrou API, dashboard, Kafka, Schema
Registry, PostgreSQL, MinIO, consumer, simulador e `spark-archive` ativos; as
verificações de saúde configuradas estavam saudáveis.

Situação confirmada no código: PostgreSQL é o único banco relacional. MinIO é
object storage, não outro banco relacional. Spark Structured Streaming arquiva
os tópicos Kafka em Parquet e o job Spark batch calcula agregados e paridade. O
consumer Python ainda realiza validação e projeções online. A implementação não
inclui Protobuf, ClickHouse, Iceberg, Debezium, Kubernetes, OpenTelemetry,
Prometheus, Grafana ou GitHub Actions/CI/CD. O README agora apresenta essa
diferença entre stack local executável e possibilidades futuras, sem listar o
motor de processamento removido.

O menu interno do README segue: 1 Objetivo (1.1 problema); 2 Princípios (2.1
tecnologias); 3 Executar corrida (3.1 iniciar serviços e corrida, 3.2 finalizar,
3.3 telemetria); 4 Resultados; 5 Como analisar; 6 Simulação (6.1 configuração);
7 implementação; 8 documentação. Os acessos ficam na documentação técnica, sem
uma seção de links de serviços no README. A decisão de adotar Spark como único motor
distribuído está registrada na ADR 0014. Nenhuma corrida foi iniciada para essa
atualização documental.

## Ajuste do pelotão e nomes Kafka (06/10/2026)

Removida do pelotão a coluna **DIF. LÍDER**. Os tópicos de novas publicações
foram simplificados para `telemetry`, `validated`, `timing`, `lap_completed`,
`pitstop`, `incident`, `control`, `state`, `analytics` e `dead_letter`. O README
referencia o
[dicionário de dados](dicionario-de-dados.md). A decisão está registrada na
[ADR 0013](adr/0013-nomes-curtos-topicos-kafka.md). Tópicos antigos ficam
preservados para consulta histórica. Broker, Schema Registry, API, consumer,
simulador, painel e Spark foram atualizados; Spark usa o checkpoint v2, mantendo
os arquivos anteriores. Testes unitários pertinentes, Ruff, build do painel e
Compose aprovados. A API lista os aliases e o broker contém os dez novos tópicos.
Os links individuais dos dez tópicos no Redpanda Console responderam HTTP 200.
Não foi iniciada uma nova corrida para validar esta alteração; uma corrida já
ativa terminou antes da atualização dos serviços.

## Melhoria do painel em andamento

Correção de 06/10/2026: uma configuração de chuva na volta 30 para 20 carros
era rejeitada corretamente (HTTP 422), mas o painel escondia o motivo com um
alerta genérico. A largada seguinte foi aceita com chuva desabilitada e terminou
normalmente. O painel agora mostra o detalhe da API, informa o limite calculado
junto ao campo e bloqueia cliques duplicados. Verificação HTTP confirmou que a
tentativa tardia explica a volta 21 e não cria nova corrida. API e dashboard foram
reconstruídos; a última corrida permanece preservada no histórico.

Pedido de 06/10/2026: no pelotão, mostrar tempo da volta anterior e progresso
`volta/total`; manter o tempo da última volta ao terminar. O acompanhamento deve
permitir trocar carro, piloto ou equipe em qualquer momento da prova e o gráfico
de parciais deve atualizar com os dados recebidos e permitir inspeção interativa.

Implementado no painel: coluna de última volta no pelotão, progresso como
`atual/total`, gráfico com pontos acessíveis por teclado e hover mostrando parcial,
volta, tempo e referência. O gráfico é montado das análises recebidas ao vivo e
aparece a partir da primeira parcial. Controles de acompanhamento permanecem
disponíveis durante a prova. Validação local: testes do frontend e build TypeScript/
Vite aprovados. A inspeção visual durante uma corrida curta continua pendente;
nenhuma corrida foi iniciada para esta alteração.

## Trabalho atual

**Classificação e visualização do pelotão (07/10/2026):** o pelotão agora usa a
distância acumulada como critério principal e a posição oficial em caso de
empate; tempo de última volta não determina posição. O número exibido corresponde
à ordem apresentada. Os marcadores do mapa mantêm distância visual mínima ao
longo da linha de corrida e seguem a ordem da classificação, trocando após uma
ultrapassagem. Testes cobrem ordem por distância, mudança de ordem e espaçamento;
testes frontend/build e verificações Python passaram. Uma projeção pausada de 20
carros foi inspecionada: posições e distâncias estavam coerentes, com grupos
separados por apenas 3 m, insuficiente para os marcadores atuais. ADR 0019 registra
a regra. Carros retirados após colisão também são removidos do mapa, permanecendo
no pelotão e no histórico. Nenhuma nova corrida foi iniciada.

**Configuração de eventos e cadastro do piloto (07/10/2026):** após a colisão,
os dois carros envolvidos deixam de aparecer para eventos na mesma volta e nas
seguintes. A tela e a API também rejeitam eventos repetidos para o mesmo tipo,
participantes e volta; a comparação de colisões não depende da ordem dos carros.
Os testes cobrem a colisão repetida, o furo repetido e penalidades repetidas
mesmo quando o valor em segundos muda. O nome do piloto `DRV-01` foi atualizado
para Rafael Batista no seed e em uma migração aditiva para bancos existentes; o
Dockerfile inclui essa migração. O PostgreSQL ativo foi atualizado e a API
retornou Rafael Batista. API e dashboard foram reconstruídos e ficaram saudáveis.
Testes do frontend, build, testes focados da API e Ruff passaram. A interface
atualizada ainda precisa de uma verificação manual no navegador após recarga.

## Próxima continuidade recomendada

1. Fazer uma checagem manual no navegador: adicionar uma colisão, confirmar que
   seus carros saem das opções naquela volta e nas seguintes, trocar a ordem dos
   carros, tentar repetir o mesmo incidente e conferir a mensagem de bloqueio.
2. Decidir se eventos ainda não enviados devem sobreviver a uma recarga da página.
   Hoje `raceSetup` existe apenas no estado React e só é enviado quando a corrida
   começa; atualizar a página apaga o rascunho.
3. Criar testes automatizados próprios para os jobs Spark e a paridade com o
   consumer, que permanecem sem suíte dedicada.
4. Adicionar CI para Ruff, mypy, pytest, build do frontend e validação do Compose.
5. Planejar retenção, backup e restauração de PostgreSQL e MinIO, além de
   readiness e métricas para consumer e Spark.

Não iniciar uma corrida completa apenas para revisar o setup: as regras de
disponibilidade e duplicidade têm testes unitários e de API; a inspeção visual
pendente deve usar o formulário antes da largada e uma carga de teste isolada.

**Penalidade de tempo (07/10/2026):** a configuração da largada aceita penalidade
por carro, volta e duração. O painel oferece 5, 10 e 20 segundos e exibe o total
no pelotão e na telemetria. A sanção é publicada em `incident` e somada ao tempo
de chegada, podendo inverter a classificação final. Fixture curta comprovou uma
inversão por cinco segundos; nenhuma corrida completa foi iniciada. O plano de
realismo está concluído, com limitações registradas na ADR 0017.

**Realismo de corrida (07/10/2026):** a aproximação à vaga dos boxes desacelera
progressivamente e mantém o limite de 60 km/h. Colisões programadas acionam
safety car até o líder completar a volta seguinte: o pelotão fica limitado a
120 km/h, sem ultrapassagens, e voltas neutralizadas não entram em recordes ou
ritmo. Penalidades configuráveis de 5, 10 ou 20 segundos aparecem no pelotão e
na telemetria e são somadas ao tempo final, podendo inverter a classificação.
Testes direcionados, Ruff, mypy, typecheck e build foram aprovados; os serviços
foram reconstruídos e a prova completa não foi iniciada. Detalhes e limites na
[ADR de safety car](adr/0016-safety-car-e-voltas-neutralizadas.md) e na
[ADR de penalidades](adr/0017-penalidade-de-tempo.md).

**Safety car e bandeira amarela (registro anterior, 07/10/2026):** colisões programadas agora
neutralizam a prova até o líder completar a volta seguinte. O pelotão fica
limitado a 120 km/h e não pode ultrapassar em pista. Telemetria e painel informam
o estado, e voltas com qualquer passagem neutralizada não entram em recordes ou
ritmo. Testes determinísticos validaram início/fim, limite e exclusão analítica;
nenhuma corrida completa foi iniciada.

**Frenagem na vaga dos boxes (07/10/2026):** o carro agora usa a distância
restante do trajeto do pit lane para reduzir continuamente a velocidade até a
vaga. A curva reserva margem sobre a capacidade máxima de frenagem e conserva o
limite de 60 km/h. O trecho curto de boxes foi validado sem executar uma corrida
completa. Bandeiras/neutralização e penalidades continuam nas próximas etapas do
`execplan-realismo-corrida.md`.

**Grid, pelotão e eventos enriquecidos (06/10/2026):** a largada posiciona os
vinte carros em dez linhas de duas colunas. Durante a corrida, os três primeiros
recebem fundo verde claro; abandonos recebem vermelho claro. Após o encerramento,
as três primeiras linhas usam ouro, prata e bronze e exibem seus troféus. O cartão
de telemetria mostra força G instantânea e pico. `lap_completed` inclui volta
corrente e posição, enquanto `pitstop` inclui volta, composto e duração cumulativa
desde a entrada até a saída. A decisão está na ADR 0015 e a execução no plano
`execplan-grid-e-eventos.md`. Ruff, mypy, quatro testes Python direcionados,
testes do frontend, typecheck e build foram aprovados. Os schemas foram aceitos
pelo Schema Registry e os serviços alterados foram reconstruídos. Nenhuma
corrida completa foi iniciada para essa validação.

**Chuva e troca gradual para pneus molhados (06/10/2026):** intensidade agora
reduz velocidade máxima e aderência dos pneus secos (e afeta também o ritmo com
pneu de chuva), aumentando o tempo físico medido por volta. O setup aceita
composto `wet`. Com chuva, todos os carros recebem paradas reproduzíveis para
trocar para esse composto e completar o tanque, com intervalo de 2 a 6 voltas.
No grid padrão de 20 carros e 60 voltas, a chuva precisa começar até a volta 21;
a API e o simulador rejeitam início tardio que impeça as paradas individuais.
Telemetria e resultado carregam o composto montado. A migração 007
foi aplicada ao PostgreSQL local. Testes curtos confirmaram sequência, aumento do
tempo de volta com maior intensidade, troca, abastecimento e telemetria molhada.
Serviços API, simulador e dashboard foram reconstruídos; a API saudável publica
`wet` entre os compostos aceitos. Não iniciei corrida completa.

**Melhorias entregues em 06/10/2026:** o painel mantém página de desktop, com
largura mínima de 1.100 px. Antes da largada, permite configurar chuva (volta de
início e intensidade), furos de pneu e colisões por carro e volta. A chuva reduz
aderência e velocidade; os carros trocam pneus de chuva em paradas escalonadas
de 2 a 6 voltas e aproveitam para completar o tanque. A intensidade afeta o tempo
medido das voltas e a telemetria identifica o composto montado. O furo agenda
parada emergencial apenas para troca de pneus; a colisão programada retira os dois
carros na metade da volta escolhida. Os cenários ficam em PostgreSQL e acompanham
a configuração reservada pelo worker.

O job `stream-processing/spark/agregar_voltas.py` gera agregados de voltas
válidas e compara quantidade, melhor e pior volta com o último analytics do
consumer. Os Parquet ficam em `lap_performance/` e `consumer_parity/` no MinIO.
Validação real de 06/10: 80 pares corrida/carro comparados e 80 coincidentes.
O decoder consulta os schemas pelo ID dos envelopes no Schema Registry, então
aceita as versões Avro históricas compatíveis.

**Concluído:** limite de 60 km/h desde a entrada até a saída dos boxes,
serviço parado com duração física e classificação recalculada durante os boxes.
A terceira parada de C continua apenas abastecimento, com reserva de uma volta.

Validação: 152 testes Python (incluindo Kafka), Ruff, mypy e recuperação
PostgreSQL aprovados. Um trecho de dois carros comprovou limite, duração,
troca de pneus e perda de posição; não foi iniciada nova corrida pelo painel.
API, simulador e consumidor foram reconstruídos; dependências estão saudáveis.

Também foi entregue a primeira etapa de Spark/PostgreSQL/MinIO: Spark 4.0.1
arquiva envelopes Kafka em Parquet no bucket `racestream`; PostgreSQL mantém
configurações, estado, resultados e projeções. A leitura de validação encontrou 7.960 registros em 8 tópicos, sem offsets
duplicados; a contagem cresce enquanto chegam eventos. O reinício reutilizou
o checkpoint S3A.
O MinIO local usa as portas 19000 (S3) e 19001 (Console), pois a porta 9000 já
estava ocupada. MinIO Community foi compilado das tags fonte fixadas devido à
retirada das imagens públicas.

Próximos incrementos: desaceleração contínua até a vaga, bandeiras e
neutralização, penalidades, além de testes de recuperação/paridade com fixtures
curtas. Chuva e incidentes determinísticos configuráveis já foram entregues.
Consulte o ExecPlan específico antes de continuar.

## Onde consultar

- [Plano e histórico de melhorias](execplan-refinamento-corrida.md).
- [ExecPlan Spark, PostgreSQL e MinIO](execplan-spark-postgresql-minio.md).
- [ExecPlan de cenários configuráveis e análises Spark](execplan-corrida-interativa.md).
- [ADR 0011 de persistência e Spark](adr/0011-spark-postgresql-minio.md).
- [Decisões técnicas e limites](adr/0010-cronometragem-e-projecoes-de-corrida.md).
- [Índice da documentação técnica](index.md).
- [Plano de grid, pelotão e eventos](execplan-grid-e-eventos.md).
- [Evidências anteriores](validation/refinamento-v4.json).
- `git log --oneline -12`: commits efetivamente registrados.
- `git status --short`: alterações ainda não commitadas.

## Procedimento de retomada

Leia `.agents/AGENTS.md`, este arquivo e a última seção do plano. Confirme arquivos
e serviços atuais antes de seguir; um teste aprovado anteriormente não comprova
uma alteração posterior.

Execute somente os testes pertinentes. Prefira fixtures de trechos curtos; não
rode corridas completas repetidamente. Faça um commit para cada melhoria validada.
Não declare push ou troca de modelo sem confirmação efetiva dessas operações.

Ao terminar uma etapa, atualize trabalho atual, evidências e pendências aqui e no
plano. A gravação em arquivos versionados preserva o contexto para retomada.
