# Análise do projeto

## Contexto e objetivo

No estudo de caso, cada loja da rede Raízes do Nordeste tem seu próprio cardápio e estoque. Um pedido pode vir do aplicativo, do totem, do balcão, da retirada ou da web. Todos passam pela mesma API, que guarda de onde cada pedido veio.

O foco do trabalho foi fazer o caminho do pedido funcionar até a entrega. O cliente escolhe os itens do cardápio ou o atendente registra a venda na loja. A cozinha atualiza o preparo, o gerente acompanha a unidade e o administrador pode consultar a rede.

## Requisitos funcionais

| ID | Requisito | Situação |
|---|---|---|
| RF01 | Cadastrar cliente e autenticar usuário com perfil | Implementado |
| RF02 | Cadastrar, consultar e alterar unidades | Implementado, ADMIN |
| RF03 | Cadastrar produtos e definir preço/disponibilidade por unidade | Implementado |
| RF04 | Consultar cardápio específico da unidade | Implementado |
| RF05 | Criar pedido com itens, total calculado e canal obrigatório | Implementado |
| RF06 | Consultar pedidos por canal, status e página | Implementado |
| RF07 | Reservar estoque e impedir quantidade acima do saldo | Implementado |
| RF08 | Registrar entrada ou saída de estoque com motivo | Implementado |
| RF09 | Solicitar pagamento simulado e registrar aprovação, recusa ou indisponibilidade | Implementado |
| RF10 | Controlar a sequência de status e cancelar pedido pendente | Implementado |
| RF11 | Registrar consentimento e revogação para fidelidade | Implementado |
| RF12 | Acumular pontos na entrega e resgatar desconto simples | Implementado |
| RF13 | Registrar auditoria de ações sensíveis | Implementado |
| RF14 | Consolidar receita entregue por unidade, região e canal | Implementado em relatório básico |
| RF15 | Campanhas por frequência e perfil | Proposto |
| RF16 | Controlar ingredientes, receitas regionais e sazonalidade automática | Proposto |
| RF17 | Solicitar anonimização e controlar retenção de dados | Proposto, política descrita abaixo |

## Requisitos não funcionais

| ID | Requisito e critério de verificação | Situação |
|---|---|---|
| RNF01 | Senhas com salt aleatório e scrypt, sem exposição nos responses | Implementado |
| RNF02 | JWT com expiração e autorização por perfil, proprietário e unidade | Implementado e testado |
| RNF03 | Transação atômica para itens, pedido, reserva e resgate | Implementado e testado |
| RNF04 | Repetição de chamada crítica preserva a operação original | Implementado com chaves únicas e hash do corpo |
| RNF05 | Erros em JSON com código, mensagem, detalhes, horário e caminho | Implementado |
| RNF06 | Contrato OpenAPI e exemplos de entradas e saídas | Implementado |
| RNF07 | Operações sensíveis registram usuário, ação, recurso e horário | Implementado |
| RNF08 | Suportar pico de 100 usuários simultâneos, p95 de leitura até 500 ms | Meta futura, requer teste de carga |
| RNF09 | Disponibilidade mensal de 99,5%, backups e restauração verificada | Meta futura de implantação |
| RNF10 | Recuperar falhas de integração com timeout, retentativa e conciliação | Timeout e retentativa simulados; conciliação proposta |

Os testes locais cobrem o fluxo da API e verificam o que acontece quando dois pedidos disputam o mesmo estoque. As metas de desempenho e disponibilidade ainda precisam ser avaliadas em um ambiente de produção.

## Decisões e regras

A aplicação roda como um único serviço. O código foi dividido entre rotas, regras de negócio e acesso ao banco para facilitar a leitura. O FastAPI valida os dados recebidos e oferece o Swagger para testar as rotas. O SQLite usa um arquivo local, e a estrutura das tabelas fica nas migrações SQL.

O banco possui chaves estrangeiras, restrições CHECK e índices únicos. Toda conexão habilita foreign_keys. Escritas usam BEGIN IMMEDIATE, que serializa as transações de gravação. O modo WAL facilita leituras durante gravações. Esse modelo atende à demonstração local. Para expansão com múltiplos servidores, a proposta é migrar para PostgreSQL, rever bloqueios e validar carga (SQLITE, s.d.).

Um mesmo produto pode ter preços e saldos diferentes em cada loja. Quando alguém faz um pedido, a API copia o preço atual do cardápio para o item do pedido. Assim, se o preço mudar no dia seguinte, o pedido mantém o valor da compra. Um produto indisponível no cardápio da loja fica fora de novas vendas.

O pedido começa em AGUARDANDO_PAGAMENTO. Aprovação permite RECEBIDO. Depois são permitidos EM_PREPARO, PRONTO e ENTREGUE, nessa ordem. O cancelamento é permitido no estado inicial. A reserva fica pendente até pagamento ou cancelamento manual. Expiração automática da reserva é uma evolução necessária para evitar retenção prolongada de estoque.

Ao criar um pedido, o cliente envia uma chave de idempotência que fica vinculada à sua conta. Se a conexão cair e ele enviar os mesmos dados com a mesma chave, recebe o pedido que já foi criado. Se mandar dados diferentes com essa chave, recebe um erro `409`. No pagamento, a chave vale por pedido e o banco limita cada pedido a um pagamento aprovado.

O `GatewayMock` simula o serviço de pagamento. Na requisição dá para escolher se o pagamento foi aprovado, recusado ou se o serviço ficou indisponível. O `TIMEOUT` simulado registra a tentativa sem cobrança. Com um provedor real, seria preciso consultar o resultado e conciliar a cobrança, pois a confirmação pode se perder mesmo quando o valor foi cobrado.

## Funcionalidade crítica

O caso de uso UC01 cobre criar o pedido e pagar. O cliente ou o atendente precisa estar logado. A unidade precisa estar ativa, com o produto no cardápio e saldo suficiente. O atendente precisa estar vinculado à loja, e o cliente só pode usar pontos com consentimento ativo.

O fluxo segue esta ordem.

1. O consumidor consulta o cardápio da unidade.
2. Envia unidade, canal, itens e uma chave de idempotência.
3. A API confere os dados, calcula o total e grava o pedido junto com a reserva do estoque.
4. O consumidor solicita o pagamento simulado e manda outra chave de idempotência.
5. O adaptador confirma a aprovação e o pedido passa para RECEBIDO.
6. A cozinha inicia e termina o preparo. A operação confirma a entrega.
7. O sistema credita pontos quando houver consentimento vigente.

No fim, ficam registrados o canal, o preço de cada item, o pagamento e as ações feitas no pedido. O estoque reservado é consumido.

Exceções. Produto/unidade ausente gera 404. Saldo insuficiente gera 409. Canal ausente ou inválido gera 422. Token ausente gera 401 e perfil/unidade proibidos geram 403. Pagamento recusado retorna 200 com status RECUSADO e mantém o pedido pendente. Timeout retorna 503 e registra a tentativa. Cancelamento pendente devolve a reserva. Falha de um item invalida toda a criação.

## Fidelidade e campanhas

A regra simples dá um ponto por real pago na entrega. Cada ponto pode descontar um centavo em pedido futuro, até metade do subtotal. O saldo é um extrato de créditos, resgates e estornos. O resgate é reservado junto do pedido e devolvido no cancelamento pendente.

A proposta de campanhas prevê data inicial e final, unidades participantes, produtos elegíveis e limite de desconto. A elegibilidade usaria frequência de compras e consentimento de marketing específico, com registro da regra aplicada no pedido. Essas campanhas e descontos progressivos ainda precisam ser implementados. Dados de idade foram deixados fora do cadastro por falta de necessidade no fluxo entregue.

## Privacidade, segurança e LGPD

O cadastro coleta nome, e-mail e senha. Nome e e-mail identificam a conta e permitem autenticação e acompanhamento do pedido. O banco guarda apenas hash da senha com salt. A base legal proposta para dados necessários à compra e à conta é execução de contrato, conforme art. 7º, V. O consentimento específico é usado para fidelidade opcional, conforme art. 7º, I. A aplicação registra finalidade FIDELIDADE, aceite, versão do aviso e horário, e permite revogação pela mesma rota. O aviso correspondente é a regra de pontos descrita neste material. Um produto publicado precisará apresentar esse aviso ao titular antes do aceite (BRASIL, 2018).

O projeto usa contas fictícias. Os endpoints de pedidos aplicam controle por proprietário. Funcionários atuam na unidade vinculada e somente ADMIN acessa a auditoria completa. JWT contém ID e datas, com perfil consultado no banco a cada requisição. Responses não incluem hashes. Auditoria armazena IDs e ações, sem senha, token ou dados de cartão. Consultas de fidelidade, auditoria e vendas são registradas.

A proposta de retenção prevê revisão e eliminação dos cadastros inativos após 24 meses, respeitando obrigações legais a serem definidas com o responsável pela rede. O prazo é uma escolha inicial do projeto e precisa de validação. Pedidos necessários a obrigações legais seriam preservados pelo prazo aplicável e desvinculados da conta quando possível. Identificadores reversíveis representam pseudonimização e exigem proteção de acesso. Uma anonimização efetiva precisará considerar os riscos de reidentificação. A API entregue ainda exige operação administrativa para atender exclusão e anonimização.

Para implantação, ficam pendentes HTTPS, limitação de tentativas de login, gestão de segredos, monitoramento, backup protegido e procedimento para direitos do titular. A implementação demonstra controles de privacidade e segurança, com avaliação adicional necessária antes de usar dados reais.

## O que ficou para depois

Ainda falta liberar automaticamente o estoque de pedidos que ficam sem pagamento, estornar pagamentos aprovados e cadastrar a equipe por unidade. Outra melhoria seria vincular as vendas do balcão à conta do cliente. O relatório de vendas já agrupa os pedidos entregues, mas ainda pode ganhar um filtro de período e uma lista dos produtos mais vendidos.

Antes de usar a API em várias unidades ao mesmo tempo, seria preciso testar a carga, migrar o banco e integrar um serviço real de pagamento.

## Referências

BRASIL. Lei nº 13.709, de 14 de agosto de 2018. Lei Geral de Proteção de Dados Pessoais. Texto atualizado. Disponível em https://www2.camara.leg.br/legin/fed/lei/2018/lei-13709-14-agosto-2018-787077-normaatualizada-pl.html. Acesso em 9 nov. 2026.

FASTAPI. OAuth2 with Password and Bearer with JWT tokens. Disponível em https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/. Acesso em 9 nov. 2026.

SQLITE. Transaction. Disponível em https://www.sqlite.org/lang_transaction.html. Acesso em 9 nov. 2026.

ALMEIDA, Giuliano Lanes de et al. Projeto Multidisciplinar — Orientações e Estudo de Caso. Rede Raízes do Nordeste. Material da disciplina, 2026.

KANASHIRO, Luciane Yanase. Roteiro de Atividade Prática — Projeto Multidisciplinar, Trilha Back-End. Material da disciplina, 2026.
