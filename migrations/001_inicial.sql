CREATE TABLE unidades (
 id INTEGER PRIMARY KEY, nome TEXT NOT NULL, regiao TEXT NOT NULL,
 ativa INTEGER NOT NULL CHECK(ativa IN (0,1))
);
CREATE TABLE usuarios (
 id INTEGER PRIMARY KEY, nome TEXT NOT NULL, email TEXT NOT NULL UNIQUE,
 senha_hash TEXT NOT NULL,
 perfil TEXT NOT NULL DEFAULT 'CLIENTE' CHECK(perfil IN ('CLIENTE','ATENDENTE','COZINHA','GERENTE','ADMIN')),
 unidade_id INTEGER REFERENCES unidades(id)
);
CREATE TABLE produtos (id INTEGER PRIMARY KEY, nome TEXT NOT NULL);
CREATE TABLE cardapio (
 unidade_id INTEGER NOT NULL REFERENCES unidades(id),
 produto_id INTEGER NOT NULL REFERENCES produtos(id),
 preco_centavos INTEGER NOT NULL CHECK(preco_centavos > 0),
 disponivel INTEGER NOT NULL CHECK(disponivel IN (0,1)),
 saldo INTEGER NOT NULL DEFAULT 0 CHECK(saldo >= 0),
 PRIMARY KEY(unidade_id,produto_id)
);
CREATE TABLE pedidos (
 id INTEGER PRIMARY KEY, usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
 unidade_id INTEGER NOT NULL REFERENCES unidades(id),
 canal TEXT NOT NULL CHECK(canal IN ('APP','TOTEM','BALCAO','PICKUP','WEB')),
 status TEXT NOT NULL CHECK(status IN ('AGUARDANDO_PAGAMENTO','RECEBIDO','EM_PREPARO','PRONTO','ENTREGUE','CANCELADO')),
 subtotal_centavos INTEGER NOT NULL CHECK(subtotal_centavos > 0),
 desconto_centavos INTEGER NOT NULL CHECK(desconto_centavos >= 0),
 total_centavos INTEGER NOT NULL CHECK(total_centavos > 0),
 pontos_resgate INTEGER NOT NULL DEFAULT 0,
 chave TEXT NOT NULL, corpo_hash TEXT NOT NULL, criado_em TEXT NOT NULL,
 UNIQUE(usuario_id,chave)
);
CREATE TABLE itens_pedido (
 pedido_id INTEGER NOT NULL REFERENCES pedidos(id),
 produto_id INTEGER NOT NULL REFERENCES produtos(id),
 quantidade INTEGER NOT NULL CHECK(quantidade > 0),
 preco_centavos INTEGER NOT NULL CHECK(preco_centavos > 0),
 PRIMARY KEY(pedido_id,produto_id)
);
CREATE TABLE movimentos_estoque (
 id INTEGER PRIMARY KEY, unidade_id INTEGER NOT NULL, produto_id INTEGER NOT NULL,
 pedido_id INTEGER REFERENCES pedidos(id), usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
 quantidade INTEGER NOT NULL CHECK(quantidade != 0), motivo TEXT NOT NULL, criado_em TEXT NOT NULL,
 FOREIGN KEY(unidade_id,produto_id) REFERENCES cardapio(unidade_id,produto_id)
);
CREATE TABLE pagamentos (
 id INTEGER PRIMARY KEY, pedido_id INTEGER NOT NULL REFERENCES pedidos(id),
 chave TEXT NOT NULL, resultado_solicitado TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('APROVADO','RECUSADO','TIMEOUT')),
 referencia TEXT, valor_centavos INTEGER NOT NULL, criado_em TEXT NOT NULL,
 UNIQUE(pedido_id,chave)
);
CREATE UNIQUE INDEX um_pagamento_aprovado ON pagamentos(pedido_id) WHERE status='APROVADO';
CREATE TABLE consentimentos (
 id INTEGER PRIMARY KEY, usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
 finalidade TEXT NOT NULL, aceito INTEGER NOT NULL CHECK(aceito IN (0,1)),
 versao TEXT NOT NULL, criado_em TEXT NOT NULL
);
CREATE TABLE pontos (
 id INTEGER PRIMARY KEY, usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
 pedido_id INTEGER NOT NULL REFERENCES pedidos(id),
 tipo TEXT NOT NULL CHECK(tipo IN ('CREDITO','RESGATE','ESTORNO')),
 quantidade INTEGER NOT NULL, criado_em TEXT NOT NULL, UNIQUE(pedido_id,tipo)
);
CREATE TABLE auditoria (
 id INTEGER PRIMARY KEY, usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
 acao TEXT NOT NULL, recurso TEXT NOT NULL, criado_em TEXT NOT NULL
);
CREATE INDEX pedidos_filtro ON pedidos(usuario_id,canal,status);
CREATE INDEX pedidos_unidade ON pedidos(unidade_id,criado_em);
CREATE INDEX consentimento_recente ON consentimentos(usuario_id,id DESC);
