# Limitações conhecidas e próximos passos

## Limitações funcionais

- A pista, a força G e a física são aproximações educacionais.
- Colisões programadas retiram os carros envolvidos e acionam safety car com
  bandeira amarela até o líder completar a volta seguinte. Não há VSC, bandeira
  vermelha, nem dinâmica física de impacto.
- Penalidades determinísticas de tempo podem ser configuradas na largada; não há
  penalidades emergentes durante a prova nem outras classes de sanção.
- Chuva e intensidade são definidas antes da largada e permanecem fixas durante
  a prova. Não há temperatura de pista ou DRS.
- Furos são cenários determinísticos, não resultado emergente da pista.
- O estado físico de uma corrida não é retomado após reinício do producer.
- O setup salvo durante uma corrida vale para a próxima sessão.

## Limitações de dados

- Kafka retém sete dias e tem um único broker.
- PostgreSQL não tem expurgo das projeções/eventos discretos.
- MinIO não tem lifecycle, backup ou replicação.
- O arquivo bruto depende dos schemas históricos do Registry para decodificação.
- O registro `schema_migrations` mantém versão e checksum; ainda falta validar
  upgrade, reexecução e recuperação de migração em PostgreSQL isolado.
- Não há Iceberg, ClickHouse, CDC ou Protobuf.

## Limitações da aplicação

- A API não tem identidade individual nem autorização por ação. A composição de
  produção aplica TLS e autenticação básica compartilhada no Caddy.
- O Compose local usa Vite em modo de desenvolvimento; o overlay de produção
  serve o build estático por Nginx.
- O PostgreSQL não é exposto ao host.
- O grupo do consumer online é fixo no código.
- Nem todas as variáveis lidas pelo código são repassadas pelo Compose.
- O adapter e simulador históricos continuam no pacote, embora o Compose use o
  caminho físico atual.

## Limitações de operação e qualidade

- Há CI para testes/builds; não há entrega contínua, Kubernetes ou deploy
  automatizado de produção.
- Não há métricas, traces, dashboards ou alertas.
- Não há E2E automatizado de navegador ou carga.
- A integração PostgreSQL é um script manual que não é copiado para a imagem.
- Os agregados e a paridade Spark têm teste com fixtures locais; falta teste
  ponta a ponta do decoder Avro, leitura Parquet e escrita/recuperação no MinIO.
- Há docstrings históricas em inglês e a regra de documentação pública não é
  verificada automaticamente.

## Próximos passos baseados nas lacunas atuais

1. Adicionar teste ponta a ponta do job Spark com envelopes Avro, Parquet e
   Schema Registry, mantendo as fixtures locais atuais para as regras.
2. Validar upgrade, reexecução e checksum das migrações em PostgreSQL isolado.
3. Adicionar readiness real para producer, consumer e Spark, além de métricas de
   atraso, outbox e DLQ.
4. Revisar e endurecer autenticação, segredos, Kafka e disponibilidade antes de
   expor o esqueleto Compose de produção fora de rede controlada.
5. Definir backup, restauração e retenção para PostgreSQL e MinIO.
6. Avaliar Iceberg ou ClickHouse somente com casos de consulta e retenção claros;
   a implementação atual não depende deles.

Os itens acima são recomendações derivadas das lacunas verificadas; não
representam componentes já aprovados ou implementados.
