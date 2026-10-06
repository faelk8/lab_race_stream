# Retomada do RaceStream

Atualizado em 06/10/2026. Este arquivo é o ponto de entrada após pausa por crédito,
fechamento do chat ou troca de modelo. O repositório e o Jota guardam o estado;
não é necessário copiar toda a conversa.

## Trabalho atual

**Concluído:** limite de 60 km/h desde a entrada até a saída dos boxes,
serviço parado com duração física e classificação recalculada durante os boxes.
A terceira parada de C continua apenas abastecimento, com reserva de uma volta.

Validação: 152 testes Python (incluindo Kafka), Ruff, mypy e recuperação
PostgreSQL aprovados. Um trecho de dois carros comprovou limite, duração,
troca de pneus e perda de posição; não foi iniciada nova corrida pelo painel.
API, simulador e consumidor foram reconstruídos; dependências estão saudáveis.

Próxima retomada: consultar o plano antes de escolher outra melhoria. Ainda cabe
refinar a desaceleração até a vaga de serviço, hoje representada por parada
discreta; esse instante não é apresentado como uma medida válida de impacto.
Há uma alteração preexistente em `.env.example`; não sobrescrever nem incluir
em commit sem verificar sua origem.

Para economizar créditos no Codex, considerar `gpt-6-luna` no seletor de modelos,
se disponível na conta, em tarefas pequenas com critérios claros e testes.
A [documentação oficial](https://learn.chatgpt.com/docs/models) recomenda Luna
para tarefas delimitadas. O modelo deste chat não foi trocado. Se o pedido for
sobre o Jota local, consultar os modelos instalados antes de alterar sua configuração.

## Onde consultar

- [Plano e histórico de melhorias](execplan-refinamento-corrida.md).
- [Decisões técnicas e limites](adr/0010-cronometragem-e-projecoes-de-corrida.md).
- [Contexto compartilhado com Jota](jota-contexto.md).
- [Evidências anteriores](validation/refinamento-v4.json).
- `git log --oneline -12`: commits efetivamente registrados.
- `git status --short`: alterações ainda não commitadas.

## Procedimento de retomada

Leia `AGENTS.md`, este arquivo e a última seção do plano. Consulte as preferências
no Jota conforme `AGENTS.md`. Confirme arquivos e serviços atuais antes de seguir;
um teste aprovado anteriormente não comprova uma alteração posterior.

Execute somente os testes pertinentes. Prefira fixtures de trechos curtos; não
rode corridas completas repetidamente. Faça um commit para cada melhoria validada.
Não declare push ou troca de modelo sem confirmação efetiva dessas operações.

Ao terminar uma etapa, atualize trabalho atual, evidências e pendências aqui e no
plano, então execute `systemctl --user start jota-racestream-sync.service`.
O timer do Jota também indexa os arquivos a cada dois minutos com a sessão ativa.
A gravação em arquivos preserva o trabalho mesmo se o Jota estiver indisponível.
