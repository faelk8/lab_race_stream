# Operação e recuperação do laboratório local

Este documento acompanha o escopo confirmado pelo usuário: laboratório local de
testes, sem deploy público. Prometheus e Grafana são optativos. Backups ficam em
disco local e servem para testar restauração, não para recuperar perda da máquina.

## 1. Estado entregue nesta etapa

- O workflow `.github/workflows/ci.yml` executa Ruff, mypy, pytest, testes e build
  do frontend, transformações Spark com fixtures e validação dos arquivos Compose.
- Os testes Spark validam agregação, deduplicação, seleção da análise online mais
  recente e paridade com `local[1]`, sem Kafka, PostgreSQL, MinIO ou corrida ativa.
- As migrações SQL recebem versão numérica, checksum SHA-256 e instante de
  aplicação em `schema_migrations`. Uma versão existente com outro arquivo ou
  checksum interrompe a inicialização; a correção deve entrar em arquivo novo.
- O perfil `observabilidade` oferece Prometheus e Grafana em `127.0.0.1`; dashboards e datasource são provisionados pelo repositório.
- API expõe `/live`, `/ready` e `/metrics`; consumer e Spark publicam endpoints internos nas portas 9101 e 9102.
- O procedimento de backup local guarda dump PostgreSQL e snapshots frios dos volumes MinIO e Kafka, incluindo schemas e offsets Avro. Recusa corridas ativas e restaura somente em projeto Compose isolado.
- O temporizador systemd opcional executa backup diário local e mantém os três snapshots recentes mais os backups dos últimos sete dias.
- A retenção PostgreSQL simula por padrão e exige `--apply`; limpa somente payloads de eventos antigos de corridas encerradas, sem remover IDs, chaves lógicas, projeções, outbox ou a corrida mais recente.
- Corridas locais podem ser pausadas; o estado do Spark inativo durante ociosidade não é considerado travado.
- Os rascunhos de chuva e eventos são salvos no `localStorage` com versão e
  validação. A configuração persiste no navegador usado; não sincroniza entre
  dispositivos ou navegadores.

## 2. Execução local

Ative a coleta local com os arquivos do Compose e o perfil optativo:

```bash
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml \
  --profile observabilidade up -d
```

Consulte Grafana em `http://localhost:3000` e Prometheus em
`http://localhost:9090`. Veja os procedimentos de backup, restauração e expurgo
no README e em `scripts/backup_local.py`.

## 3. Limites atuais do laboratório

- O backup está no mesmo disco e não protege contra falha/perda da máquina.
- A restauração foi projetada para validar em um projeto Compose isolado; não há
  ambiente separado sempre ativo.
- Kafka retém tópicos por sete dias; IDs de fatos e recibos do consumer são
  mantidos indefinidamente para impedir reaplicação. O conteúdo de eventos
  PostgreSQL pode expirar após 30 dias, sem remover as chaves.
- MinIO mantém objetos e checkpoints indefinidamente. Expurgá-los por idade pode
  invalidar metadados do Spark e comprometer a leitura do arquivo.
- Serviços sem progressos recentes mostram zero/último valor nas métricas; o
  dashboard não promete SLO ou alerta.
- Autenticação compartilhada, domínio e endurecimento para ambiente público não
  são escopo deste laboratório.
