# Limitações conhecidas e próximos passos

## Limitações funcionais

- A pista, a força G e a física são aproximações educacionais.
- Não há safety car, virtual safety car, bandeiras, neutralização, penalidades,
  DRS, temperatura de pista ou clima variável depois do início configurado.
- Colisões programadas retiram os carros; não há dinâmica de impacto.
- Furos são cenários determinísticos, não resultado emergente da pista.
- O estado físico de uma corrida não é retomado após reinício do producer.
- O setup salvo durante uma corrida vale para a próxima sessão.

## Limitações de dados

- Kafka retém sete dias e tem um único broker.
- PostgreSQL não tem expurgo das projeções/eventos discretos.
- MinIO não tem lifecycle, backup ou replicação.
- O arquivo bruto depende dos schemas históricos do Registry para decodificação.
- O script `007_pneu_chuva.sql` não é reaplicado pelo bootstrap Python.
- Não há Iceberg, ClickHouse, CDC ou Protobuf.

## Limitações da aplicação

- API e serviços não têm autenticação, autorização ou TLS.
- O frontend usa Vite em modo de desenvolvimento no container.
- O PostgreSQL não é exposto ao host.
- O grupo do consumer online é fixo no código.
- Nem todas as variáveis lidas pelo código são repassadas pelo Compose.
- O adapter e simulador históricos continuam no pacote, embora o Compose use o
  caminho físico atual.

## Limitações de operação e qualidade

- Não há CI/CD, Kubernetes ou deploy de produção.
- Não há métricas, traces, dashboards ou alertas.
- Não há E2E automatizado de navegador ou carga.
- A integração PostgreSQL é um script manual que não é copiado para a imagem.
- Os jobs Spark não têm suíte automatizada própria.
- Há docstrings históricas em inglês e a regra de documentação pública não é
  verificada automaticamente.

## Próximos passos baseados nas lacunas atuais

1. Automatizar as migrações PostgreSQL e incluir a revisão `007` no caminho de
   upgrade de volumes existentes.
2. Criar testes pequenos e determinísticos para os jobs Spark e para a paridade
   com o consumer.
3. Adicionar readiness real para producer, consumer e Spark, além de métricas de
   atraso, outbox e DLQ.
4. Criar um build de produção do dashboard e proteger API e transporte antes de
   qualquer deploy fora da máquina local.
5. Implementar CI para Ruff, mypy, pytest, frontend e validação Compose.
6. Definir backup, restauração e retenção para PostgreSQL e MinIO.
7. Refinar realismo com desaceleração contínua na vaga, neutralização, bandeiras
   e penalidades, acompanhadas de regras e testes.
8. Avaliar Iceberg ou ClickHouse somente com casos de consulta e retenção claros;
   a implementação atual não depende deles.

Os próximos passos 3 a 8 são recomendações derivadas das lacunas verificadas.
Eles não representam componentes já aprovados ou implementados.
