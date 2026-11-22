"""Usa respostas reais do Newman para documentar contratos e evidências."""

import json
import re
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.main import app


def main():
    arquivo = ROOT / "docs/evidencias/newman.json"
    relatorio = json.loads(arquivo.read_text(encoding="utf-8"))
    spec = app.openapi()
    exemplos = {}
    evidencias = []
    linhas = [
        "# Contratos da API",
        "",
        "Exemplos abaixo foram obtidos na execução local da coleção. O Swagger contém os tipos, limites e campos obrigatórios. Todos os valores monetários são inteiros em centavos. Tokens foram omitidos.",
        "",
    ]
    for execucao in relatorio["run"]["executions"]:
        request = execucao["request"]
        metodo = request["method"].lower()
        url = request["url"]
        caminho = "/" + "/".join(url["path"])
        rota = next(
            (
                p
                for p in spec["paths"]
                if re.fullmatch(re.sub(r"\{[^}]+\}", r"[^/]+", p), caminho)
                and metodo in spec["paths"][p]
            ),
            None,
        )
        if not rota:
            continue
        status = str(execucao["response"]["code"])
        resposta = json.loads(
            bytes(execucao["response"]["stream"]["data"]).decode("utf-8")
        )
        if "accessToken" in resposta:
            resposta["accessToken"] = "TOKEN_JWT_OMITIDO"
        corpo = request.get("body", {}).get("raw")
        chave = metodo.upper() + " " + rota
        exemplos.setdefault(chave, {})
        exemplos[chave].setdefault(status, resposta)
        evidencias.append(
            {
                "cenario": execucao["item"]["name"],
                "metodo": metodo.upper(),
                "rota": caminho,
                "status": int(status),
                "assercoes": len(execucao.get("assertions", [])),
                "falhas": [
                    a["assertion"]
                    for a in execucao.get("assertions", [])
                    if a.get("error")
                ],
                "resposta": resposta,
            }
        )
        # Marcador removido na escrita, mantém um contrato por método/rota.
        marcador = (chave,)
        if marcador not in linhas:
            linhas.extend(
                [
                    marcador,
                    "## " + chave,
                    "",
                    "Permissão — " + permissao(rota, metodo),
                    "",
                    "Parâmetros — "
                    + ", ".join(
                        p["name"] + " (" + p["in"] + ")"
                        for p in spec["paths"][rota][metodo].get("parameters", [])
                    ),
                    "",
                    "Request",
                    "```json",
                    corpo or "{}",
                    "```",
                    "",
                    f"Response HTTP {status}",
                    "```json",
                    json.dumps(resposta, ensure_ascii=False, indent=2),
                    "```",
                    "",
                ]
            )
    # Erros de contrato ficam documentados em cada operação no Swagger.
    for rota, metodos in spec["paths"].items():
        for metodo, op in metodos.items():
            for status, exemplo in exemplos.get(
                metodo.upper() + " " + rota, {}
            ).items():
                op.setdefault("responses", {}).setdefault(
                    status, {"description": "Resposta observada"}
                )
                op["responses"][status].setdefault("content", {}).setdefault(
                    "application/json", {}
                )["example"] = exemplo
    (ROOT / "docs/api_examples.json").write_text(
        json.dumps(exemplos, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (ROOT / "docs/openapi.json").write_text(
        json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (ROOT / "docs/endpoints.md").write_text(
        "\n".join(l for l in linhas if isinstance(l, str)), encoding="utf-8"
    )
    resumo = {
        "ferramenta": "Newman",
        "inicio": relatorio["run"]["timings"]["started"],
        "requisicoes": len(evidencias),
        "assercoes": relatorio["run"]["stats"]["assertions"]["total"],
        "falhas": relatorio["run"]["stats"]["assertions"]["failed"],
        "execucoes": evidencias,
    }
    (ROOT / "docs/evidencias/colecao_resultado.json").write_text(
        json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"{len(exemplos)} contratos, {len(evidencias)} cenários documentados.")


def permissao(rota, metodo):
    if (
        rota in ["/health", "/auth/login"]
        or (
            metodo == "get"
            and rota in ["/unidades", "/produtos", "/unidades/{unidade_id}/cardapio"]
        )
        or (rota == "/usuarios" and metodo == "post")
    ):
        return "Público."
    if rota in [
        "/unidades",
        "/unidades/{unidade_id}",
        "/produtos",
        "/produtos/{produto_id}",
        "/auditoria",
    ]:
        return "JWT, ADMIN."
    if "/estoque" in rota or ("/cardapio/" in rota) or rota == "/relatorios/vendas":
        return "JWT, ADMIN ou GERENTE da unidade. ADMIN acessa todas as unidades."
    if rota.startswith("/fidelidade"):
        return "JWT, CLIENTE, somente os próprios dados."
    if metodo == "post":
        return "JWT, CLIENTE proprietário, ATENDENTE ou GERENTE da unidade, ou ADMIN."
    return "JWT. CLIENTE vê seus pedidos e cancela pendentes. Equipe opera na própria unidade. COZINHA altera para EM_PREPARO ou PRONTO. ADMIN acessa todas."


if __name__ == "__main__":
    main()
