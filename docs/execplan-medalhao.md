# ExecPlan — Camadas medalhão por corrida

## 1. Objetivo

Materializar no MinIO os eventos já arquivados pelo Spark em bronze, dados
normalizados em prata e uma classificação ouro para o dashboard. Ao detectar o
fim da corrida, a tela apresenta essa classificação em uma janela de resultados.

## 2. Escopo

Inclui somente execução local via Docker Compose, transformações batch Spark,
leitura do resultado ouro pela API e modal React. O workflow GitHub Actions fica
local e ignorado pelo Git; não haverá publicação ou deploy.

## 3. Estado atual

O serviço `spark-archive` grava envelopes Avro em `telemetry_raw` no MinIO. Há
transformações batch para voltas e paridade, porém ainda não há camadas por
corrida nem consumo dessas tabelas no dashboard.

## 4. Arquitetura alvo

```mermaid
flowchart LR
    K[Kafka: tópicos da corrida] --> S[Spark Structured Streaming]
    S --> R[(MinIO: telemetry_raw)]
    R --> B[Bronze: envelopes da corrida]
    B --> P[Prata: voltas, pit stops e estado final]
    P --> O[Ouro: classificação e métricas]
    O --> A[API FastAPI]
    A --> F[Modal de resultados React]
```

## 5. Contratos

- Prefixo por corrida: `corridas/{race_id}/bronze`, `prata` e `ouro`.
- Ouro: posição, carro, piloto, país, melhores/piores/médias de voltas, pit stops
  concluídos e medalha do pódio.
- API: `GET /api/races/{race_id}/medalhao`, com `404` enquanto o resultado não
  estiver materializado.
- O término é identificado pelo evento `control` com `status=finished`.

## 6. Etapas

- [x] Implementar a transformação idempotente dos envelopes arquivados em
  camadas por corrida.
- [x] Expor a classificação ouro pela API e mostrar a janela após o término.
- [x] Testar agregações, contagem de pit stops e leitura da API.
- [x] Atualizar instruções do laboratório e ignorar o workflow GitHub local.
- [x] Executar as fixtures Spark e testar leitura/escrita real no MinIO com dados
  de uma corrida já arquivada.

## 7. Estratégia de testes

Fixtures Spark sem dependências externas validam deduplicação, voltas válidas,
paradas concluídas, pódio e ordenação. Testes FastAPI usam um adaptador falso;
testes frontend validam formatação e apresentação da classificação.

## 8. Riscos e decisões

- O histórico bruto continua em `telemetry_raw`; bronze é uma cópia particionada
  por corrida e mantém os envelopes originais para consulta independente.
- A transformação roda no processo Spark de arquivamento, sem um segundo driver
  Spark residente no laboratório.
- A janela usa um fundo externo com 50% de opacidade e painel interno opaco para
  conservar o contraste do texto.
- Resultado ouro ausente após falha de transformação é reprocessado na próxima
  varredura; cada camada da corrida usa gravação `overwrite` idempotente.
