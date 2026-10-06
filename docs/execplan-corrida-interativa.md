# Plano de execução: cenários configuráveis e análises Spark

Atualizado em 06/10/2026. Estado: implementado e validado localmente.

## 1. Objetivo

Permitir configurar clima e incidentes antes da largada, aplicar efeitos
determinísticos na simulação física e comparar agregados de voltas calculados
no Spark com os resumos produzidos pelo consumer online.

## 2. Escopo

Inclui API, PostgreSQL, simulador, painel desktop, Spark e documentação. Chuva
reduz aderência e velocidade conforme intensidade; todos os carros recebem uma
parada escalonada para montar pneus de chuva e abastecer. Furo de pneu agenda
troca emergencial; colisão programada retira os carros envolvidos. Penalidades
e neutralização ficam como etapas seguintes. A prova segue local e reproduzível.

## 3. Estado atual

O painel inicia corridas com configuração fixa e já usa layout desktop com
adaptações estreitas. PostgreSQL persiste o ciclo da corrida. O Spark arquiva
envelopes Avro em Parquet, enquanto o consumer calcula voltas, parciais e
analytics online.

## 4. Arquitetura alvo

```text
Painel -> API -> PostgreSQL (cenários) -> worker -> simulador físico -> Kafka
                                                  -> consumer -> analytics online
Kafka -> Spark -> Parquet no MinIO -> agregados por carro/volta -> comparação
```

## 5. Contratos

- Cenários são JSON persistido junto à corrida e copiado para a configuração do
  worker ao reservar a largada.
- Chuva: ativa/desativa, volta inicial e intensidade entre 0,1 e 1; a maior
  intensidade aumenta os tempos medidos de volta.
- Pneus de chuva: parada individual escalonada a cada 2–6 voltas; chuva iniciada
  tarde demais é rejeitada para preservar espaço até a chegada. Tanque completado
  durante o serviço e composto montado publicado na telemetria.
- Incidentes: tipo, volta, carro principal e segundo carro opcional para colisão.
- Agregado Spark: corrida/carro, quantidade de voltas válidas, melhor, pior e
  média; paridade compara quantidade, melhor e pior com `race.analytics.v1`.
- Os schemas Kafka existentes permanecem compatíveis; os agregados são dados
  analíticos no MinIO.

## 6. Etapas

1. Persistir e validar cenários no início da corrida.
2. Aplicar chuva, furo com parada obrigatória e colisão em voltas configuradas.
3. Expor formulário de cenários no painel e manter apresentação desktop.
4. Gerar agregado Spark de voltas e relatório de paridade com analytics do consumer.
5. Atualizar README, retomada e este plano com evidências.

## 7. Testes e validação

- Testes unitários determinísticos de chuva, furo e colisão.
- Comparação do tempo de volta com intensidades diferentes e teste curto de
  troca para pneu de chuva com abastecimento.
- Teste API dos cenários e persistência/recuperação quando PostgreSQL local estiver
  disponível.
- Verificação de sintaxe Spark e execução sobre arquivo Kafka real.
- Ruff, mypy, pytest, build frontend e `docker compose config --quiet`.

## 8. Riscos

- Um cenário inválido poderia falhar só durante a corrida; validar IDs e voltas
  antes de enfileirar.
- O consumer pode publicar analytics antes de receber todas as voltas; a
  comparação deve usar a revisão mais recente e explicitar ausências.
- Chuva simplificada não substitui modelo meteorológico; intensidade é um fator
  determinístico de aderência, não previsão de pista.

## 9. Decisões

- Configuração de incidentes é explícita e reproduzível, sem aleatoriedade oculta.
- Colisão programada gera abandono dos dois carros no ponto configurado.
- Pneu furado força uma visita aos boxes e reinicia idade/pressão dos pneus.
- Pneus de chuva são montados em paradas distribuídas deterministicamente; a
  API rejeita início tardio que não permita manter cada parada a 2–6 voltas da
  anterior e da chegada; com 20 carros e 60 voltas, chuva inicia até a volta 21.
- O layout permanece página desktop; larguras menores podem exigir rolagem.

## 10. Progresso

- [x] Inspecionar plano vigente, modelos, schemas, painel e fluxo de largada.
- [x] API e persistência dos cenários.
- [x] Efeitos físicos determinísticos.
- [x] Controles desktop para configurar a corrida.
- [x] Agregado Spark e comparação com consumer.
- [x] Validação e sincronização da documentação com o Jota.

Validação em 06/10/2026: o módulo físico passou com 20 testes e a seleção
direcionada com 7 testes; Ruff, mypy, build React e `docker compose config --quiet` passaram. A
migração 006 foi aplicada na instância local e os serviços API, simulador,
dashboard e Spark estão ativos. O job leu os dados reais arquivados no MinIO e
comparou 80 pares corrida/carro: 80 coincidiram na contagem, melhor e pior volta.
Uma requisição HTTP real para colisão inválida retornou 422 sem enfileirar prova.

## 11. Pendências

O decoder Spark usa o schema writer indicado pelo ID Confluent de cada mensagem
e o schema reader compatível mais recente do Schema Registry. Os agregados são
gravados em `lap_performance/` e a comparação em `consumer_parity/` no bucket
`racestream`.

Continuam fora desta entrega: desaceleração contínua até a vaga, bandeiras,
neutralização e penalidades. A chuva é um fator físico determinístico de pista
molhada, sem previsão meteorológica detalhada. O teste legado com `TestClient`
ficou bloqueado na inicialização do lifespan nesta instalação; a nova rota foi
validada diretamente com dependências injetadas, sem iniciar serviços externos.
O POST de configuração inválida foi exercitado pelo HTTP da API local e retornou
422 sem criar uma corrida.
O serviço de sincronização do Jota terminou com sucesso e atualizou um contexto.
As operações de listar/salvar preferência no PostgreSQL do Jota continuam
retornando `OperationalError`; a preferência de desktop ficou registrada nos
arquivos do projeto, aguardando a recuperação desse banco.
