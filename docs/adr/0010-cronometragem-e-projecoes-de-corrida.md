# ADR 0010: cronometragem por eventos e projeções da corrida

## Estado

Implementada em 04/10/2026. Substitui, para novas corridas, os tempos estimados
e o consumo de telemetria bruta pelo painel descritos nas ADRs anteriores.
Os contratos antigos permanecem disponíveis para testes e leitura de legado.

## Atualização de decisão

Em 06/10/2026, a seleção do motor foi definida na ADR 0014: Spark é o único
motor distribuído adotado. O consumer Python continua responsável pelas
projeções online; Spark arquiva eventos e calcula agregados batch.

## Contexto

O laboratório já publica telemetria e mostra a corrida. Os tempos atuais são
estimados, o avanço não é integrado diretamente da velocidade e o painel depende
de eventos brutos completos. A evolução exige publicação por segundo, passagens
cronometradas, comparações por piloto/equipe e G derivado de um modelo coerente.

## Decisão

1. Separar integração física, publicação de snapshots a 1 Hz real e eventos imediatos de passagem.
2. Publicar diretamente do simulador ao Kafka, mantendo Avro e Schema Registry. Não adicionar Debezium ao caminho da telemetria.
3. Introduzir um consumer Python de validação/cronometragem com transformações independentes de Kafka e motor distribuído escolhido em etapa própria.
4. Consolidar estado, voltas e parciais no backend. Publicar derivados e fornecer snapshot inicial + WebSocket versionado ao painel.
5. Confirmar offsets após processamento durável; usar deduplicação e outbox PostgreSQL para os derivados. Essa decisão não garante entrega exatamente uma vez do produtor; sua política de falha deve ser explícita.
6. Versionar a mudança semântica de tempos e relógio numa nova família de contratos/tópicos. Preservar leitura de v3 como legado e fazer o corte entre corridas.
7. Manter regras próprias de categoria e as estratégias autorizadas. Não representar o laboratório como um regulamento oficial de Fórmula 1.

## Alternativas consideradas

- Calcular tudo no navegador: rejeitada para cronometragem, pois perde histórico na reconexão e pode divergir entre clientes.
- Colocar dados dos carros no PostgreSQL e usar CDC para transportá-los: etapa desnecessária para uma fonte que já produz eventos.
- Migrar imediatamente para um motor distribuído: adiado até existirem contratos e fixtures de comportamento estáveis.
- Apenas adicionar campos ao Avro v3: insuficiente para comunicar a mudança de significado dos tempos existentes.

## Consequências

Aumenta a quantidade de contratos e projeções, mas permite auditar parciais,
reprocessar eventos e recuperar o painel. Latência, ordenação entre tópicos,
retardatários e qualidade dos dados passam a ter regras explícitas. G permanece
estimativa física e só entra depois de corrigir o relógio e a integração do movimento.

## Referências internas

- [Regras propostas](../planejamento/regras-corrida-v2.md).
- [Plano de implementação](../execplan-refinamento-corrida.md).

## Decisões de implementação e limites

- Física em passos de 20 ms; escala padrão 45 e snapshots a 1 Hz de relógio real.
  Eventos usam `simulation_time_us` como tempo autoritativo dos cálculos; UTC
  identifica produção/transporte. Controle congela escala, pista e participantes.
- Geometria, checkpoints, setores e boxes são aproximações versionadas. A configuração
  não representa levantamento oficial de Interlagos.
- A entrada física dos boxes tornou inviável a combinação de 220 kg por prova,
  tanque de 110 kg e exatamente uma parada antes da metade. Foi enviada a escolha
  ao usuário; sem resposta, adotou-se a proposta recomendada: consumo nominal de
  218,9 kg/60 voltas (redução de 0,5%). O tanque permanece com 110 kg. A terceira
  parada de C continua descontando o combustível a bordo e acrescentando uma volta.
- Serviço de boxes usa o maior valor entre duração configurada e combustível
  adicionado/vazão de 12 kg/s; deslocamento dos boxes é separado do serviço.
- Pressão cresce por distância; compostos ajustam aderência lateral em +1%, base
  e −1%. O limite legado de 12 ultrapassagens permanece configurável.
- Projeção em lotes de até 100 eventos ou 50 ms, transação PostgreSQL única por lote.
  Cada evento tem savepoint; estados são gravados uma vez por sessão/lote. Análises
  intermediárias do mesmo lote são substituídas pela última revisão antes da outbox.
- Offsets confirmados depois da transação, em lote assíncrono; falha causa replay
  idempotente. Outbox só é removida após confirmação do Kafka. Não há promessa
  de entrega exatamente uma vez no transporte.
- O produtor encerra a sessão como falha se não confirmar publicação; reinício
  não retoma uma corrida parcial. O estado REST informa essa falha, mesmo se
  Kafka estiver indisponível para publicar um evento terminal.
- Parciais tardias corrigem análises, inclusive após o último quadro. O histórico
  deduplica por corrida/carro/volta/linha; a janela de gaps conserva três voltas.
  Quadros incompletos aguardam três snapshots/segundos e preservam posições anteriores.
- O PostgreSQL mantém as projeções operacionais sem expurgo automático. Kafka
  retém sete dias. A etapa posterior da ADR 0011 implementou o arquivo analítico
  externo em Parquet no MinIO com Spark.
- G é horizontal e simulado. Ajustes discretos de tráfego/boxes sem aceleração
  física confiável publicam G ausente, em vez de representar um impacto fictício.
- Retorno ao modelo antigo exige parar a corrida e restaurar a versão anterior
  do código/Compose. Não existe seletor automático v3/v4 nem remoção de históricos.

### Revisão de 06/10/2026: boxes

Por solicitação de Rafael, o limite passa a 60 km/h da entrada até a saída.
A revisão da pista é `interlagos-lab-v2`; sessões anteriores preservam sua
configuração congelada. O nome do arquivo JSON mantém a versão do formato.
O serviço ocupa tempo físico: maior duração entre serviço configurado e
abastecimento a 12 kg/s, considerando operações simultâneas. Os pneus são
substituídos na primeira parada; a terceira de C permanece somente abastecimento.
A classificação usa a distância percorrida, inclusive durante a parada, de modo
que o retorno pode acontecer em uma posição inferior. Os eventos de pit stop
permitem medir os intervalos entre entrada, início/fim do serviço e saída.

### Revisão de 07/10/2026: aproximação da vaga

Durante o trecho entre a entrada e a vaga, o carro calcula a velocidade-alvo pela
distância restante no trajeto do pit lane. A curva planejada usa metade da
capacidade máxima de frenagem, criando margem para o integrador discreto e
evitando zerar a velocidade apenas ao cruzar a vaga. O serviço ainda começa na
posição configurada do box e a parada final fica limitada à resolução física de
20 ms.
