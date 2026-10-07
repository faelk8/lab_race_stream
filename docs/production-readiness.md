# Plano operacional e preparação para produção

Este plano registra o que foi automatizado e as etapas necessárias antes de
expor o RaceStream a usuários fora de uma rede controlada. A configuração de
produção em Compose é um ponto de partida para uma instalação de nó único; não
representa alta disponibilidade nem substitui revisão de segurança.

## 1. Estado entregue nesta etapa

- O workflow `.github/workflows/ci.yml` executa Ruff, mypy, pytest, testes e build
  do frontend, transformações Spark com fixtures e validação dos arquivos Compose.
- Os testes Spark validam agregação, deduplicação, seleção da análise online mais
  recente e paridade com `local[1]`, sem Kafka, PostgreSQL, MinIO ou corrida ativa.
- As migrações SQL recebem versão numérica, checksum SHA-256 e instante de
  aplicação em `schema_migrations`. Uma versão existente com outro arquivo ou
  checksum interrompe a inicialização; a correção deve entrar em arquivo novo.
- O dashboard de produção é compilado como arquivos estáticos e servido por
  Nginx. O Nginx encaminha `/api/` e `/ws/` à API no mesmo domínio.
- `docker-compose.prod.yml` remove as portas públicas de banco, Kafka, Schema
  Registry, MinIO e API. Caddy encerra TLS e aplica autenticação básica. O hash
  da senha e as credenciais devem vir de `.env.prod`, nunca do Git.
- Os rascunhos de chuva e eventos são salvos no `localStorage` com versão e
  validação. A configuração persiste no navegador usado; não sincroniza entre
  dispositivos ou navegadores.

## 2. Execução da composição de produção

Copie `.env.prod.example` para `.env.prod`, defina domínio, usuário, hash bcrypt
da senha e segredos aleatórios. Configure DNS para apontar o domínio ao host e
permita tráfego de entrada nas portas 80 e 443.

```bash
cp .env.prod.example .env.prod
docker compose --env-file .env.prod \
  -f docker-compose.yml -f docker-compose.prod.yml config --quiet
docker compose --env-file .env.prod \
  -f docker-compose.yml -f docker-compose.prod.yml up --build -d
```

O Caddy publica o dashboard em HTTPS, solicita e renova certificados para o
domínio configurado e protege dashboard, API e WebSocket com autenticação básica.
Os serviços de estado continuam na rede privada do Compose. O perfil de produção
não publica o broker, o banco, o Schema Registry nem o object storage no host.

Para executar somente as verificações do pipeline localmente:

```bash
poetry run ruff check src tests stream-processing/spark
poetry run mypy src
poetry run pytest -q
npm --prefix frontend ci
npm --prefix frontend test
npm --prefix frontend run build
docker compose --profile test run --rm spark-tests
```

## 3. Limites que ainda impedem produção irrestrita

- Compose continua em nó único. Kafka e PostgreSQL não têm replicação ou
  failover; os serviços usam recursos locais e volumes no mesmo host.
- Kafka e Schema Registry usam tráfego interno sem autenticação/TLS. A API
  também não possui identidade por usuário nem autorização por ação; a proteção
  básica do Caddy cobre toda a aplicação com uma credencial compartilhada.
- Os segredos do exemplo são marcadores e precisam ser substituídos. Não use os
  padrões do Compose local em qualquer ambiente compartilhado.
- Não existe processo de backup ou restauração automatizado. `docker compose
  down` preserva volumes, mas não é cópia de segurança.
- A retenção Kafka está configurada para sete dias. PostgreSQL e MinIO não têm
  expurgo/lifecycle automático.
- Consumer e Spark não têm readiness próprios. O Compose pode reiniciá-los, mas
  não detecta atraso de consumo ou falta de progresso do Spark.
- O CI valida código e imagens de teste; não publica imagens nem faz deploy.

## 4. Plano de métricas e readiness

Antes de definir limites de alerta, medir uma execução de referência com 20
carros e registrar throughput, memória e atraso. Proposta de etapas:

1. Consumer: expor estado de conexão/partição, timestamp do último evento
   processado, offsets pendentes, tamanho da outbox e total da DLQ. Readiness só
   fica verde após conexão com Kafka e PostgreSQL e uma atribuição de partição.
2. Spark: registrar último progresso da query, offsets de entrada/saída, backlog
   Kafka, duração do micro-lote, falhas e idade do checkpoint. Readiness falha
   se a query estiver inativa ou sem progresso além de um limite configurado.
3. API: separar liveness de readiness; a readiness verifica PostgreSQL e Kafka
   sem bloquear a thread do servidor. Medir conexões WebSocket, erros e latência
   das operações principais.
4. Adicionar Prometheus após definir nomes, unidades, cardinalidade e limites.
   Não usar `race_id`, `car_id` ou `event_id` como labels de métricas; manter esses
   identificadores nos logs estruturados.
5. Definir SLOs e alertas depois de observar a carga local. Valores-alvo ainda
   não foram identificados no repositório.

## 5. Plano de backup, recuperação e retenção

1. Definir RPO e RTO aceitáveis antes de escolher frequência e retenção. Esses
   valores ainda não foram definidos.
2. Criar backup consistente do PostgreSQL com `pg_dump` em formato customizado,
   incluindo globals/roles, e armazená-lo criptografado fora do host.
3. Copiar os dados do MinIO, incluindo `telemetry_raw`, agregados e checkpoints,
   para destino independente. Confirmar checksums e alertar falhas de cópia.
4. Executar restauração periódica em ambiente isolado; confirmar migrações,
   leitura dos Parquet e recuperação de uma projeção antes de considerar o backup
   válido.
5. Documentar a relação entre retenção Kafka de sete dias, arquivo bruto no
   MinIO e retenção operacional no PostgreSQL. Definir lifecycle do MinIO somente
   após confirmar requisitos de análise e eventuais obrigações de conservação.
6. Registrar responsáveis, localização dos segredos e procedimento de rotação;
   nenhum desses valores deve ser armazenado neste documento.

## 6. Próximas entregas

- Criar ambientes e segredos reais no provedor escolhido e validar o certificado
  TLS com um domínio controlado.
- Implementar métricas/readiness conforme as etapas acima e cobri-las com testes.
- Adicionar backup automatizado e um teste documentado de restauração.
- Estabelecer política de retenção para `stream_events`, `stream_receipts`, Kafka
  e os objetos do MinIO.
- Fazer deploy apenas depois de revisar autenticação individual, segurança
  interna do Kafka, disponibilidade e recuperação.
