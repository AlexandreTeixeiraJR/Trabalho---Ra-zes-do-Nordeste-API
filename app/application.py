"""Casos de uso. Cada alteração de negócio termina em uma única transação."""

import hashlib
import json

from app.domain import PedidoEntrada, TRANSICOES, exigir
from app.infrastructure import GatewayMock, agora, auditar, banco


def obter(db, tabela, identificador):
    # Os nomes de tabela são constantes internas, nunca dados recebidos na API.
    registro = db.execute(
        f"SELECT * FROM {tabela} WHERE id=?", (identificador,)
    ).fetchone()
    exigir(registro, 404, "NAO_ENCONTRADO", "Recurso não encontrado.")
    return registro


def permitir_unidade(usuario, unidade_id):
    exigir(
        usuario["perfil"] == "ADMIN" or usuario["unidade_id"] == unidade_id,
        403,
        "SEM_PERMISSAO",
        "Usuário sem acesso a esta unidade.",
    )


def permitir_pedido(usuario, pedido):
    if usuario["perfil"] == "CLIENTE":
        exigir(
            usuario["id"] == pedido["usuario_id"],
            403,
            "SEM_PERMISSAO",
            "Pedido de outro cliente.",
        )
    else:
        permitir_unidade(usuario, pedido["unidade_id"])


def consentiu(db, usuario_id):
    registro = db.execute(
        "SELECT aceito FROM consentimentos WHERE usuario_id=? AND finalidade='FIDELIDADE' ORDER BY id DESC LIMIT 1",
        (usuario_id,),
    ).fetchone()
    return bool(registro and registro["aceito"])


def saldo_pontos(db, usuario_id):
    return db.execute(
        "SELECT COALESCE(SUM(quantidade),0) FROM pontos WHERE usuario_id=?",
        (usuario_id,),
    ).fetchone()[0]


def pedido_json(db, pedido_id):
    p = obter(db, "pedidos", pedido_id)
    itens = db.execute(
        "SELECT produto_id AS produtoId,quantidade,preco_centavos AS precoUnitarioCentavos FROM itens_pedido WHERE pedido_id=?",
        (pedido_id,),
    ).fetchall()
    return dict(
        pedidoId=p["id"],
        clienteId=p["usuario_id"],
        unidadeId=p["unidade_id"],
        canalPedido=p["canal"],
        status=p["status"],
        subtotalCentavos=p["subtotal_centavos"],
        descontoCentavos=p["desconto_centavos"],
        totalCentavos=p["total_centavos"],
        pontosResgate=p["pontos_resgate"],
        itens=[dict(i) for i in itens],
        criadoEm=p["criado_em"],
    )


def criar_pedido(usuario, entrada: PedidoEntrada, chave):
    corpo_hash = hashlib.sha256(
        json.dumps(entrada.model_dump(mode="json"), sort_keys=True).encode()
    ).hexdigest()
    with banco(True) as db:
        existente = db.execute(
            "SELECT * FROM pedidos WHERE usuario_id=? AND chave=?",
            (usuario["id"], chave),
        ).fetchone()
        if existente:
            exigir(
                existente["corpo_hash"] == corpo_hash,
                409,
                "CHAVE_REUTILIZADA",
                "A chave já foi usada com outro conteúdo.",
            )
            return pedido_json(db, existente["id"])
        unidade = obter(db, "unidades", entrada.unidadeId)
        exigir(unidade["ativa"], 409, "UNIDADE_INATIVA", "A unidade está inativa.")
        if usuario["perfil"] != "CLIENTE":
            permitir_unidade(usuario, entrada.unidadeId)
        ids = [i.produtoId for i in entrada.itens]
        exigir(
            len(ids) == len(set(ids)),
            422,
            "ITEM_REPETIDO",
            "Agrupe a quantidade de cada produto em um único item.",
        )
        subtotal = 0
        itens = []
        for item in entrada.itens:
            obter(db, "produtos", item.produtoId)
            oferta = db.execute(
                "SELECT * FROM cardapio WHERE unidade_id=? AND produto_id=?",
                (entrada.unidadeId, item.produtoId),
            ).fetchone()
            exigir(
                oferta and oferta["disponivel"],
                409,
                "PRODUTO_INDISPONIVEL",
                "Produto indisponível nesta unidade.",
            )
            exigir(
                oferta["saldo"] >= item.quantidade,
                409,
                "ESTOQUE_INSUFICIENTE",
                "Quantidade acima do estoque disponível.",
            )
            subtotal += oferta["preco_centavos"] * item.quantidade
            itens.append((item, oferta["preco_centavos"]))
        resgate = entrada.pontosResgate
        if resgate:
            exigir(
                usuario["perfil"] == "CLIENTE" and consentiu(db, usuario["id"]),
                409,
                "CONSENTIMENTO_NECESSARIO",
                "O resgate exige consentimento vigente do cliente.",
            )
            exigir(
                saldo_pontos(db, usuario["id"]) >= resgate,
                409,
                "PONTOS_INSUFICIENTES",
                "Saldo de pontos insuficiente.",
            )
            exigir(
                resgate <= subtotal // 2,
                409,
                "LIMITE_DESCONTO",
                "O desconto máximo é 50% do subtotal.",
            )
        pedido_id = db.execute(
            "INSERT INTO pedidos (usuario_id,unidade_id,canal,status,subtotal_centavos,desconto_centavos,total_centavos,pontos_resgate,chave,corpo_hash,criado_em) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                usuario["id"],
                entrada.unidadeId,
                entrada.canalPedido.value,
                "AGUARDANDO_PAGAMENTO",
                subtotal,
                resgate,
                subtotal - resgate,
                resgate,
                chave,
                corpo_hash,
                agora(),
            ),
        ).lastrowid
        for item, preco in itens:
            db.execute(
                "INSERT INTO itens_pedido VALUES (?,?,?,?)",
                (pedido_id, item.produtoId, item.quantidade, preco),
            )
            mover_estoque(
                db,
                usuario,
                entrada.unidadeId,
                item.produtoId,
                -item.quantidade,
                "RESERVA_PEDIDO",
                pedido_id,
            )
        if resgate:
            db.execute(
                "INSERT INTO pontos (usuario_id,pedido_id,tipo,quantidade,criado_em) VALUES (?,?,'RESGATE',?,?)",
                (usuario["id"], pedido_id, -resgate, agora()),
            )
        auditar(db, usuario["id"], "CRIAR_PEDIDO", pedido_id)
        return pedido_json(db, pedido_id)


def mover_estoque(
    db, usuario, unidade_id, produto_id, quantidade, motivo, pedido_id=None
):
    oferta = db.execute(
        "SELECT saldo FROM cardapio WHERE unidade_id=? AND produto_id=?",
        (unidade_id, produto_id),
    ).fetchone()
    exigir(
        oferta, 404, "NAO_ENCONTRADO", "Produto não cadastrado no cardápio da unidade."
    )
    exigir(
        oferta["saldo"] + quantidade >= 0,
        409,
        "ESTOQUE_INSUFICIENTE",
        "O saldo não pode ficar negativo.",
    )
    db.execute(
        "UPDATE cardapio SET saldo=saldo+? WHERE unidade_id=? AND produto_id=?",
        (quantidade, unidade_id, produto_id),
    )
    db.execute(
        "INSERT INTO movimentos_estoque (unidade_id,produto_id,pedido_id,usuario_id,quantidade,motivo,criado_em) VALUES (?,?,?,?,?,?,?)",
        (unidade_id, produto_id, pedido_id, usuario["id"], quantidade, motivo, agora()),
    )
    auditar(db, usuario["id"], "MOVIMENTAR_ESTOQUE", f"{unidade_id}/{produto_id}")
    return {
        "unidadeId": unidade_id,
        "produtoId": produto_id,
        "saldo": oferta["saldo"] + quantidade,
    }


def pagar(usuario, pedido_id, entrada, chave):
    falhou = False
    with banco(True) as db:
        pedido = obter(db, "pedidos", pedido_id)
        permitir_pedido(usuario, pedido)
        existente = db.execute(
            "SELECT * FROM pagamentos WHERE pedido_id=? AND chave=?", (pedido_id, chave)
        ).fetchone()
        if existente:
            exigir(
                existente["resultado_solicitado"] == entrada.resultado,
                409,
                "CHAVE_REUTILIZADA",
                "A chave já foi usada com outro resultado.",
            )
            falhou = existente["status"] == "TIMEOUT"
            pagamento = dict(existente)
        else:
            exigir(
                pedido["status"] == "AGUARDANDO_PAGAMENTO",
                409,
                "STATUS_INVALIDO",
                "Pedido não aguarda pagamento.",
            )
            try:
                retorno = GatewayMock().solicitar(
                    pedido_id, pedido["total_centavos"], entrada.resultado
                )
            except TimeoutError:
                retorno = {"status": "TIMEOUT", "referencia": None}
                falhou = True
            pg_id = db.execute(
                "INSERT INTO pagamentos (pedido_id,chave,resultado_solicitado,status,referencia,valor_centavos,criado_em) VALUES (?,?,?,?,?,?,?)",
                (
                    pedido_id,
                    chave,
                    entrada.resultado,
                    retorno["status"],
                    retorno["referencia"],
                    pedido["total_centavos"],
                    agora(),
                ),
            ).lastrowid
            pagamento = dict(obter(db, "pagamentos", pg_id))
            if retorno["status"] == "APROVADO":
                db.execute(
                    "UPDATE pedidos SET status='RECEBIDO' WHERE id=?", (pedido_id,)
                )
            auditar(db, usuario["id"], "PAGAMENTO_" + retorno["status"], pedido_id)
        resposta = {
            "pagamentoId": pagamento["id"],
            "statusPagamento": pagamento["status"],
            "referencia": pagamento["referencia"],
            "valorCentavos": pagamento["valor_centavos"],
            "pedido": pedido_json(db, pedido_id),
        }
    # A falha precisa ser reportada depois do commit do registro de tentativa.
    exigir(
        not falhou,
        503,
        "PAGAMENTO_INDISPONIVEL",
        "Tempo de resposta excedido. Consulte o pedido e tente com nova chave.",
    )
    return resposta


def atualizar_status(usuario, pedido_id, novo):
    with banco(True) as db:
        pedido = obter(db, "pedidos", pedido_id)
        permitir_pedido(usuario, pedido)
        if usuario["perfil"] == "CLIENTE":
            exigir(
                novo == "CANCELADO",
                403,
                "SEM_PERMISSAO",
                "Cliente só pode cancelar pedido pendente.",
            )
        if usuario["perfil"] == "COZINHA":
            exigir(
                novo in {"EM_PREPARO", "PRONTO"},
                403,
                "SEM_PERMISSAO",
                "Cozinha pode iniciar e concluir o preparo.",
            )
        exigir(
            novo in TRANSICOES[pedido["status"]],
            409,
            "STATUS_INVALIDO",
            "Transição de status não permitida.",
        )
        db.execute("UPDATE pedidos SET status=? WHERE id=?", (novo, pedido_id))
        if novo == "CANCELADO":
            for item in db.execute(
                "SELECT * FROM itens_pedido WHERE pedido_id=?", (pedido_id,)
            ).fetchall():
                mover_estoque(
                    db,
                    usuario,
                    pedido["unidade_id"],
                    item["produto_id"],
                    item["quantidade"],
                    "CANCELAMENTO",
                    pedido_id,
                )
            if pedido["pontos_resgate"]:
                db.execute(
                    "INSERT INTO pontos (usuario_id,pedido_id,tipo,quantidade,criado_em) VALUES (?,?,'ESTORNO',?,?)",
                    (
                        pedido["usuario_id"],
                        pedido_id,
                        pedido["pontos_resgate"],
                        agora(),
                    ),
                )
        if novo == "ENTREGUE" and consentiu(db, pedido["usuario_id"]):
            # Um ponto por real efetivamente pago, somente depois da entrega.
            db.execute(
                "INSERT INTO pontos (usuario_id,pedido_id,tipo,quantidade,criado_em) VALUES (?,?,'CREDITO',?,?)",
                (
                    pedido["usuario_id"],
                    pedido_id,
                    pedido["total_centavos"] // 100,
                    agora(),
                ),
            )
        auditar(db, usuario["id"], "STATUS_" + novo, pedido_id)
        return pedido_json(db, pedido_id)
