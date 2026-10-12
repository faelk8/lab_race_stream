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
- A retenção de eventos PostgreSQL não remove projeções nem recibos de deduplicação.
- MinIO não tem lifecycle ou replicação externa; há backup local no mesmo host.
- O arquivo bruto depende dos schemas históricos do Registry para decodificação.
- O registro `schema_migrations` mantém versão e checksum; os testes atuais
  cobrem detecção de checksum diferente. A suíte completa de upgrade/reexecução
  em PostgreSQL isolado permanece limitada.
- Não há Iceberg, ClickHouse, CDC ou Protobuf.

## Limitações da aplicação

- A API não tem identidade individual nem autorização por ação; o painel é de
  uso local.
- O Compose principal usa Vite em modo de desenvolvimento. Há arquivos de
  composição adicionais no repositório que não fazem parte do uso deste laboratório.
- O PostgreSQL não é exposto ao host.
- O grupo do consumer online é fixo no código.
- Nem todas as variáveis lidas pelo código são repassadas pelo Compose.
- O adapter e simulador históricos continuam no pacote, embora o Compose use o
  caminho físico atual.

## Limitações de operação e qualidade

- CI, publicação e deploy não estão configurados no repositório compartilhado.
- O perfil local opcional oferece Prometheus, Grafana e métricas básicas dos
  serviços; não há traces OpenTelemetry, SLOs nem alertas.
- Não há E2E automatizado de navegador ou carga.
- A integração PostgreSQL é um script manual que não é copiado para a imagem.
- Os agregados, a classificação medalhão e a contagem de paradas Spark têm teste
  com fixtures locais; falta teste ponta a ponta do decoder Avro, leitura Parquet
  e escrita/recuperação no MinIO como execução automatizada. Uma validação manual
  ponta a ponta foi feita com a corrida já arquivada `race-c93b4916a097`.
- Há docstrings históricas em inglês e a regra de documentação pública não é
  verificada automaticamente.

## Próximos passos baseados nas lacunas atuais

1. Automatizar a validação ponta a ponta do decoder Avro, leitura Parquet e
   escrita S3A usando fixtures locais no serviço Spark de testes.
2. Ampliar o teste isolado de migrações para reexecução e upgrade completo.
3. Avaliar Iceberg ou ClickHouse somente se surgirem consultas e requisitos
   locais que justifiquem essas ferramentas.

Os itens acima são recomendações derivadas das lacunas verificadas; não
representam componentes já aprovados ou implementados.
