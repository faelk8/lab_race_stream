# Plano de execução: links de acesso e Redpanda Console

## Objetivo e escopo
Adicionar ao README links clicáveis para corrida, Kafka, API e Schema Registry.
Disponibilizar o Redpanda Console no Compose para que o link do Kafka funcione.

## Estado atual e arquitetura
O painel usa a porta 5173, API 8000 e Schema Registry 8081. Não existia Console.
Adicionar somente um serviço Console conectado a `kafka:29092` e ao Registry.

## Contratos e decisões
Console v3.12.0, porta local 8080; os nomes dos tópicos seguem o catálogo atual
descrito no dicionário de dados. Configuração conforme documentação referenciada
no README.

## Etapas e validação
- [x] Conferir portas e documentar links.
- [x] Adicionar serviço Console ao Compose.
- [x] Executar `docker compose config --quiet` e iniciar somente o Console.
- [x] Verificar resposta HTTP, tópicos e acesso ao painel.

## Testes e riscos
Verificar HTTP e integração com Kafka real; não executar novas simulações.
A porta 8080 estava disponível na conferência local. Reversão: remover o serviço
Console e os links correspondentes, preservando os volumes e dados existentes.

## Evidências
Compose válido. Console, painel da corrida, documentação da API e Schema Registry
responderam HTTP 200. A API do Console respondeu HTTP 200 e listou
os tópicos históricos disponíveis na ocasião. A nomenclatura foi atualizada
depois pela ADR 0013.
