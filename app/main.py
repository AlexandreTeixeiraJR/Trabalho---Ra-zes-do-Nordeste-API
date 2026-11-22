"""Interface REST. Execute com python -m uvicorn app.main:app --reload."""

import os
import json
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends, FastAPI, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.openapi.utils import get_openapi
from starlette.exceptions import HTTPException

from app import application as casos
from app.domain import (
    Cadastro,
    Canal,
    CardapioEntrada,
    ConsentimentoEntrada,
    ErroResposta,
    Login,
    LoginResposta,
    MovimentoEntrada,
    PagamentoEntrada,
    PagamentoResposta,
    PaginaPedidos,
    PedidoEntrada,
    PedidoResposta,
    ProdutoEntrada,
    RegraNegocio,
    StatusEntrada,
    StatusPedido,
    UnidadeEntrada,
    UsuarioResposta,
    exigir,
)
from app.infrastructure import (
    agora,
    auditar,
    banco,
    conferir_senha,
    migrar,
    senha_hash,
    ROOT,
)


def segredo():
    chave = os.getenv("JWT_SECRET", "")
    if len(chave) < 32 or chave.startswith("troque-"):
        raise RuntimeError(
            "Configure JWT_SECRET com uma chave aleatória de pelo menos 32 caracteres."
        )
    return chave


@asynccontextmanager
async def iniciar(app):
    segredo()
    migrar()
    yield


erros = {
    codigo: {"model": ErroResposta, "description": descricao}
    for codigo, descricao in {
        401: "Token ausente ou inválido",
        403: "Sem permissão",
        404: "Recurso inexistente",
        409: "Conflito de negócio ou idempotência",
        422: "Dados inválidos",
        503: "Dependência indisponível",
    }.items()
}
app = FastAPI(
    title="Raízes do Nordeste - API",
    version="1.0.0",
    lifespan=iniciar,
    description="Projeto Back-end. Valores monetários em centavos. Pagamento exclusivamente simulado.",
    responses=erros,
)
bearer = HTTPBearer(auto_error=False)


def erro(request, status, codigo, mensagem, detalhes=None):
    return JSONResponse(
        status_code=status,
        content={
            "error": codigo,
            "message": mensagem,
            "details": detalhes or [],
            "timestamp": agora(),
            "path": request.url.path,
        },
    )


@app.exception_handler(RegraNegocio)
async def tratar_regra(request: Request, exc: RegraNegocio):
    return erro(request, exc.status, exc.codigo, exc.mensagem)


@app.exception_handler(RequestValidationError)
async def tratar_validacao(request: Request, exc: RequestValidationError):
    detalhes = [
        {"field": ".".join(map(str, e["loc"])), "issue": e["msg"]} for e in exc.errors()
    ]
    return erro(request, 422, "VALIDACAO", "Verifique os campos enviados.", detalhes)


@app.exception_handler(HTTPException)
async def tratar_http(request: Request, exc: HTTPException):
    return erro(request, exc.status_code, "ERRO_HTTP", str(exc.detail))


@app.exception_handler(sqlite3.OperationalError)
async def tratar_banco(request: Request, exc: sqlite3.OperationalError):
    return erro(
        request,
        503,
        "BANCO_INDISPONIVEL",
        "Banco temporariamente indisponível. Tente novamente.",
    )


@app.exception_handler(Exception)
async def tratar_inesperado(request: Request, exc: Exception):
    return erro(
        request, 500, "ERRO_INTERNO", "Falha interna ao processar a solicitação."
    )


def atual(credencial: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
    exigir(
        credencial and credencial.scheme.lower() == "bearer",
        401,
        "NAO_AUTENTICADO",
        "Informe um token Bearer.",
    )
    try:
        payload = jwt.decode(
            credencial.credentials,
            segredo(),
            algorithms=["HS256"],
            options={"require": ["exp", "sub", "iat"]},
        )
        usuario_id = int(payload["sub"])
    except (jwt.InvalidTokenError, ValueError, KeyError):
        raise RegraNegocio(401, "TOKEN_INVALIDO", "Token inválido ou expirado.")
    with banco() as db:
        usuario = db.execute(
            "SELECT id,nome,email,perfil,unidade_id FROM usuarios WHERE id=?",
            (usuario_id,),
        ).fetchone()
        exigir(usuario, 401, "TOKEN_INVALIDO", "Usuário do token não existe.")
        return dict(usuario)


def perfis(*permitidos):
    def verificar(usuario=Depends(atual)):
        exigir(
            usuario["perfil"] in permitidos,
            403,
            "SEM_PERMISSAO",
            "Perfil sem permissão para esta operação.",
        )
        return usuario

    return verificar


Usuario = Annotated[dict, Depends(atual)]
Gestor = Annotated[dict, Depends(perfis("ADMIN", "GERENTE"))]
Admin = Annotated[dict, Depends(perfis("ADMIN"))]
Comprador = Annotated[dict, Depends(perfis("CLIENTE", "ATENDENTE", "GERENTE", "ADMIN"))]
Pagina = Annotated[int, Query(ge=1)]
Limite = Annotated[int, Query(ge=1, le=100)]
Chave = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=100)]


def paginar(db, sql, args, page, limit):
    total = db.execute("SELECT COUNT(*) FROM (" + sql + ")", args).fetchone()[0]
    rows = db.execute(
        sql + " LIMIT ? OFFSET ?", (*args, limit, (page - 1) * limit)
    ).fetchall()
    return {
        "items": [dict(r) for r in rows],
        "page": page,
        "limit": limit,
        "total": total,
    }


@app.get("/health", tags=["Sistema"])
def health():
    """Verifica se o processo e o banco respondem."""
    with banco() as db:
        db.execute("SELECT 1")
    return {"status": "ok"}


@app.post(
    "/usuarios", status_code=201, tags=["Autenticação"], response_model=UsuarioResposta
)
def cadastrar(entrada: Cadastro):
    """Cadastro público cria exclusivamente perfil CLIENTE."""
    with banco(True) as db:
        try:
            novo = db.execute(
                "INSERT INTO usuarios (nome,email,senha_hash) VALUES (?,?,?)",
                (entrada.nome, entrada.email, senha_hash(entrada.senha)),
            ).lastrowid
        except sqlite3.IntegrityError:
            raise RegraNegocio(409, "EMAIL_CADASTRADO", "E-mail já cadastrado.")
        auditar(db, novo, "CADASTRAR_USUARIO", novo)
        return {"id": novo, "nome": entrada.nome, "perfil": "CLIENTE"}


@app.post("/auth/login", tags=["Autenticação"], response_model=LoginResposta)
def login(entrada: Login):
    """Retorna JWT válido por TOKEN_MINUTES. Use-o em Authorize no Swagger."""
    with banco(True) as db:
        usuario = db.execute(
            "SELECT * FROM usuarios WHERE email=?", (entrada.email,)
        ).fetchone()
        exigir(
            usuario and conferir_senha(entrada.senha, usuario["senha_hash"]),
            401,
            "CREDENCIAIS_INVALIDAS",
            "E-mail ou senha inválidos.",
        )
        minutos = int(os.getenv("TOKEN_MINUTES", "60"))
        instante = datetime.now(timezone.utc)
        token = jwt.encode(
            {
                "sub": str(usuario["id"]),
                "iat": instante,
                "exp": instante + timedelta(minutes=minutos),
            },
            segredo(),
            algorithm="HS256",
        )
        auditar(db, usuario["id"], "LOGIN", usuario["id"])
        return {
            "accessToken": token,
            "tokenType": "Bearer",
            "expiresIn": minutos * 60,
            "user": {
                "id": usuario["id"],
                "nome": usuario["nome"],
                "perfil": usuario["perfil"],
            },
        }


@app.get("/unidades", tags=["Catálogo"])
def unidades(page: Pagina = 1, limit: Limite = 10):
    with banco() as db:
        return paginar(db, "SELECT * FROM unidades ORDER BY id", (), page, limit)


@app.post("/unidades", status_code=201, tags=["Catálogo"])
def criar_unidade(entrada: UnidadeEntrada, usuario: Admin):
    with banco(True) as db:
        novo = db.execute(
            "INSERT INTO unidades (nome,regiao,ativa) VALUES (?,?,?)",
            (entrada.nome, entrada.regiao, entrada.ativa),
        ).lastrowid
        auditar(db, usuario["id"], "CRIAR_UNIDADE", novo)
        return dict(casos.obter(db, "unidades", novo))


@app.put("/unidades/{unidade_id}", tags=["Catálogo"])
def editar_unidade(unidade_id: int, entrada: UnidadeEntrada, usuario: Admin):
    with banco(True) as db:
        casos.obter(db, "unidades", unidade_id)
        db.execute(
            "UPDATE unidades SET nome=?,regiao=?,ativa=? WHERE id=?",
            (entrada.nome, entrada.regiao, entrada.ativa, unidade_id),
        )
        auditar(db, usuario["id"], "EDITAR_UNIDADE", unidade_id)
        return dict(casos.obter(db, "unidades", unidade_id))


@app.get("/produtos", tags=["Catálogo"])
def produtos(page: Pagina = 1, limit: Limite = 10):
    with banco() as db:
        return paginar(db, "SELECT * FROM produtos ORDER BY id", (), page, limit)


@app.post("/produtos", status_code=201, tags=["Catálogo"])
def criar_produto(entrada: ProdutoEntrada, usuario: Admin):
    with banco(True) as db:
        novo = db.execute(
            "INSERT INTO produtos (nome) VALUES (?)", (entrada.nome,)
        ).lastrowid
        auditar(db, usuario["id"], "CRIAR_PRODUTO", novo)
        return {"id": novo, "nome": entrada.nome}


@app.put("/produtos/{produto_id}", tags=["Catálogo"])
def editar_produto(produto_id: int, entrada: ProdutoEntrada, usuario: Admin):
    with banco(True) as db:
        casos.obter(db, "produtos", produto_id)
        db.execute("UPDATE produtos SET nome=? WHERE id=?", (entrada.nome, produto_id))
        auditar(db, usuario["id"], "EDITAR_PRODUTO", produto_id)
        return {"id": produto_id, "nome": entrada.nome}


@app.get("/unidades/{unidade_id}/cardapio", tags=["Catálogo"])
def cardapio(unidade_id: int, page: Pagina = 1, limit: Limite = 10):
    with banco() as db:
        unidade = casos.obter(db, "unidades", unidade_id)
        exigir(unidade["ativa"], 409, "UNIDADE_INATIVA", "A unidade está inativa.")
        return paginar(
            db,
            "SELECT c.produto_id AS produtoId,p.nome,c.preco_centavos AS precoCentavos,c.saldo FROM cardapio c JOIN produtos p ON p.id=c.produto_id WHERE c.unidade_id=? AND c.disponivel=1 ORDER BY p.id",
            (unidade_id,),
            page,
            limit,
        )


@app.put("/unidades/{unidade_id}/cardapio/{produto_id}", tags=["Catálogo"])
def definir_oferta(
    unidade_id: int, produto_id: int, entrada: CardapioEntrada, usuario: Gestor
):
    """Inclui ou altera preço e disponibilidade local. Estoque começa em zero."""
    casos.permitir_unidade(usuario, unidade_id)
    with banco(True) as db:
        casos.obter(db, "unidades", unidade_id)
        casos.obter(db, "produtos", produto_id)
        db.execute(
            "INSERT INTO cardapio VALUES (?,?,?,?,0) ON CONFLICT(unidade_id,produto_id) DO UPDATE SET preco_centavos=excluded.preco_centavos,disponivel=excluded.disponivel",
            (unidade_id, produto_id, entrada.precoCentavos, entrada.disponivel),
        )
        auditar(db, usuario["id"], "ALTERAR_CARDAPIO", f"{unidade_id}/{produto_id}")
        return {
            "unidadeId": unidade_id,
            "produtoId": produto_id,
            **entrada.model_dump(),
        }


@app.get("/unidades/{unidade_id}/estoque", tags=["Estoque"])
def estoque(unidade_id: int, usuario: Gestor, page: Pagina = 1, limit: Limite = 10):
    casos.permitir_unidade(usuario, unidade_id)
    with banco() as db:
        casos.obter(db, "unidades", unidade_id)
        return paginar(
            db,
            "SELECT produto_id AS produtoId,saldo FROM cardapio WHERE unidade_id=? ORDER BY produto_id",
            (unidade_id,),
            page,
            limit,
        )


@app.post(
    "/unidades/{unidade_id}/estoque/{produto_id}/movimentos",
    status_code=201,
    tags=["Estoque"],
)
def movimentar(
    unidade_id: int, produto_id: int, entrada: MovimentoEntrada, usuario: Gestor
):
    """Quantidade positiva é entrada. Negativa é saída. Motivo obrigatório."""
    casos.permitir_unidade(usuario, unidade_id)
    with banco(True) as db:
        return casos.mover_estoque(
            db, usuario, unidade_id, produto_id, entrada.quantidade, entrada.motivo
        )


@app.post("/pedidos", status_code=201, tags=["Pedidos"], response_model=PedidoResposta)
def criar_pedido(entrada: PedidoEntrada, usuario: Comprador, chave: Chave):
    """Reserva estoque. Reenvie a mesma chave e corpo para obter o mesmo pedido."""
    return casos.criar_pedido(usuario, entrada, chave)


@app.get("/pedidos", tags=["Pedidos"], response_model=PaginaPedidos)
def pedidos(
    usuario: Usuario,
    page: Pagina = 1,
    limit: Limite = 10,
    canalPedido: Canal | None = None,
    status: StatusPedido | None = None,
):
    clausulas = ["1=1"]
    args = []
    if usuario["perfil"] == "CLIENTE":
        clausulas.append("usuario_id=?")
        args.append(usuario["id"])
    elif usuario["perfil"] != "ADMIN":
        clausulas.append("unidade_id=?")
        args.append(usuario["unidade_id"])
    if canalPedido:
        clausulas.append("canal=?")
        args.append(canalPedido.value)
    if status:
        clausulas.append("status=?")
        args.append(status.value)
    with banco() as db:
        resultado = paginar(
            db,
            "SELECT id FROM pedidos WHERE "
            + " AND ".join(clausulas)
            + " ORDER BY id DESC",
            tuple(args),
            page,
            limit,
        )
        resultado["items"] = [
            casos.pedido_json(db, r["id"]) for r in resultado["items"]
        ]
        return resultado


@app.get("/pedidos/{pedido_id}", tags=["Pedidos"], response_model=PedidoResposta)
def pedido(pedido_id: int, usuario: Usuario):
    with banco() as db:
        casos.permitir_pedido(usuario, casos.obter(db, "pedidos", pedido_id))
        return casos.pedido_json(db, pedido_id)


@app.patch(
    "/pedidos/{pedido_id}/status", tags=["Pedidos"], response_model=PedidoResposta
)
def status_pedido(pedido_id: int, entrada: StatusEntrada, usuario: Usuario):
    """Pagamento aprovado libera RECEBIDO. Depois EM_PREPARO, PRONTO e ENTREGUE.

    Cancelamento somente enquanto AGUARDANDO_PAGAMENTO. Devolve estoque e pontos reservados.
    """
    return casos.atualizar_status(usuario, pedido_id, entrada.status.value)


@app.post(
    "/pedidos/{pedido_id}/pagamentos",
    tags=["Pagamentos"],
    response_model=PagamentoResposta,
)
def pagamento(
    pedido_id: int, entrada: PagamentoEntrada, usuario: Comprador, chave: Chave
):
    """Simula APROVADO, RECUSADO ou TIMEOUT. Recusa mantém pedido pendente.

    TIMEOUT retorna 503 e persiste a tentativa. Use uma nova chave para nova tentativa.
    """
    return casos.pagar(usuario, pedido_id, entrada, chave)


@app.put("/fidelidade/consentimento", tags=["Fidelidade"])
def consentimento(
    entrada: ConsentimentoEntrada, usuario: Annotated[dict, Depends(perfis("CLIENTE"))]
):
    """Registra aceite ou revogação da finalidade FIDELIDADE e versão do aviso."""
    with banco(True) as db:
        db.execute(
            "INSERT INTO consentimentos (usuario_id,finalidade,aceito,versao,criado_em) VALUES (?,'FIDELIDADE',?,'1.0',?)",
            (usuario["id"], entrada.aceito, agora()),
        )
        auditar(db, usuario["id"], "CONSENTIMENTO_FIDELIDADE", usuario["id"])
        return {"finalidade": "FIDELIDADE", "aceito": entrada.aceito, "versao": "1.0"}


@app.get("/fidelidade", tags=["Fidelidade"])
def fidelidade(
    usuario: Annotated[dict, Depends(perfis("CLIENTE"))],
    page: Pagina = 1,
    limit: Limite = 10,
):
    with banco(True) as db:
        auditar(db, usuario["id"], "CONSULTAR_FIDELIDADE", usuario["id"])
        historico = paginar(
            db,
            "SELECT pedido_id AS pedidoId,tipo,quantidade,criado_em AS criadoEm FROM pontos WHERE usuario_id=? ORDER BY id DESC",
            (usuario["id"],),
            page,
            limit,
        )
        return {
            "saldo": casos.saldo_pontos(db, usuario["id"]),
            "consentimento": casos.consentiu(db, usuario["id"]),
            "historico": historico,
        }


@app.get("/auditoria", tags=["Gestão"])
def auditoria(usuario: Admin, page: Pagina = 1, limit: Limite = 10):
    with banco(True) as db:
        auditar(db, usuario["id"], "CONSULTAR_AUDITORIA", "auditoria")
        return paginar(db, "SELECT * FROM auditoria ORDER BY id DESC", (), page, limit)


@app.get("/relatorios/vendas", tags=["Gestão"])
def vendas(usuario: Gestor):
    """Receita de pedidos entregues agrupada por unidade, região e canal."""
    with banco(True) as db:
        filtro = ""
        args = ()
        if usuario["perfil"] != "ADMIN":
            filtro = " AND p.unidade_id=?"
            args = (usuario["unidade_id"],)
        sql = (
            "SELECT u.id AS unidadeId,u.regiao,p.canal AS canalPedido,COUNT(*) AS pedidos,SUM(p.total_centavos) AS receitaCentavos FROM pedidos p JOIN unidades u ON u.id=p.unidade_id WHERE p.status='ENTREGUE'"
            + filtro
            + " GROUP BY u.id,u.regiao,p.canal ORDER BY u.id,p.canal"
        )
        auditar(db, usuario["id"], "CONSULTAR_VENDAS", "vendas")
        return {"items": [dict(r) for r in db.execute(sql, args)]}


def documentacao_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    arquivo = ROOT / "docs/api_examples.json"
    if arquivo.exists():
        exemplos = json.loads(arquivo.read_text(encoding="utf-8"))
        for caminho, operacoes in schema["paths"].items():
            for metodo, operacao in operacoes.items():
                for codigo, exemplo in exemplos.get(
                    metodo.upper() + " " + caminho, {}
                ).items():
                    resposta = operacao["responses"].setdefault(
                        codigo, {"description": "Resposta observada em teste"}
                    )
                    resposta.setdefault("content", {}).setdefault(
                        "application/json", {}
                    )["example"] = exemplo
    app.openapi_schema = schema
    return schema


app.openapi = documentacao_openapi
