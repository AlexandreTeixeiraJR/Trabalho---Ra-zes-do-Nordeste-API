"""Regressões de consistência e segurança que complementam a coleção Postman."""

from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app.infrastructure import banco, seed
from app.main import app


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "teste.db"))
    monkeypatch.setenv(
        "JWT_SECRET", "segredo-exclusivo-de-testes-com-mais-de-32-caracteres"
    )
    seed()
    with TestClient(app) as client:
        yield client


def auth(api, email="cliente", senha="Cliente@123"):
    resposta = api.post(
        "/auth/login", json={"email": email + "@raizes.local", "senha": senha}
    )
    assert resposta.status_code == 200, resposta.text
    return {"Authorization": "Bearer " + resposta.json()["accessToken"]}


def criar(api, headers, chave="pedido-teste-001", quantidade=1):
    return api.post(
        "/pedidos",
        headers={**headers, "Idempotency-Key": chave},
        json={
            "unidadeId": 1,
            "canalPedido": "APP",
            "itens": [{"produtoId": 1, "quantidade": quantidade}],
        },
    )


def test_idempotencia_e_conflito(api):
    headers = auth(api)
    a = criar(api, headers)
    b = criar(api, headers)
    assert a.status_code == b.status_code == 201
    assert a.json() == b.json()
    assert criar(api, headers, quantidade=2).status_code == 409
    with banco() as db:
        assert (
            db.execute(
                "SELECT saldo FROM cardapio WHERE unidade_id=1 AND produto_id=1"
            ).fetchone()[0]
            == 99
        )


def test_reserva_concorrente(api):
    headers = auth(api)
    with banco(True) as db:
        db.execute("UPDATE cardapio SET saldo=1 WHERE unidade_id=1 AND produto_id=1")
    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados = list(
            pool.map(
                lambda chave: criar(api, headers, chave),
                ["concorrencia-01", "concorrencia-02"],
            )
        )
    assert sorted(r.status_code for r in resultados) == [201, 409]
    with banco() as db:
        assert (
            db.execute(
                "SELECT saldo FROM cardapio WHERE unidade_id=1 AND produto_id=1"
            ).fetchone()[0]
            == 0
        )


def test_atomicidade_itens(api):
    headers = auth(api)
    resposta = api.post(
        "/pedidos",
        headers={**headers, "Idempotency-Key": "atomicidade-01"},
        json={
            "unidadeId": 1,
            "canalPedido": "APP",
            "itens": [
                {"produtoId": 1, "quantidade": 1},
                {"produtoId": 999, "quantidade": 1},
            ],
        },
    )
    assert resposta.status_code == 404
    with banco() as db:
        assert db.execute("SELECT COUNT(*) FROM pedidos").fetchone()[0] == 0
        assert (
            db.execute(
                "SELECT saldo FROM cardapio WHERE unidade_id=1 AND produto_id=1"
            ).fetchone()[0]
            == 100
        )


def test_cancelamento_devolve_uma_vez(api):
    headers = auth(api)
    pedido = criar(api, headers).json()["pedidoId"]
    url = f"/pedidos/{pedido}/status"
    assert (
        api.patch(url, headers=headers, json={"status": "CANCELADO"}).status_code == 200
    )
    assert (
        api.patch(url, headers=headers, json={"status": "CANCELADO"}).status_code == 409
    )
    with banco() as db:
        assert (
            db.execute(
                "SELECT saldo FROM cardapio WHERE unidade_id=1 AND produto_id=1"
            ).fetchone()[0]
            == 100
        )


def test_timeout_persistido_e_retentativa(api):
    headers = auth(api)
    pedido = criar(api, headers).json()["pedidoId"]
    url = f"/pedidos/{pedido}/pagamentos"
    timeout = api.post(
        url,
        headers={**headers, "Idempotency-Key": "timeout-teste"},
        json={"resultado": "TIMEOUT"},
    )
    assert timeout.status_code == 503
    assert timeout.json()["error"] == "PAGAMENTO_INDISPONIVEL"
    with banco() as db:
        assert (
            db.execute(
                "SELECT COUNT(*) FROM pagamentos WHERE status='TIMEOUT'"
            ).fetchone()[0]
            == 1
        )
    for _ in range(2):
        aprovado = api.post(
            url,
            headers={**headers, "Idempotency-Key": "aprovar-teste"},
            json={"resultado": "APROVADO"},
        )
        assert aprovado.status_code == 200
        assert aprovado.json()["pedido"]["status"] == "RECEBIDO"
    with banco() as db:
        assert (
            db.execute(
                "SELECT COUNT(*) FROM pagamentos WHERE status='APROVADO'"
            ).fetchone()[0]
            == 1
        )


def test_isolamento_cliente_e_unidade(api):
    headers = auth(api)
    pedido = criar(api, headers).json()["pedidoId"]
    api.post(
        "/usuarios",
        json={
            "nome": "Outro cliente",
            "email": "outro@raizes.local",
            "senha": "Outra@123",
        },
    )
    outro = auth(api, "outro", "Outra@123")
    assert api.get(f"/pedidos/{pedido}", headers=outro).status_code == 403
    assert api.get("/pedidos", headers=outro).json()["total"] == 0
    gerente = auth(api, "gerente", "Gerente@123")
    assert api.get("/unidades/2/estoque", headers=gerente).status_code == 403
    assert (
        api.post("/produtos", headers=headers, json={"nome": "Novo"}).status_code == 403
    )


@pytest.mark.parametrize(
    "alteracao",
    [
        {"canalPedido": None},
        {"canalPedido": "INVALIDO"},
        {"itens": [{"produtoId": 1, "quantidade": -1}]},
        {"itens": [{"produtoId": 1, "quantidade": True}]},
        {
            "itens": [
                {"produtoId": 1, "quantidade": 1},
                {"produtoId": 1, "quantidade": 1},
            ]
        },
        {"totalCentavos": 1},
    ],
)
def test_validacoes(api, alteracao):
    corpo = {
        "unidadeId": 1,
        "canalPedido": "APP",
        "itens": [{"produtoId": 1, "quantidade": 1}],
    }
    corpo.update(alteracao)
    assert (
        api.post(
            "/pedidos",
            headers={**auth(api), "Idempotency-Key": "validacao-001"},
            json=corpo,
        ).status_code
        == 422
    )


def test_fidelidade_resgate_estorno_revogacao(api):
    cliente = auth(api)
    admin = auth(api, "admin", "Admin@123")
    api.put("/fidelidade/consentimento", headers=cliente, json={"aceito": True})
    pedido = criar(api, cliente).json()["pedidoId"]
    api.post(
        f"/pedidos/{pedido}/pagamentos",
        headers={**cliente, "Idempotency-Key": "fidelidade-pg"},
        json={"resultado": "APROVADO"},
    )
    for status in ["EM_PREPARO", "PRONTO", "ENTREGUE"]:
        assert (
            api.patch(
                f"/pedidos/{pedido}/status", headers=admin, json={"status": status}
            ).status_code
            == 200
        )
    assert api.get("/fidelidade", headers=cliente).json()["saldo"] == 12
    corpo = {
        "unidadeId": 1,
        "canalPedido": "WEB",
        "pontosResgate": 10,
        "itens": [{"produtoId": 1, "quantidade": 1}],
    }
    novo = api.post(
        "/pedidos", headers={**cliente, "Idempotency-Key": "resgate-teste"}, json=corpo
    )
    assert novo.json()["totalCentavos"] == 1190
    assert api.get("/fidelidade", headers=cliente).json()["saldo"] == 2
    assert (
        api.patch(
            f"/pedidos/{novo.json()['pedidoId']}/status",
            headers=cliente,
            json={"status": "CANCELADO"},
        ).status_code
        == 200
    )
    assert api.get("/fidelidade", headers=cliente).json()["saldo"] == 12
    api.put("/fidelidade/consentimento", headers=cliente, json={"aceito": False})
    assert (
        api.post(
            "/pedidos",
            headers={**cliente, "Idempotency-Key": "resgate-revogado"},
            json=corpo,
        ).status_code
        == 409
    )


def test_reiniciar_preserva_dados(api):
    headers = auth(api)
    pedido = criar(api, headers).json()["pedidoId"]
    with TestClient(app) as outro_processo:
        assert (
            outro_processo.get(f"/pedidos/{pedido}", headers=headers).status_code == 200
        )


def test_seed_repetivel(api):
    headers = auth(api)
    criar(api, headers)
    seed()
    with banco() as db:
        assert (
            db.execute(
                "SELECT saldo FROM cardapio WHERE unidade_id=1 AND produto_id=1"
            ).fetchone()[0]
            == 99
        )


def test_credenciais_e_auditoria(api):
    assert api.get("/pedidos").status_code == 401
    assert (
        api.get("/pedidos", headers={"Authorization": "Bearer invalido"}).status_code
        == 401
    )
    assert (
        api.post(
            "/auth/login", json={"email": "cliente@raizes.local", "senha": "errada123"}
        ).status_code
        == 401
    )
    admin = auth(api, "admin", "Admin@123")
    resposta = api.get("/auditoria", headers=admin)
    assert resposta.status_code == 200
    assert any(item["acao"] == "LOGIN" for item in resposta.json()["items"])
    assert "senha_hash" not in resposta.text


def test_movimento_zero_e_contrato(api):
    admin = auth(api, "admin", "Admin@123")
    resposta = api.post(
        "/unidades/1/estoque/1/movimentos",
        headers=admin,
        json={"quantidade": 0, "motivo": "Quantidade inválida"},
    )
    assert resposta.status_code == 422
    schema = api.get("/openapi.json").json()
    assert "canalPedido" in schema["components"]["schemas"]["PedidoEntrada"]["required"]
    assert api.get("/docs").status_code == 200
