# Plano de testes da coleção

Execute as pastas em ordem, após aplicar o seed. Cada linha corresponde a uma requisição com asserção de status. As regras do fluxo principal têm asserções de conteúdo. Os testes de regressão em `tests/test_api.py` verificam concorrência, rollback e isolamento.

| ID | Cenário e evidência na coleção | Método e endpoint | Entrada | Resultado |
|---|---|---|---|---|
| T01 | Login Cliente | POST /auth/login | {   "email": "cliente@raizes.local",   "senha": "Cliente@123" } | HTTP 200 |
| T02 | Login Admin | POST /auth/login | {   "email": "admin@raizes.local",   "senha": "Admin@123" } | HTTP 200 |
| T03 | Login Cozinha | POST /auth/login | {   "email": "cozinha@raizes.local",   "senha": "Cozinha@123" } | HTTP 200 |
| T04 | Login Gerente | POST /auth/login | {   "email": "gerente@raizes.local",   "senha": "Gerente@123" } | HTTP 200 |
| T05 | Cadastro público | POST /usuarios | {   "nome": "Cliente da coleção",   "email": "colecao+{{execucao}}@raizes.local",   "senha": "Colecao@123" } | HTTP 201 |
| T06 | Consultar unidades | GET /unidades?page=1&limit=10 | Sem body | HTTP 200 |
| T07 | Consultar produtos | GET /produtos?page=1&limit=10 | Sem body | HTTP 200 |
| T08 | Consultar cardápio local | GET /unidades/1/cardapio | Sem body | HTTP 200 |
| T09 | Cadastrar unidade | POST /unidades | {   "nome": "Unidade da coleção",   "regiao": "Nordeste",   "ativa": true } | HTTP 201 |
| T10 | Editar unidade | PUT /unidades/{{unidadeNova}} | {   "nome": "Unidade teste atualizada",   "regiao": "Nordeste",   "ativa": true } | HTTP 200 |
| T11 | Cadastrar produto | POST /produtos | {   "nome": "Bolo da coleção" } | HTTP 201 |
| T12 | Editar produto | PUT /produtos/{{produtoNovo}} | {   "nome": "Bolo de macaxeira" } | HTTP 200 |
| T13 | Definir preço local | PUT /unidades/1/cardapio/{{produtoNovo}} | {   "precoCentavos": 800,   "disponivel": true } | HTTP 200 |
| T14 | Entrada com motivo | POST /unidades/1/estoque/{{produtoNovo}}/movimentos | {   "quantidade": 10,   "motivo": "Reposição de demonstração" } | HTTP 201 |
| T15 | Consultar saldo | GET /unidades/1/estoque | Sem body | HTTP 200 |
| T16 | Aceitar fidelidade | PUT /fidelidade/consentimento | {   "aceito": true } | HTTP 200 |
| T17 | Criar pedido APP | POST /pedidos | {   "unidadeId": 1,   "canalPedido": "APP",   "itens": [     {       "produtoId": 1,       "quantidade": 1     }   ] } | HTTP 201 |
| T18 | Repetir criação idempotente | POST /pedidos | {   "unidadeId": 1,   "canalPedido": "APP",   "itens": [     {       "produtoId": 1,       "quantidade": 1     }   ] } | HTTP 201 |
| T19 | Consultar pedido | GET /pedidos/{{pedidoId}} | Sem body | HTTP 200 |
| T20 | Filtrar por canal | GET /pedidos?canalPedido=APP&status=AGUARDANDO_PAGAMENTO | Sem body | HTTP 200 |
| T21 | Recusar pagamento | POST /pedidos/{{pedidoId}}/pagamentos | {   "resultado": "RECUSADO" } | HTTP 200 |
| T22 | Simular indisponibilidade | POST /pedidos/{{pedidoId}}/pagamentos | {   "resultado": "TIMEOUT" } | HTTP 503 |
| T23 | Aprovar pagamento | POST /pedidos/{{pedidoId}}/pagamentos | {   "resultado": "APROVADO" } | HTTP 200 |
| T24 | Repetir pagamento aprovado | POST /pedidos/{{pedidoId}}/pagamentos | {   "resultado": "APROVADO" } | HTTP 200 |
| T25 | Iniciar preparo | PATCH /pedidos/{{pedidoId}}/status | {   "status": "EM_PREPARO" } | HTTP 200 |
| T26 | Marcar pronto | PATCH /pedidos/{{pedidoId}}/status | {   "status": "PRONTO" } | HTTP 200 |
| T27 | Confirmar entrega | PATCH /pedidos/{{pedidoId}}/status | {   "status": "ENTREGUE" } | HTTP 200 |
| T28 | Consultar pontos | GET /fidelidade | Sem body | HTTP 200 |
| T29 | Auditar operação sensível | GET /auditoria?limit=100 | Sem body | HTTP 200 |
| T30 | Vendas consolidadas | GET /relatorios/vendas | Sem body | HTTP 200 |
| T31 | Acesso sem token | GET /pedidos | Sem body | HTTP 401 |
| T32 | Perfil sem permissão | POST /produtos | {   "nome": "Produto bloqueado" } | HTTP 403 |
| T33 | Canal obrigatório ausente | POST /pedidos | {   "unidadeId": 1,   "itens": [     {       "produtoId": 1,       "quantidade": 1     }   ] } | HTTP 422 |
| T34 | Canal inválido | POST /pedidos | {   "unidadeId": 1,   "canalPedido": "EMAIL",   "itens": [     {       "produtoId": 1,       "quantidade": 1     }   ] } | HTTP 422 |
| T35 | Quantidade negativa | POST /pedidos | {   "unidadeId": 1,   "canalPedido": "APP",   "itens": [     {       "produtoId": 1,       "quantidade": -1     }   ] } | HTTP 422 |
| T36 | Produto inexistente | POST /pedidos | {   "unidadeId": 1,   "canalPedido": "APP",   "itens": [     {       "produtoId": 999999,       "quantidade": 1     }   ] } | HTTP 404 |
| T37 | Unidade inexistente | POST /pedidos | {   "unidadeId": 999999,   "canalPedido": "APP",   "itens": [     {       "produtoId": 1,       "quantidade": 1     }   ] } | HTTP 404 |
| T38 | Estoque insuficiente | POST /pedidos | {   "unidadeId": 1,   "canalPedido": "APP",   "itens": [     {       "produtoId": 2,       "quantidade": 100     }   ] } | HTTP 409 |
| T39 | Transição inválida | PATCH /pedidos/{{pedidoId}}/status | {   "status": "RECEBIDO" } | HTTP 409 |
| T40 | Isolamento de unidade | GET /unidades/2/estoque | Sem body | HTTP 403 |
| T41 | Criar pedido TOTEM | POST /pedidos | {   "unidadeId": 1,   "canalPedido": "TOTEM",   "itens": [     {       "produtoId": 1,       "quantidade": 1     }   ] } | HTTP 201 |
| T42 | Cancelar pendente | PATCH /pedidos/{{pedidoCancelar}}/status | {   "status": "CANCELADO" } | HTTP 200 |
| T43 | Revogar consentimento | PUT /fidelidade/consentimento | {   "aceito": false } | HTTP 200 |
| T44 | Verificar API e banco | GET /health | Sem body | HTTP 200 |

Pré-condições gerais. O banco contém o seed e os cenários anteriores foram executados. T01 a T04 guardam os tokens. T17 guarda pedidoId. T41 guarda pedidoCancelar. Os testes negativos enviam entradas inválidas deliberadamente.

Critérios de conteúdo. O pedido APP tem total de 1.200 centavos. Recusa mantém AGUARDANDO_PAGAMENTO, aprovação muda para RECEBIDO, entrega gera pelo menos 12 pontos e a auditoria contém STATUS_ENTREGUE.

Os cenários representam uma validação local. Teste de carga, disponibilidade e avaliação jurídica da política de privacidade ficam como etapas futuras.