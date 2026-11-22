# Raízes do Nordeste

Este projeto é a API de uma rede de lanchonetes. Dá para consultar o cardápio de cada unidade, fazer um pedido, simular o pagamento e acompanhar até a entrega. Cada unidade tem seu próprio estoque e o pedido guarda o canal de origem (`APP`, `TOTEM`, `BALCAO`, `PICKUP` ou `WEB`).

A API foi feita com Python e FastAPI. O banco é SQLite, então dá para rodar tudo localmente com o Python.

## Executar no Windows

Você vai precisar do Python 3.13 e de internet para instalar as dependências. O Node.js 22 ou superior é usado para rodar o Newman e gerar as imagens dos diagramas.

Na primeira vez, abra o PowerShell na pasta do projeto e rode os comandos abaixo. Eles usam o Python da `.venv` diretamente.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
.\.venv\Scripts\python.exe -c "import secrets; from pathlib import Path; p=Path('.env'); p.write_text(p.read_text().replace('troque-esta-chave-antes-de-iniciar-a-api', secrets.token_urlsafe(48)), encoding='utf-8')"
.\.venv\Scripts\python.exe -m app.infrastructure --seed
.\.venv\Scripts\python.exe -m uvicorn app.main:app
```

O `.env` fica na sua máquina. A API precisa de uma chave própria para iniciar, por isso o comando troca a chave de exemplo. Nas próximas vezes, basta rodar a última linha para subir a API.

Em Linux ou macOS, substitua `.venv\Scripts\python.exe` por `.venv/bin/python` e use `cp .env.example .env` para copiar o arquivo.

Com a API rodando, abra o [Swagger](http://127.0.0.1:8000/docs) no navegador para testar as rotas. O [contrato em JSON](http://127.0.0.1:8000/openapi.json) lista os detalhes da API. A [rota de saúde](http://127.0.0.1:8000/health) responde `{"status":"ok"}` quando a API e o banco estão funcionando.

O `--seed` cadastra as contas de teste e o estoque inicial. Dá para repetir esse comando, pois ele preserva os pedidos e os saldos que já existem. Para aplicar só as migrações SQL, rode `.\.venv\Scripts\python.exe -m app.infrastructure`.

## Contas de demonstração

| E-mail | Senha | Perfil | Unidade |
|---|---|---|---|
| cliente@raizes.local | Cliente@123 | CLIENTE | Pedidos próprios |
| admin@raizes.local | Admin@123 | ADMIN | Todas |
| gerente@raizes.local | Gerente@123 | GERENTE | 1 |
| cozinha@raizes.local | Cozinha@123 | COZINHA | 1 |
| atendente@raizes.local | Atendente@123 | ATENDENTE | 1 |

Essas contas são para testar a API. O cadastro público cria contas de cliente. As contas de funcionários já vêm no seed.

## Testar pelo Swagger

1. Execute `POST /auth/login` com uma conta da tabela e copie `accessToken`.
2. Clique em **Authorize** e cole o token.
3. Consulte `GET /unidades/1/cardapio`.
4. Execute `POST /pedidos` com `Idempotency-Key` igual a `meu-pedido-001` e o corpo abaixo.

```json
{
  "unidadeId": 1,
  "canalPedido": "APP",
  "itens": [{"produtoId": 1, "quantidade": 1}],
  "pontosResgate": 0
}
```

5. Use o `pedidoId` retornado em `POST /pedidos/{pedido_id}/pagamentos`. Envie `{"resultado":"APROVADO"}` e outra chave, como `meu-pagamento-001`.
6. Faça login como cozinha e altere o pedido para `EM_PREPARO` e depois `PRONTO` usando `PATCH /pedidos/{pedido_id}/status`.
7. Faça login como gerente e altere para `ENTREGUE`.

Todos os valores monetários são inteiros em centavos. Um cuscuz da unidade 1 custa `1200`, equivalente a R$ 12,00. O servidor calcula os preços e o total. O cliente envia produto e quantidade.

## Coleção Postman e evidências

Importe `postman/raizes.postman_collection.json` no Postman e execute todas as pastas em ordem no Collection Runner. A variável `baseUrl` já aponta para `http://127.0.0.1:8000`. Os primeiros passos guardam tokens e os pedidos guardam seus IDs. As chaves de idempotência recebem um identificador de execução.

O banco inicial tem estoque para executar a coleção. Cada execução completa consome um cuscuz. Para uma reprodução isolada, use outro caminho de banco em `DATABASE_PATH` antes do seed e da inicialização. A variável de ambiente do processo tem prioridade sobre o arquivo `.env`.

Também é possível executar com Newman, em outro terminal, mantendo a API aberta.

```powershell
npx.cmd --yes newman run postman/raizes.postman_collection.json --reporters cli,json --reporter-json-export docs/evidencias/newman.json
```

Os testes automatizados usam bancos temporários independentes.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Os resultados de uma execução local estão em `docs/evidencias/`. Em `colecao_resultado.json` dá para ver as requisições e as respostas da coleção com os tokens omitidos. O resultado do pytest está em `pytest.txt` e o roteiro dos testes, em `docs/plano_testes.md`. Os oito prints do Postman estão em [docs/evidencias/postman/](docs/evidencias/postman/).

## Organização

| Pasta ou arquivo | Responsabilidade |
|---|---|
| app/domain.py | Contratos de entrada, enums, validações e transições |
| app/application.py | Fluxo de pedido, pagamento, estoque e pontos |
| app/infrastructure.py | Conexões SQLite, migrações, senhas, auditoria e mock |
| app/main.py | Rotas, autenticação, autorização e respostas HTTP |
| migrations/ | Modelo SQL versionado |
| tests/ | Testes de integração e consistência |
| postman/ | Coleção executável |
| docs/diagramas/ | DER, classes, casos de uso, arquitetura e atividade, em PNG e DOT |
| docs/analise.md | Requisitos, decisões, regras e limites do recorte |
| docs/endpoints.md | Exemplos de request e response obtidos na execução |
| docs/openapi.json | Cópia do contrato para consulta sem iniciar a API |

As rotas estão em `app/main.py`. Para mudar uma regra de pedido, pagamento ou estoque, o primeiro lugar para olhar é `app/application.py`. As rotas mais simples do catálogo consultam o banco diretamente pela função de `app/infrastructure.py`.

## Regras principais

- O estoque representa unidades de produto pronto. Ingredientes e fichas técnicas ficam como evolução.
- A criação do pedido reserva estoque em transação. O cancelamento pendente devolve a reserva uma única vez.
- `Idempotency-Key` é obrigatório para criar pedido e solicitar pagamento. Mesma chave e conteúdo retornam a operação existente. Conteúdo diferente retorna 409.
- Pagamento aprovado muda o pedido para RECEBIDO. Recusa mantém AGUARDANDO_PAGAMENTO e permite outra tentativa com nova chave.
- TIMEOUT registra a tentativa e retorna 503. A simulação garante que esse resultado representa uma tentativa sem cobrança.
- O cancelamento está disponível enquanto o pedido aguarda pagamento. Estorno financeiro de pedidos aprovados ficou como proposta.
- Com consentimento vigente, cada real efetivamente pago gera um ponto na entrega. Cada ponto resgatado vale um centavo, limitado a 50% do subtotal. O pedido reserva o resgate e o cancelamento devolve os pontos.
- O atendente registra a venda em seu próprio usuário operacional. Identificação do consumidor em pedidos assistidos e associação de fidelidade ficam como evolução.

## Documentação do trabalho

Em `docs/analise.md` estão os requisitos, as decisões e o que ficou para depois. Os exemplos de chamadas estão em `docs/endpoints.md`. As imagens em `docs/diagramas/` ajudam a entender as tabelas do banco, os perfis de usuário e as etapas do pedido.

## Regenerar os materiais

```powershell
.\.venv\Scripts\python.exe scripts/gerar_colecao.py
npm.cmd install --prefix tmp/diagramas @viz-js/viz sharp
node scripts/renderizar_diagramas.cjs
```

Para atualizar exemplos e evidências, execute Newman com `--reporter-json-export docs/evidencias/newman.json` e depois `python scripts/exportar_documentacao.py`. O exportador produz um resumo com tokens omitidos. O relatório bruto contém tokens de demonstração e deve ficar apenas no ambiente local.
