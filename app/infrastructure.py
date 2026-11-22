"""SQLite, migrações, senhas e adaptador de pagamento de demonstração."""

import hashlib
import hmac
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
ROOT = Path(__file__).resolve().parent.parent


def agora():
    return datetime.now(timezone.utc).isoformat()


def senha_hash(senha):
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(senha.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1)
    return salt + ":" + digest.hex()


def conferir_senha(senha, armazenada):
    salt, esperado = armazenada.split(":")
    digest = hashlib.scrypt(senha.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1)
    return hmac.compare_digest(digest.hex(), esperado)


@contextmanager
def banco(escrita=False):
    caminho = Path(os.getenv("DATABASE_PATH", "data/raizes.db"))
    caminho.parent.mkdir(parents=True, exist_ok=True)
    conexao = sqlite3.connect(caminho, timeout=10)
    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA foreign_keys = ON")
    try:
        if escrita:
            conexao.execute("BEGIN IMMEDIATE")
        yield conexao
        conexao.commit()
    except Exception:
        conexao.rollback()
        raise
    finally:
        conexao.close()


def migrar():
    with banco() as db:
        db.execute("PRAGMA journal_mode = WAL")
        db.execute("CREATE TABLE IF NOT EXISTS migrations (nome TEXT PRIMARY KEY)")
        for arquivo in sorted((ROOT / "migrations").glob("*.sql")):
            if not db.execute(
                "SELECT 1 FROM migrations WHERE nome=?", (arquivo.name,)
            ).fetchone():
                script = arquivo.read_text(encoding="utf-8")
                db.executescript("BEGIN IMMEDIATE;\n" + script)
                db.execute("INSERT INTO migrations VALUES (?)", (arquivo.name,))
                db.commit()


class GatewayMock:
    """Substitui o fornecedor externo por resultados determinísticos, sem rede."""

    def solicitar(self, pedido_id, valor_centavos, resultado):
        if resultado == "TIMEOUT":
            raise TimeoutError("Provedor simulado indisponível.")
        return {
            "referencia": "mock-" + secrets.token_hex(8),
            "pedidoId": pedido_id,
            "valorCentavos": valor_centavos,
            "status": resultado,
        }


def auditar(db, usuario_id, acao, recurso):
    db.execute(
        "INSERT INTO auditoria (usuario_id,acao,recurso,criado_em) VALUES (?,?,?,?)",
        (usuario_id, acao, str(recurso), agora()),
    )


def seed():
    migrar()
    with banco(True) as db:
        for nome, email, perfil, unidade, senha in [
            ("Cliente exemplo", "cliente@raizes.local", "CLIENTE", None, "Cliente@123"),
            ("Administrador exemplo", "admin@raizes.local", "ADMIN", None, "Admin@123"),
            ("Cozinha Recife", "cozinha@raizes.local", "COZINHA", 1, "Cozinha@123"),
            ("Gerente Recife", "gerente@raizes.local", "GERENTE", 1, "Gerente@123"),
            (
                "Atendente Recife",
                "atendente@raizes.local",
                "ATENDENTE",
                1,
                "Atendente@123",
            ),
        ]:
            # Unidades devem existir antes dos usuários vinculados a elas.
            db.execute(
                "INSERT OR IGNORE INTO unidades VALUES (1,'Recife Centro','Nordeste',1)"
            )
            db.execute(
                "INSERT OR IGNORE INTO unidades VALUES (2,'Caruaru','Nordeste',1)"
            )
            db.execute(
                "INSERT OR IGNORE INTO usuarios (nome,email,senha_hash,perfil,unidade_id) VALUES (?,?,?,?,?)",
                (nome, email, senha_hash(senha), perfil, unidade),
            )
        db.execute("INSERT OR IGNORE INTO produtos VALUES (1,'Cuscuz recheado')")
        db.execute("INSERT OR IGNORE INTO produtos VALUES (2,'Tapioca de queijo')")
        for unidade, produto, preco, saldo in [
            (1, 1, 1200, 100),
            (1, 2, 1000, 80),
            (2, 1, 1300, 40),
        ]:
            db.execute(
                "INSERT OR IGNORE INTO cardapio VALUES (?,?,?,?,?)",
                (unidade, produto, preco, 1, saldo),
            )


if __name__ == "__main__":
    import sys

    if "--seed" in sys.argv:
        seed()
        print("Migrações e seed concluídos. Contas de demonstração criadas.")
    else:
        migrar()
        print("Migrações concluídas.")
