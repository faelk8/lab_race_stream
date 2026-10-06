# Contexto compartilhado do RaceStream com o Jota

Atualizado em 04/10/2026. Repositório: `/home/rafael/Documentos/github/lab_race_stream`.
O índice acompanha o diretório de trabalho, incluindo alterações não commitadas.
Consulte os arquivos atuais antes de agir: este resumo não declara toda mudança
como validada nem autoriza alterações adicionais.

Rafael solicitou documentação em português do Brasil, poucas simulações,
telemetria por carro a cada segundo, parciais cronometradas, Kafka acessível pelo
Redpanda, acompanhamento por carro/piloto/equipe, melhor e pior volta e força G.
Preservar balões, nomes, equipes, bandeiras, ordem do pelotão e controles manuais.
A terceira parada de C deve repor somente o necessário para a distância restante
mais uma volta, descontando o combustível a bordo.

Implementação validada nesta instalação: motor físico a 50 Hz, snapshots a 1 Hz real, escala
45 configurável, 15 checkpoints, três setores e chegada. Consumer Python calcula
projeções duráveis e publica derivados por outbox PostgreSQL. Kafka/Avro tem
tópicos distintos para telemetria, passagens, voltas, boxes, incidentes, controle,
estado, análises e erros. Debezium não é necessário para esses eventos diretos.

Estado do trabalho, evidências e pendências estão no
`docs/execplan-refinamento-corrida.md`; decisões em
`docs/adr/0010-cronometragem-e-projecoes-de-corrida.md`.
O traçado, os setores e os raios são aproximações do laboratório. G representa
aceleração horizontal simulada. Bandeiras/neutralização e armazenamento analítico
distribuído permanecem como entregas futuras.

Painel: http://localhost:5173. Kafka: http://localhost:8080.
API: http://localhost:8000/docs. Jota: http://127.0.0.1:8765/health.
O timer `jota-racestream-sync.timer` atualiza o índice e este contexto a cada dois
minutos enquanto a sessão local está ativa. PostgreSQL é a fonte de verdade do
Jota; a projeção Neo4j é um processo separado.

Validação final: 53 testes Python, 8 testes frontend, build, Ruff/mypy e teste
PostgreSQL isolado aprovados. Última idade de snapshot via API: 0,884–0,972 s em
dez amostras. A proposta de reduzir o consumo nominal para 218,9 kg/60 voltas foi
adotada sem resposta à escolha opcional, para preservar uma parada de A; não
registrar essa escolha como preferência explicitamente confirmada por Rafael.

Melhoria incremental: validação antecipada de pista, boxes, curvas e parâmetros
físicos, com 94 casos adicionais e 147 testes Python aprovados ao todo.

O acompanhamento usa a pista congelada da sessão também no gráfico; mudanças
posteriores na API de pista não deslocam as parciais históricas. Tabela ordenada
pela distância física, incluindo S1 e S2 entre checkpoints. Validado no navegador
com respostas de pista divergentes, sem iniciar outra corrida.

Em 05/10/2026: chegada não inicia uma volta fictícia; abandono congela o
cronômetro individual e zera comandos e G instantâneo. Foram validados 151
casos Python no total e recuperação PostgreSQL, sem nova corrida pelo painel.

Também em 05/10/2026: indicador de força G diferencia “Sem medida” de zero
medido. Build, oito testes frontend e quatro condições no navegador aprovados;
nenhuma corrida nova pelo painel foi necessária para essas duas melhorias.

Em 06/10/2026: configuração interlagos-lab-v2 limita os boxes a 60 km/h,
da entrada à saída. Frenagem antecipada considera o subpasso físico; durante
serviço parado os comandos e G instantâneo ficam zerados. Teste curto com dois
carros cobre duração, combustível, pneus e retorno em segunda posição.
O ponto de retomada após pausa ou falta de créditos é docs/RETOMADA.md.

Validação de 06/10: 152 testes Python incluindo Kafka, Ruff, mypy e recuperação
PostgreSQL aprovados. Serviços locais reconstruídos, sem iniciar outra corrida.


Em 06/10/2026, Spark Structured Streaming 4.0.1 lê tópicos Kafka e arquiva
mensagens Avro originais em Parquet no MinIO, com offsets e checkpoint S3A.
Validação leu 7.960 registros em 8 tópicos sem offsets duplicados; reinício
retomou do checkpoint.
PostgreSQL continua autoridade operacional para configurações, corridas,
resultados e projeções. A API e o consumer seguem online sem substituição.
Console MinIO: http://localhost:19001; S3: http://localhost:19000. Plano: docs/execplan-spark-postgresql-minio.md.
