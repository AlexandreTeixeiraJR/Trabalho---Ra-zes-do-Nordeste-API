"""Gera a coleção e o plano de testes a partir dos mesmos cenários."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
cenarios = []


def adicionar(
    pasta,
    nome,
    metodo,
    rota,
    esperado,
    corpo=None,
    token="tokenCliente",
    verificar=None,
    salvar=None,
    chave=None,
    pre="Seed aplicado e passos anteriores executados.",
):
    numero = f"T{len(cenarios) + 1:02}"
    testes = [
        f'pm.test("HTTP {esperado}", () => pm.response.to.have.status({esperado}));'
    ]
    if verificar:
        testes.append(f'pm.test("Regra de negócio", () => {{ {verificar} }});')
    if salvar:
        for variavel, campo in salvar.items():
            testes.append(
                f'pm.collectionVariables.set("{variavel}", pm.response.json().{campo});'
            )
    headers = []
    if token:
        headers.append({"key": "Authorization", "value": "Bearer {{" + token + "}}"})
    if chave:
        headers.append({"key": "Idempotency-Key", "value": chave + "-{{execucao}}"})
    request = {
        "method": metodo,
        "header": headers,
        "url": "{{baseUrl}}" + rota,
        "description": f"{numero}. {nome}\n\nPré-condição — {pre}\n\nEsperado — HTTP {esperado}.",
    }
    if corpo is not None:
        headers.append({"key": "Content-Type", "value": "application/json"})
        request["body"] = {
            "mode": "raw",
            "raw": json.dumps(corpo, ensure_ascii=False, indent=2),
            "options": {"raw": {"language": "json"}},
        }
    cenarios.append(
        {
            "pasta": pasta,
            "id": numero,
            "nome": nome,
            "esperado": esperado,
            "pre": pre,
            "item": {
                "name": numero + " - " + nome,
                "request": request,
                "event": [
                    {
                        "listen": "test",
                        "script": {"type": "text/javascript", "exec": testes},
                    }
                ],
            },
        }
    )


pedido = {
    "unidadeId": 1,
    "canalPedido": "APP",
    "itens": [{"produtoId": 1, "quantidade": 1}],
}
for perfil, senha in [
    ("Cliente", "Cliente@123"),
    ("Admin", "Admin@123"),
    ("Cozinha", "Cozinha@123"),
    ("Gerente", "Gerente@123"),
]:
    adicionar(
        "01 Autenticação",
        "Login " + perfil,
        "POST",
        "/auth/login",
        200,
        {"email": perfil.lower() + "@raizes.local", "senha": senha},
        token=None,
        verificar='pm.expect(pm.response.json().accessToken).to.be.a("string");',
        salvar={"token" + perfil: "accessToken"},
    )
adicionar(
    "01 Autenticação",
    "Cadastro público",
    "POST",
    "/usuarios",
    201,
    {
        "nome": "Cliente da coleção",
        "email": "colecao+{{execucao}}@raizes.local",
        "senha": "Colecao@123",
    },
    token=None,
)
adicionar(
    "02 Catálogo",
    "Consultar unidades",
    "GET",
    "/unidades?page=1&limit=10",
    200,
    token=None,
)
adicionar(
    "02 Catálogo",
    "Consultar produtos",
    "GET",
    "/produtos?page=1&limit=10",
    200,
    token=None,
)
adicionar(
    "02 Catálogo",
    "Consultar cardápio local",
    "GET",
    "/unidades/1/cardapio",
    200,
    token=None,
)
adicionar(
    "02 Catálogo",
    "Cadastrar unidade",
    "POST",
    "/unidades",
    201,
    {"nome": "Unidade da coleção", "regiao": "Nordeste", "ativa": True},
    token="tokenAdmin",
    salvar={"unidadeNova": "id"},
)
adicionar(
    "02 Catálogo",
    "Editar unidade",
    "PUT",
    "/unidades/{{unidadeNova}}",
    200,
    {"nome": "Unidade teste atualizada", "regiao": "Nordeste", "ativa": True},
    token="tokenAdmin",
)
adicionar(
    "02 Catálogo",
    "Cadastrar produto",
    "POST",
    "/produtos",
    201,
    {"nome": "Bolo da coleção"},
    token="tokenAdmin",
    salvar={"produtoNovo": "id"},
)
adicionar(
    "02 Catálogo",
    "Editar produto",
    "PUT",
    "/produtos/{{produtoNovo}}",
    200,
    {"nome": "Bolo de macaxeira"},
    token="tokenAdmin",
)
adicionar(
    "02 Catálogo",
    "Definir preço local",
    "PUT",
    "/unidades/1/cardapio/{{produtoNovo}}",
    200,
    {"precoCentavos": 800, "disponivel": True},
    token="tokenAdmin",
)
adicionar(
    "03 Estoque",
    "Entrada com motivo",
    "POST",
    "/unidades/1/estoque/{{produtoNovo}}/movimentos",
    201,
    {"quantidade": 10, "motivo": "Reposição de demonstração"},
    token="tokenGerente",
)
adicionar(
    "03 Estoque",
    "Consultar saldo",
    "GET",
    "/unidades/1/estoque",
    200,
    token="tokenGerente",
)
adicionar(
    "04 Pedidos",
    "Aceitar fidelidade",
    "PUT",
    "/fidelidade/consentimento",
    200,
    {"aceito": True},
)
adicionar(
    "04 Pedidos",
    "Criar pedido APP",
    "POST",
    "/pedidos",
    201,
    pedido,
    chave="pedido-principal",
    salvar={"pedidoId": "pedidoId"},
    verificar='pm.expect(pm.response.json().canalPedido).to.equal("APP"); pm.expect(pm.response.json().totalCentavos).to.equal(1200);',
)
adicionar(
    "04 Pedidos",
    "Repetir criação idempotente",
    "POST",
    "/pedidos",
    201,
    pedido,
    chave="pedido-principal",
    verificar='pm.expect(pm.response.json().pedidoId).to.equal(Number(pm.collectionVariables.get("pedidoId")));',
)
adicionar("04 Pedidos", "Consultar pedido", "GET", "/pedidos/{{pedidoId}}", 200)
adicionar(
    "04 Pedidos",
    "Filtrar por canal",
    "GET",
    "/pedidos?canalPedido=APP&status=AGUARDANDO_PAGAMENTO",
    200,
    verificar='pm.expect(pm.response.json().items.every(p => p.canalPedido === "APP")).to.equal(true);',
)
adicionar(
    "05 Pagamentos",
    "Recusar pagamento",
    "POST",
    "/pedidos/{{pedidoId}}/pagamentos",
    200,
    {"resultado": "RECUSADO"},
    chave="pagamento-recusado",
    verificar='pm.expect(pm.response.json().statusPagamento).to.equal("RECUSADO"); pm.expect(pm.response.json().pedido.status).to.equal("AGUARDANDO_PAGAMENTO");',
)
adicionar(
    "05 Pagamentos",
    "Simular indisponibilidade",
    "POST",
    "/pedidos/{{pedidoId}}/pagamentos",
    503,
    {"resultado": "TIMEOUT"},
    chave="pagamento-timeout",
    verificar='pm.expect(pm.response.json().error).to.equal("PAGAMENTO_INDISPONIVEL");',
)
adicionar(
    "05 Pagamentos",
    "Aprovar pagamento",
    "POST",
    "/pedidos/{{pedidoId}}/pagamentos",
    200,
    {"resultado": "APROVADO"},
    chave="pagamento-aprovado",
    verificar='pm.expect(pm.response.json().pedido.status).to.equal("RECEBIDO");',
)
adicionar(
    "05 Pagamentos",
    "Repetir pagamento aprovado",
    "POST",
    "/pedidos/{{pedidoId}}/pagamentos",
    200,
    {"resultado": "APROVADO"},
    chave="pagamento-aprovado",
)
adicionar(
    "06 Operação",
    "Iniciar preparo",
    "PATCH",
    "/pedidos/{{pedidoId}}/status",
    200,
    {"status": "EM_PREPARO"},
    token="tokenCozinha",
)
adicionar(
    "06 Operação",
    "Marcar pronto",
    "PATCH",
    "/pedidos/{{pedidoId}}/status",
    200,
    {"status": "PRONTO"},
    token="tokenCozinha",
)
adicionar(
    "06 Operação",
    "Confirmar entrega",
    "PATCH",
    "/pedidos/{{pedidoId}}/status",
    200,
    {"status": "ENTREGUE"},
    token="tokenGerente",
)
adicionar(
    "06 Operação",
    "Consultar pontos",
    "GET",
    "/fidelidade",
    200,
    verificar="pm.expect(pm.response.json().saldo).to.be.at.least(12);",
)
adicionar(
    "06 Operação",
    "Auditar operação sensível",
    "GET",
    "/auditoria?limit=100",
    200,
    token="tokenAdmin",
    verificar='pm.expect(pm.response.json().items.some(a => a.acao === "STATUS_ENTREGUE")).to.equal(true);',
)
adicionar(
    "06 Operação",
    "Vendas consolidadas",
    "GET",
    "/relatorios/vendas",
    200,
    token="tokenAdmin",
)
adicionar("07 Erros", "Acesso sem token", "GET", "/pedidos", 401, token=None)
adicionar(
    "07 Erros",
    "Perfil sem permissão",
    "POST",
    "/produtos",
    403,
    {"nome": "Produto bloqueado"},
)
adicionar(
    "07 Erros",
    "Canal obrigatório ausente",
    "POST",
    "/pedidos",
    422,
    {k: v for k, v in pedido.items() if k != "canalPedido"},
    chave="sem-canal",
)
adicionar(
    "07 Erros",
    "Canal inválido",
    "POST",
    "/pedidos",
    422,
    {**pedido, "canalPedido": "EMAIL"},
    chave="canal-invalido",
)
adicionar(
    "07 Erros",
    "Quantidade negativa",
    "POST",
    "/pedidos",
    422,
    {**pedido, "itens": [{"produtoId": 1, "quantidade": -1}]},
    chave="quantidade-invalida",
)
adicionar(
    "07 Erros",
    "Produto inexistente",
    "POST",
    "/pedidos",
    404,
    {**pedido, "itens": [{"produtoId": 999999, "quantidade": 1}]},
    chave="produto-inexistente",
)
adicionar(
    "07 Erros",
    "Unidade inexistente",
    "POST",
    "/pedidos",
    404,
    {**pedido, "unidadeId": 999999},
    chave="unidade-inexistente",
)
adicionar(
    "07 Erros",
    "Estoque insuficiente",
    "POST",
    "/pedidos",
    409,
    {**pedido, "itens": [{"produtoId": 2, "quantidade": 100}]},
    chave="sem-estoque",
)
adicionar(
    "07 Erros",
    "Transição inválida",
    "PATCH",
    "/pedidos/{{pedidoId}}/status",
    409,
    {"status": "RECEBIDO"},
    token="tokenAdmin",
)
adicionar(
    "07 Erros",
    "Isolamento de unidade",
    "GET",
    "/unidades/2/estoque",
    403,
    token="tokenGerente",
)
adicionar(
    "08 Cancelamento",
    "Criar pedido TOTEM",
    "POST",
    "/pedidos",
    201,
    {**pedido, "canalPedido": "TOTEM"},
    chave="pedido-cancelar",
    salvar={"pedidoCancelar": "pedidoId"},
)
adicionar(
    "08 Cancelamento",
    "Cancelar pendente",
    "PATCH",
    "/pedidos/{{pedidoCancelar}}/status",
    200,
    {"status": "CANCELADO"},
)
adicionar(
    "08 Cancelamento",
    "Revogar consentimento",
    "PUT",
    "/fidelidade/consentimento",
    200,
    {"aceito": False},
)
adicionar("09 Sistema", "Verificar API e banco", "GET", "/health", 200, token=None)


def main():
    pastas = {}
    for c in cenarios:
        pastas.setdefault(c["pasta"], []).append(c["item"])
    colecao = {
        "info": {
            "name": "Raízes do Nordeste - fluxo completo",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
            "description": "Execute em ordem, com banco de demonstração. As credenciais são fictícias.",
        },
        "variable": [
            {"key": "baseUrl", "value": "http://127.0.0.1:8000"},
            {"key": "execucao", "value": ""},
        ],
        "event": [
            {
                "listen": "prerequest",
                "script": {
                    "type": "text/javascript",
                    "exec": [
                        'if (pm.info.requestName === "T01 - Login Cliente") { pm.collectionVariables.set("execucao", Date.now().toString()); }'
                    ],
                },
            }
        ],
        "item": [{"name": p, "item": itens} for p, itens in pastas.items()],
    }
    (ROOT / "postman").mkdir(exist_ok=True)
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "postman/raizes.postman_collection.json").write_text(
        json.dumps(colecao, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    linhas = [
        "# Plano de testes da coleção",
        "",
        "Execute as pastas em ordem, após aplicar o seed. Cada linha corresponde a uma requisição com asserção de status. As regras do fluxo principal têm asserções de conteúdo. Os testes de regressão em `tests/test_api.py` verificam concorrência, rollback e isolamento.",
        "",
        "| ID | Cenário e evidência na coleção | Método e endpoint | Entrada | Resultado |",
        "|---|---|---|---|---|",
    ]
    for c in cenarios:
        r = c["item"]["request"]
        corpo = (
            r.get("body", {})
            .get("raw", "Sem body")
            .replace("\n", " ")
            .replace("|", "/")
        )
        linhas.append(
            f"| {c['id']} | {c['nome']} | {r['method']} {r['url'].replace('{{baseUrl}}', '')} | {corpo} | HTTP {c['esperado']} |"
        )
    linhas += [
        "",
        "Pré-condições gerais. O banco contém o seed e os cenários anteriores foram executados. T01 a T04 guardam os tokens. T17 guarda pedidoId. T41 guarda pedidoCancelar. Os testes negativos enviam entradas inválidas deliberadamente.",
        "",
        "Critérios de conteúdo. O pedido APP tem total de 1.200 centavos. Recusa mantém AGUARDANDO_PAGAMENTO, aprovação muda para RECEBIDO, entrega gera pelo menos 12 pontos e a auditoria contém STATUS_ENTREGUE.",
        "",
        "Os cenários representam uma validação local. Teste de carga, disponibilidade e avaliação jurídica da política de privacidade ficam como etapas futuras.",
    ]
    (ROOT / "docs/plano_testes.md").write_text("\n".join(linhas), encoding="utf-8")
    print(f"{len(cenarios)} cenários gerados.")


if __name__ == "__main__":
    main()
