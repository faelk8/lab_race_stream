# Pendências do laboratório local

Escopo confirmado em 08/10/2026: projeto de testes executado localmente.

- [x] Implementar métricas e liveness/readiness para API, consumer e Spark, com testes automatizados.
- [x] Disponibilizar visualização local das métricas com perfil opcional de observabilidade.
- [x] Automatizar backup local de PostgreSQL, MinIO e schemas Avro e validar restauração em ambiente isolado.
- [x] Definir e implementar retenção adequada ao laboratório, com simulação antes de remover dados e proteção dos checkpoints e da deduplicação.
- [x] Atualizar documentação e CI com os comandos e testes operacionais.

Domínio, deploy público, autenticação de produção, backup fora do host e alta
disponibilidade ficam fora do escopo atual. A máquina única é adequada ao objetivo
de laboratório, mas sua perda também implica perder os backups locais. As tarefas
acima foram validadas localmente; deploy público permanece fora do escopo.
