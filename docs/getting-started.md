# Instalação e primeiros passos

## Pré-requisitos

Para executar a stack integral:

- Docker Engine;
- Docker Compose v2;
- Git;
- espaço para imagens, volumes Kafka/PostgreSQL/MinIO e dependências Maven do
  Spark;
- portas `5173`, `8000`, `8080`, `8081` e `9092` livres; `19000` e `19001`
  disponíveis no loopback.

Para desenvolvimento fora dos containers também são necessários Python 3.12+,
Node.js compatível com o lockfile e npm.

## Configuração inicial

Na raiz do projeto:

```bash
cp .env.example .env
docker compose config --quiet
```

Os valores padrão são adequados apenas ao laboratório local. Consulte
[Configuração](configuration.md) antes de trocar portas, credenciais ou escala.

## Executar com Docker

```bash
docker compose up --build -d
docker compose ps
```

O primeiro build do MinIO compila os binários fixados no Dockerfile. O primeiro
início do Spark também baixa os pacotes Kafka, Avro e S3A indicados no Compose.

Depois que API e dependências estiverem saudáveis, use o dashboard para
configurar e iniciar a corrida. Os acessos locais são:

| Recurso | Endereço |
| --- | --- |
| Dashboard | `http://localhost:5173` |
| API/OpenAPI | `http://localhost:8000/docs` |
| Redpanda Console | `http://localhost:8080` |
| Schema Registry | `http://localhost:8081` |
| MinIO Console | `http://localhost:19001` |
| MinIO S3 | `http://localhost:19000` |

Para acompanhar os processos principais:

```bash
docker compose logs -f simulator consumer api spark-archive
```

## Finalizar a corrida e os serviços

Use **Parar corrida** no dashboard para persistir a classificação parcial. Para
encerrar a infraestrutura sem apagar volumes:

```bash
docker compose down
```

`docker compose down -v` também remove os dados locais de Kafka, PostgreSQL,
MinIO e Spark. Use esse comando somente quando a intenção for recriar todo o
laboratório.

## Desenvolvimento local

Instale o pacote Python e as ferramentas de desenvolvimento:

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e '.[dev]'
```

Instale o frontend:

```bash
cd frontend
npm ci
cd ..
```

Os entrypoints Python podem ser iniciados diretamente:

```bash
.venv/bin/python -m racestream.interfaces.producer
.venv/bin/python -m racestream.interfaces.stream_processor
.venv/bin/uvicorn racestream.interfaces.api:app --host 0.0.0.0 --port 8000
```

Esses processos exigem PostgreSQL, Kafka e Schema Registry acessíveis nas URLs
das variáveis de ambiente. O Compose não publica a porta do PostgreSQL no host.
Assim, a execução integral com processos Python no host não está preparada como
um fluxo pronto no repositório.

> Não identificado no repositório.

O modo comprovado para a aplicação completa é Docker Compose. A execução local
sem infraestrutura é adequada aos testes unitários.

Para desenvolver apenas o frontend com uma API acessível em `localhost:8000`:

```bash
cd frontend
npm run dev
```

## Verificação rápida

```bash
curl -fsS http://localhost:8000/health
curl -fsS http://localhost:8000/api/streaming
docker compose ps
```

A primeira resposta deve ser `{"status":"ok"}`. O segundo endpoint deve listar
os dez tópicos curtos.

