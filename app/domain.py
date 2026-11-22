"""Contratos e regras independentes de HTTP e banco de dados."""

from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field, field_validator


class RegraNegocio(Exception):
    def __init__(self, status: int, codigo: str, mensagem: str):
        self.status = status
        self.codigo = codigo
        self.mensagem = mensagem


class Canal(StrEnum):
    APP = "APP"
    TOTEM = "TOTEM"
    BALCAO = "BALCAO"
    PICKUP = "PICKUP"
    WEB = "WEB"


class StatusPedido(StrEnum):
    AGUARDANDO_PAGAMENTO = "AGUARDANDO_PAGAMENTO"
    RECEBIDO = "RECEBIDO"
    EM_PREPARO = "EM_PREPARO"
    PRONTO = "PRONTO"
    ENTREGUE = "ENTREGUE"
    CANCELADO = "CANCELADO"


TRANSICOES = {
    "AGUARDANDO_PAGAMENTO": {"CANCELADO"},
    "RECEBIDO": {"EM_PREPARO"},
    "EM_PREPARO": {"PRONTO"},
    "PRONTO": {"ENTREGUE"},
    "ENTREGUE": set(),
    "CANCELADO": set(),
}


class Contrato(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Login(Contrato):
    email: str = Field(min_length=5, max_length=150, examples=["cliente@raizes.local"])
    senha: str = Field(min_length=8, max_length=128, examples=["Cliente@123"])

    @field_validator("email")
    @classmethod
    def validar_email(cls, valor):
        if "@" not in valor or "." not in valor.split("@")[-1] or " " in valor:
            raise ValueError("E-mail inválido.")
        return valor.lower()


class Cadastro(Login):
    nome: str = Field(min_length=2, max_length=100, examples=["Maria"])


class UnidadeEntrada(Contrato):
    nome: str = Field(min_length=2, max_length=100)
    regiao: str = Field(min_length=2, max_length=50)
    ativa: bool = True


class ProdutoEntrada(Contrato):
    nome: str = Field(min_length=2, max_length=100)


class CardapioEntrada(Contrato):
    precoCentavos: int = Field(gt=0, le=1000000, strict=True)
    disponivel: bool = True


class MovimentoEntrada(Contrato):
    quantidade: int = Field(ge=-100000, le=100000, strict=True)
    motivo: str = Field(min_length=5, max_length=200)

    @field_validator("quantidade")
    @classmethod
    def quantidade_nao_nula(cls, valor):
        if valor == 0:
            raise ValueError("Informe uma quantidade diferente de zero.")
        return valor


class ItemEntrada(Contrato):
    produtoId: int = Field(gt=0, strict=True)
    quantidade: int = Field(gt=0, le=100, strict=True)


class PedidoEntrada(Contrato):
    unidadeId: int = Field(gt=0, strict=True)
    canalPedido: Canal
    itens: list[ItemEntrada] = Field(min_length=1, max_length=30)
    pontosResgate: int = Field(default=0, ge=0, le=100000, strict=True)


class PagamentoEntrada(Contrato):
    resultado: str = Field(
        pattern="^(APROVADO|RECUSADO|TIMEOUT)$", examples=["APROVADO"]
    )


class StatusEntrada(Contrato):
    status: StatusPedido


class ConsentimentoEntrada(Contrato):
    aceito: bool


class ErroResposta(BaseModel):
    error: str
    message: str
    details: list[dict] = []
    timestamp: str
    path: str


class ItemResposta(BaseModel):
    produtoId: int
    quantidade: int
    precoUnitarioCentavos: int


class PedidoResposta(BaseModel):
    pedidoId: int
    clienteId: int
    unidadeId: int
    canalPedido: Canal
    status: StatusPedido
    subtotalCentavos: int
    descontoCentavos: int
    totalCentavos: int
    pontosResgate: int
    itens: list[ItemResposta]
    criadoEm: str


class PaginaPedidos(BaseModel):
    items: list[PedidoResposta]
    page: int
    limit: int
    total: int


class PagamentoResposta(BaseModel):
    pagamentoId: int
    statusPagamento: str
    referencia: str | None
    valorCentavos: int
    pedido: PedidoResposta


class UsuarioResposta(BaseModel):
    id: int
    nome: str
    perfil: str


class LoginResposta(BaseModel):
    accessToken: str
    tokenType: str
    expiresIn: int
    user: UsuarioResposta


def exigir(condicao, status, codigo, mensagem):
    if not condicao:
        raise RegraNegocio(status, codigo, mensagem)
