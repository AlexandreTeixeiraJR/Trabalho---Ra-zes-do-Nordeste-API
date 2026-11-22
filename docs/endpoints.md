# Contratos da API

Exemplos abaixo foram obtidos na execução local da coleção. O Swagger contém os tipos, limites e campos obrigatórios. Todos os valores monetários são inteiros em centavos. Tokens foram omitidos.

## POST /auth/login

Permissão — Público.

Parâmetros — 

Request
```json
{
  "email": "cliente@raizes.local",
  "senha": "Cliente@123"
}
```

Response HTTP 200
```json
{
  "accessToken": "TOKEN_JWT_OMITIDO",
  "tokenType": "Bearer",
  "expiresIn": 3600,
  "user": {
    "id": 1,
    "nome": "Cliente exemplo",
    "perfil": "CLIENTE"
  }
}
```

## POST /usuarios

Permissão — Público.

Parâmetros — 

Request
```json
{
  "nome": "Cliente da coleção",
  "email": "colecao+1794234072319@raizes.local",
  "senha": "Colecao@123"
}
```

Response HTTP 201
```json
{
  "id": 6,
  "nome": "Cliente da coleção",
  "perfil": "CLIENTE"
}
```

## GET /unidades

Permissão — Público.

Parâmetros — page (query), limit (query)

Request
```json
{}
```

Response HTTP 200
```json
{
  "items": [
    {
      "id": 1,
      "nome": "Recife Centro",
      "regiao": "Nordeste",
      "ativa": 1
    },
    {
      "id": 2,
      "nome": "Caruaru",
      "regiao": "Nordeste",
      "ativa": 1
    }
  ],
  "page": 1,
  "limit": 10,
  "total": 2
}
```

## GET /produtos

Permissão — Público.

Parâmetros — page (query), limit (query)

Request
```json
{}
```

Response HTTP 200
```json
{
  "items": [
    {
      "id": 1,
      "nome": "Cuscuz recheado"
    },
    {
      "id": 2,
      "nome": "Tapioca de queijo"
    }
  ],
  "page": 1,
  "limit": 10,
  "total": 2
}
```

## GET /unidades/{unidade_id}/cardapio

Permissão — Público.

Parâmetros — unidade_id (path), page (query), limit (query)

Request
```json
{}
```

Response HTTP 200
```json
{
  "items": [
    {
      "produtoId": 1,
      "nome": "Cuscuz recheado",
      "precoCentavos": 1200,
      "saldo": 100
    },
    {
      "produtoId": 2,
      "nome": "Tapioca de queijo",
      "precoCentavos": 1000,
      "saldo": 80
    }
  ],
  "page": 1,
  "limit": 10,
  "total": 2
}
```

## POST /unidades

Permissão — JWT, ADMIN.

Parâmetros — 

Request
```json
{
  "nome": "Unidade da coleção",
  "regiao": "Nordeste",
  "ativa": true
}
```

Response HTTP 201
```json
{
  "id": 3,
  "nome": "Unidade da coleção",
  "regiao": "Nordeste",
  "ativa": 1
}
```

## PUT /unidades/{unidade_id}

Permissão — JWT, ADMIN.

Parâmetros — unidade_id (path)

Request
```json
{
  "nome": "Unidade teste atualizada",
  "regiao": "Nordeste",
  "ativa": true
}
```

Response HTTP 200
```json
{
  "id": 3,
  "nome": "Unidade teste atualizada",
  "regiao": "Nordeste",
  "ativa": 1
}
```

## POST /produtos

Permissão — JWT, ADMIN.

Parâmetros — 

Request
```json
{
  "nome": "Bolo da coleção"
}
```

Response HTTP 201
```json
{
  "id": 3,
  "nome": "Bolo da coleção"
}
```

## PUT /produtos/{produto_id}

Permissão — JWT, ADMIN.

Parâmetros — produto_id (path)

Request
```json
{
  "nome": "Bolo de macaxeira"
}
```

Response HTTP 200
```json
{
  "id": 3,
  "nome": "Bolo de macaxeira"
}
```

## PUT /unidades/{unidade_id}/cardapio/{produto_id}

Permissão — JWT, ADMIN ou GERENTE da unidade. ADMIN acessa todas as unidades.

Parâmetros — unidade_id (path), produto_id (path)

Request
```json
{
  "precoCentavos": 800,
  "disponivel": true
}
```

Response HTTP 200
```json
{
  "unidadeId": 1,
  "produtoId": 3,
  "precoCentavos": 800,
  "disponivel": true
}
```

## POST /unidades/{unidade_id}/estoque/{produto_id}/movimentos

Permissão — JWT, ADMIN ou GERENTE da unidade. ADMIN acessa todas as unidades.

Parâmetros — unidade_id (path), produto_id (path)

Request
```json
{
  "quantidade": 10,
  "motivo": "Reposição de demonstração"
}
```

Response HTTP 201
```json
{
  "unidadeId": 1,
  "produtoId": 3,
  "saldo": 10
}
```

## GET /unidades/{unidade_id}/estoque

Permissão — JWT, ADMIN ou GERENTE da unidade. ADMIN acessa todas as unidades.

Parâmetros — unidade_id (path), page (query), limit (query)

Request
```json
{}
```

Response HTTP 200
```json
{
  "items": [
    {
      "produtoId": 1,
      "saldo": 100
    },
    {
      "produtoId": 2,
      "saldo": 80
    },
    {
      "produtoId": 3,
      "saldo": 10
    }
  ],
  "page": 1,
  "limit": 10,
  "total": 3
}
```

## PUT /fidelidade/consentimento

Permissão — JWT, CLIENTE, somente os próprios dados.

Parâmetros — 

Request
```json
{
  "aceito": true
}
```

Response HTTP 200
```json
{
  "finalidade": "FIDELIDADE",
  "aceito": true,
  "versao": "1.0"
}
```

## POST /pedidos

Permissão — JWT, CLIENTE proprietário, ATENDENTE ou GERENTE da unidade, ou ADMIN.

Parâmetros — Idempotency-Key (header)

Request
```json
{
  "unidadeId": 1,
  "canalPedido": "APP",
  "itens": [
    {
      "produtoId": 1,
      "quantidade": 1
    }
  ]
}
```

Response HTTP 201
```json
{
  "pedidoId": 1,
  "clienteId": 1,
  "unidadeId": 1,
  "canalPedido": "APP",
  "status": "AGUARDANDO_PAGAMENTO",
  "subtotalCentavos": 1200,
  "descontoCentavos": 0,
  "totalCentavos": 1200,
  "pontosResgate": 0,
  "itens": [
    {
      "produtoId": 1,
      "quantidade": 1,
      "precoUnitarioCentavos": 1200
    }
  ],
  "criadoEm": "2026-11-09T14:21:14.258557+00:00"
}
```

## GET /pedidos/{pedido_id}

Permissão — JWT. CLIENTE vê seus pedidos e cancela pendentes. Equipe opera na própria unidade. COZINHA altera para EM_PREPARO ou PRONTO. ADMIN acessa todas.

Parâmetros — pedido_id (path)

Request
```json
{}
```

Response HTTP 200
```json
{
  "pedidoId": 1,
  "clienteId": 1,
  "unidadeId": 1,
  "canalPedido": "APP",
  "status": "AGUARDANDO_PAGAMENTO",
  "subtotalCentavos": 1200,
  "descontoCentavos": 0,
  "totalCentavos": 1200,
  "pontosResgate": 0,
  "itens": [
    {
      "produtoId": 1,
      "quantidade": 1,
      "precoUnitarioCentavos": 1200
    }
  ],
  "criadoEm": "2026-11-09T14:21:14.258557+00:00"
}
```

## GET /pedidos

Permissão — JWT. CLIENTE vê seus pedidos e cancela pendentes. Equipe opera na própria unidade. COZINHA altera para EM_PREPARO ou PRONTO. ADMIN acessa todas.

Parâmetros — page (query), limit (query), canalPedido (query), status (query)

Request
```json
{}
```

Response HTTP 200
```json
{
  "items": [
    {
      "pedidoId": 1,
      "clienteId": 1,
      "unidadeId": 1,
      "canalPedido": "APP",
      "status": "AGUARDANDO_PAGAMENTO",
      "subtotalCentavos": 1200,
      "descontoCentavos": 0,
      "totalCentavos": 1200,
      "pontosResgate": 0,
      "itens": [
        {
          "produtoId": 1,
          "quantidade": 1,
          "precoUnitarioCentavos": 1200
        }
      ],
      "criadoEm": "2026-11-09T14:21:14.258557+00:00"
    }
  ],
  "page": 1,
  "limit": 10,
  "total": 1
}
```

## POST /pedidos/{pedido_id}/pagamentos

Permissão — JWT, CLIENTE proprietário, ATENDENTE ou GERENTE da unidade, ou ADMIN.

Parâmetros — pedido_id (path), Idempotency-Key (header)

Request
```json
{
  "resultado": "RECUSADO"
}
```

Response HTTP 200
```json
{
  "pagamentoId": 1,
  "statusPagamento": "RECUSADO",
  "referencia": "mock-3be1a86720755e6f",
  "valorCentavos": 1200,
  "pedido": {
    "pedidoId": 1,
    "clienteId": 1,
    "unidadeId": 1,
    "canalPedido": "APP",
    "status": "AGUARDANDO_PAGAMENTO",
    "subtotalCentavos": 1200,
    "descontoCentavos": 0,
    "totalCentavos": 1200,
    "pontosResgate": 0,
    "itens": [
      {
        "produtoId": 1,
        "quantidade": 1,
        "precoUnitarioCentavos": 1200
      }
    ],
    "criadoEm": "2026-11-09T14:21:14.258557+00:00"
  }
}
```

## PATCH /pedidos/{pedido_id}/status

Permissão — JWT. CLIENTE vê seus pedidos e cancela pendentes. Equipe opera na própria unidade. COZINHA altera para EM_PREPARO ou PRONTO. ADMIN acessa todas.

Parâmetros — pedido_id (path)

Request
```json
{
  "status": "EM_PREPARO"
}
```

Response HTTP 200
```json
{
  "pedidoId": 1,
  "clienteId": 1,
  "unidadeId": 1,
  "canalPedido": "APP",
  "status": "EM_PREPARO",
  "subtotalCentavos": 1200,
  "descontoCentavos": 0,
  "totalCentavos": 1200,
  "pontosResgate": 0,
  "itens": [
    {
      "produtoId": 1,
      "quantidade": 1,
      "precoUnitarioCentavos": 1200
    }
  ],
  "criadoEm": "2026-11-09T14:21:14.258557+00:00"
}
```

## GET /fidelidade

Permissão — JWT, CLIENTE, somente os próprios dados.

Parâmetros — page (query), limit (query)

Request
```json
{}
```

Response HTTP 200
```json
{
  "saldo": 12,
  "consentimento": true,
  "historico": {
    "items": [
      {
        "pedidoId": 1,
        "tipo": "CREDITO",
        "quantidade": 12,
        "criadoEm": "2026-11-09T14:21:15.246430+00:00"
      }
    ],
    "page": 1,
    "limit": 10,
    "total": 1
  }
}
```

## GET /auditoria

Permissão — JWT, ADMIN.

Parâmetros — page (query), limit (query)

Request
```json
{}
```

Response HTTP 200
```json
{
  "items": [
    {
      "id": 22,
      "usuario_id": 2,
      "acao": "CONSULTAR_AUDITORIA",
      "recurso": "auditoria",
      "criado_em": "2026-11-09T14:21:15.433424+00:00"
    },
    {
      "id": 21,
      "usuario_id": 1,
      "acao": "CONSULTAR_FIDELIDADE",
      "recurso": "1",
      "criado_em": "2026-11-09T14:21:15.339024+00:00"
    },
    {
      "id": 20,
      "usuario_id": 4,
      "acao": "STATUS_ENTREGUE",
      "recurso": "1",
      "criado_em": "2026-11-09T14:21:15.246482+00:00"
    },
    {
      "id": 19,
      "usuario_id": 3,
      "acao": "STATUS_PRONTO",
      "recurso": "1",
      "criado_em": "2026-11-09T14:21:15.152478+00:00"
    },
    {
      "id": 18,
      "usuario_id": 3,
      "acao": "STATUS_EM_PREPARO",
      "recurso": "1",
      "criado_em": "2026-11-09T14:21:15.057403+00:00"
    },
    {
      "id": 17,
      "usuario_id": 1,
      "acao": "PAGAMENTO_APROVADO",
      "recurso": "1",
      "criado_em": "2026-11-09T14:21:14.870348+00:00"
    },
    {
      "id": 16,
      "usuario_id": 1,
      "acao": "PAGAMENTO_TIMEOUT",
      "recurso": "1",
      "criado_em": "2026-11-09T14:21:14.777156+00:00"
    },
    {
      "id": 15,
      "usuario_id": 1,
      "acao": "PAGAMENTO_RECUSADO",
      "recurso": "1",
      "criado_em": "2026-11-09T14:21:14.635847+00:00"
    },
    {
      "id": 14,
      "usuario_id": 1,
      "acao": "CRIAR_PEDIDO",
      "recurso": "1",
      "criado_em": "2026-11-09T14:21:14.258883+00:00"
    },
    {
      "id": 13,
      "usuario_id": 1,
      "acao": "MOVIMENTAR_ESTOQUE",
      "recurso": "1/1",
      "criado_em": "2026-11-09T14:21:14.258861+00:00"
    },
    {
      "id": 12,
      "usuario_id": 1,
      "acao": "CONSENTIMENTO_FIDELIDADE",
      "recurso": "1",
      "criado_em": "2026-11-09T14:21:14.179216+00:00"
    },
    {
      "id": 11,
      "usuario_id": 4,
      "acao": "MOVIMENTAR_ESTOQUE",
      "recurso": "1/3",
      "criado_em": "2026-11-09T14:21:13.991704+00:00"
    },
    {
      "id": 10,
      "usuario_id": 2,
      "acao": "ALTERAR_CARDAPIO",
      "recurso": "1/3",
      "criado_em": "2026-11-09T14:21:13.899507+00:00"
    },
    {
      "id": 9,
      "usuario_id": 2,
      "acao": "EDITAR_PRODUTO",
      "recurso": "3",
      "criado_em": "2026-11-09T14:21:13.805686+00:00"
    },
    {
      "id": 8,
      "usuario_id": 2,
      "acao": "CRIAR_PRODUTO",
      "recurso": "3",
      "criado_em": "2026-11-09T14:21:13.710445+00:00"
    },
    {
      "id": 7,
      "usuario_id": 2,
      "acao": "EDITAR_UNIDADE",
      "recurso": "3",
      "criado_em": "2026-11-09T14:21:13.617467+00:00"
    },
    {
      "id": 6,
      "usuario_id": 2,
      "acao": "CRIAR_UNIDADE",
      "recurso": "3",
      "criado_em": "2026-11-09T14:21:13.507555+00:00"
    },
    {
      "id": 5,
      "usuario_id": 6,
      "acao": "CADASTRAR_USUARIO",
      "recurso": "6",
      "criado_em": "2026-11-09T14:21:13.138896+00:00"
    },
    {
      "id": 4,
      "usuario_id": 4,
      "acao": "LOGIN",
      "recurso": "4",
      "criado_em": "2026-11-09T14:21:12.981232+00:00"
    },
    {
      "id": 3,
      "usuario_id": 3,
      "acao": "LOGIN",
      "recurso": "3",
      "criado_em": "2026-11-09T14:21:12.807801+00:00"
    },
    {
      "id": 2,
      "usuario_id": 2,
      "acao": "LOGIN",
      "recurso": "2",
      "criado_em": "2026-11-09T14:21:12.637414+00:00"
    },
    {
      "id": 1,
      "usuario_id": 1,
      "acao": "LOGIN",
      "recurso": "1",
      "criado_em": "2026-11-09T14:21:12.461215+00:00"
    }
  ],
  "page": 1,
  "limit": 100,
  "total": 22
}
```

## GET /relatorios/vendas

Permissão — JWT, ADMIN ou GERENTE da unidade. ADMIN acessa todas as unidades.

Parâmetros — 

Request
```json
{}
```

Response HTTP 200
```json
{
  "items": [
    {
      "unidadeId": 1,
      "regiao": "Nordeste",
      "canalPedido": "APP",
      "pedidos": 1,
      "receitaCentavos": 1200
    }
  ]
}
```

## GET /health

Permissão — Público.

Parâmetros — 

Request
```json
{}
```

Response HTTP 200
```json
{
  "status": "ok"
}
```
