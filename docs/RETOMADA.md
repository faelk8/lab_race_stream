# Retomada do RaceStream

Atualizado em 06/10/2026. Este arquivo é o ponto de entrada após pausa por crédito,
fechamento do chat ou troca de modelo. O repositório e o Jota guardam o estado;
não é necessário copiar toda a conversa.

## Ajuste do pelotão e nomes Kafka (06/10/2026)

Removida do pelotão a coluna **DIF. LÍDER**. Os tópicos de novas publicações
foram simplificados para `telemetry`, `validated`, `timing`, `lap_completed`,
`pitstop`, `incident`, `control`, `state`, `analytics` e `dead_letter`. O README
liga cada tópico ao Redpanda Console e referencia o novo
[dicionário de dados](dicionario-de-dados.md). A decisão está registrada na
[ADR 0013](adr/0013-nomes-curtos-topicos-kafka.md). Tópicos antigos ficam
preservados para consulta histórica. Broker, Schema Registry, API, consumer,
simulador, painel e Spark foram atualizados; Spark usa o checkpoint v2, mantendo
os arquivos anteriores. Testes unitários pertinentes, Ruff, build do painel e
Compose aprovados. A API lista os aliases e o broker contém os dez novos tópicos.
Os links individuais dos dez tópicos no Redpanda Console responderam HTTP 200.
Não foi iniciada uma nova corrida para validar esta alteração; uma corrida já
ativa terminou antes da atualização dos serviços.

O serviço de sincronização do Jota concluiu com `Result=success` e
`ExecMainStatus=0`. A leitura e a gravação da preferência de idioma no PostgreSQL
do Jota continuam indisponíveis (`OperationalError`); nenhuma preferência foi
declarada como persistida.

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
Há uma alteração preexistente em `.env.example`; não sobrescrever nem incluir
em commit sem verificar sua origem.

Para economizar créditos no Codex, considerar `gpt-6-luna` no seletor de modelos,
se disponível na conta, em tarefas pequenas com critérios claros e testes.
A [documentação oficial](https://learn.chatgpt.com/docs/models) recomenda Luna
para tarefas delimitadas. O modelo deste chat não foi trocado. Se o pedido for
sobre o Jota local, consultar os modelos instalados antes de alterar sua configuração.

## Onde consultar

- [Plano e histórico de melhorias](execplan-refinamento-corrida.md).
- [ExecPlan Spark, PostgreSQL e MinIO](execplan-spark-postgresql-minio.md).
- [ExecPlan de cenários configuráveis e análises Spark](execplan-corrida-interativa.md).
- [ADR 0011 de persistência e Spark](adr/0011-spark-postgresql-minio.md).
- [Decisões técnicas e limites](adr/0010-cronometragem-e-projecoes-de-corrida.md).
- [Contexto compartilhado com Jota](jota-contexto.md).
- [Evidências anteriores](validation/refinamento-v4.json).
- `git log --oneline -12`: commits efetivamente registrados.
- `git status --short`: alterações ainda não commitadas.

## Procedimento de retomada

Leia `AGENTS.md`, este arquivo e a última seção do plano. Consulte as preferências
no Jota conforme `AGENTS.md`. Confirme arquivos e serviços atuais antes de seguir;
um teste aprovado anteriormente não comprova uma alteração posterior.

Execute somente os testes pertinentes. Prefira fixtures de trechos curtos; não
rode corridas completas repetidamente. Faça um commit para cada melhoria validada.
Não declare push ou troca de modelo sem confirmação efetiva dessas operações.

Ao terminar uma etapa, atualize trabalho atual, evidências e pendências aqui e no
plano, então execute `systemctl --user start jota-racestream-sync.service`.
O timer do Jota também indexa os arquivos a cada dois minutos com a sessão ativa.
A gravação em arquivos preserva o trabalho mesmo se o Jota estiver indisponível.
Nesta sessão, o PostgreSQL do Jota retornou `OperationalError` tanto para leitura
quanto para gravação de preferências. As notas do projeto foram atualizadas; a
preferência de página desktop ainda precisa ser persistida quando o banco voltar.
O serviço de sincronização do Jota foi executado com sucesso e atualizou um
contexto do projeto.
