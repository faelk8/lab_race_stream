# ADR 0009: controle manual da corrida

## Estado
Aceito em 03/10/2026.

## Contexto
O painel precisa iniciar e parar a simulação em outro processo. O produtor
anterior iniciava provas sucessivas automaticamente.

## Decisão
Usar PostgreSQL para persistir comandos e estados. A API solicita início/parada;
um único worker reserva uma corrida pendente atomicamente e consulta seu estado
a cada passo. Um lock transacional e índice parcial único impedem corridas
controladas simultâneas. Repetir início retorna a corrida já ativa.

Parar encerra a prova e salva resultados parciais; iniciar novamente cria outra
prova. A parada publica um quadro com velocidade zero, sem avançar o relógio,
consumir combustível ou alterar posições. O frontend aceita esse quadro mesmo
com o mesmo tempo decorrido, desde que o instante do evento seja mais recente.

A telemetria continua Avro v3: `race_status` é uma string e passa a aceitar
`stopped`. Os estados de coordenação permanecem no contrato REST/PostgreSQL.
Falhas são registradas como `failed`. O reinício do único worker encerra execuções
interrompidas e preserva comandos pendentes.

## Consequências
O painel controla a corrida de fato e o simulador fica ocioso ao encerrar. Não há
retomada da prova encerrada. A recuperação pressupõe um worker no Compose;
replicação do simulador exigiria coordenação de propriedade e recuperação por
worker, além de persistência dos estados de cada carro.

## Validação
Testes de worker/API, quadro de parada, Kafka/Avro e concorrência no PostgreSQL;
início/parada real no navegador e vinte resultados parciais persistidos.
