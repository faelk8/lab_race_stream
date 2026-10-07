# Plano de execução: realismo de corrida

Data: 07/10/2026. Estado: concluído.

## 1. Objetivo

Completar os incrementos de realismo que permanecem abertos: aproximação física
da vaga nos boxes, neutralização com bandeiras e penalidades aplicáveis durante a
corrida.

## 2. Estado inicial antes da implementação

- o pit lane respeita 60 km/h, mas a velocidade é zerada ao cruzar a vaga;
- chuva, furos e colisões configuráveis já existem;
- antes deste plano, não havia estado de bandeira, neutralização nem penalidade
  no domínio;
- eventos, contratos e interface precisam evoluir de forma aditiva.

## 3. Entregas incrementais

### 3.1 Frenagem até a vaga

Calcular a curva de frenagem pela distância restante no trajeto do pit lane,
reduzindo continuamente a velocidade antes do início do serviço. Validar com um
trecho curto de boxes e preservar o limite de 60 km/h.

### 3.2 Bandeiras e neutralização

Definir estados explícitos de pista, duração e efeitos em velocidade e
ultrapassagem. Publicar o estado nos contratos e apresentá-lo no painel.

### 3.3 Penalidades

Definir tipos suportados, gatilho, cumprimento, efeito na classificação e eventos
auditáveis. A primeira versão deve permanecer determinística e configurável.

## 4. Validação

- testes unitários curtos e determinísticos por regra;
- roundtrip dos contratos Avro alterados;
- Ruff e mypy para Python;
- testes, typecheck e build para o frontend quando afetado;
- validação Compose e logs após reconstruir serviços alterados.

## 5. Progresso

- [x] Identificar as lacunas no domínio e nos planos existentes.
- [x] Implementar e validar frenagem contínua até a vaga.
- [x] Implementar e validar bandeiras e neutralização.
- [x] Implementar e validar penalidades.
- [x] Atualizar documentação de retomada e concluir o plano.

## 6. Evidência da primeira entrega

O teste curto de pit lane comprova limite de 60 km/h, três amostras finais com
velocidade estritamente decrescente, chegada à vaga dentro de dois subpassos da
capacidade de frenagem, serviço parado e perda de posição. A prova completa não
foi executada para este incremento.

## 7. Evidência da segunda entrega

Uma colisão determinística com três carros comprovou abandono dos dois
envolvidos, início e fim do safety car, redução do sobrevivente até 120 km/h e
retorno à bandeira verde. Uma fixture de cronometragem comprovou que qualquer
checkpoint neutralizado invalida a volta concluída. O roundtrip Avro cobre os
campos aditivos de pista, passagem e volta.

## 8. Evidência da terceira entrega

Uma fixture com dois carros aplicou cinco segundos ao vencedor físico e comprovou
a inversão da classificação diante de um rival que chegou três segundos depois.
O teste também validou o evento `incident`, o roundtrip Avro e a exposição da
penalidade na telemetria. A API aceita a configuração e rejeita duração zero.
