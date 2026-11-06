# SIM --- Planejamento Enxuto

## Gestor pessoal de investimentos com análise por IA

**Versão:** 2.0\
**Data:** 06/11/2026\
**Escopo:** aplicação local para Windows, uso individual, mercados do
Brasil e dos Estados Unidos, IA por API.

## 1. Objetivo

O SIM será um aplicativo pessoal para: - Gerenciar carteira, ativos,
compras, vendas, proventos, posições e rentabilidade. - Analisar ativos
comparando preço atual, histórico, indicadores e fundamentos
disponíveis. - Acompanhar notícias relevantes do Brasil e dos Estados
Unidos. - Identificar situações que merecem investigação como possíveis
oportunidades. - Gerar relatórios gerenciais e análises de IA da
carteira e de ativos.

O SIM não será uma corretora, plataforma de trading ou sistema de
execução automática de ordens.

## 2. Decisões confirmadas

  -----------------------------------------------------------------------
  Tema                                Decisão
  ----------------------------------- -----------------------------------
  Código                              Reaproveitar o máximo possível do
                                      SIM existente

  Plataforma                          Somente PC Windows

  Uso                                 Local, individual

  Mercados                            Brasil e Estados Unidos

  IA                                  API externa

  Banco                               Manter o atual se adequado; não
                                      migrar sem motivo

  Internet                            Para cotações, notícias e IA

  Offline                             Consultar e editar dados locais;
                                      mostrar data da última atualização
                                      externa

  Celular, sincronização e nuvem      Fora do escopo
  própria                             

  Ordens automáticas                  Fora do escopo
  -----------------------------------------------------------------------

**Princípio central:** não reescrever o sistema antes de conhecer o
repositório. Preservar o que funciona e mudar somente o necessário.

## 3. Funcionalidades incluídas

### 3.1 Gestão da carteira

-   Cadastro e consulta de ativos brasileiros e americanos.
-   Registro de compras, vendas e proventos.
-   Quantidade, preço médio, custo investido, posição e valor de
    mercado.
-   Resultados realizados e não realizados, com metodologia explícita.
-   Visão consolidada por ativo, classe, país e moeda.
-   Reaproveitamento das importações/exportações existentes que
    funcionem.
-   Correção manual de lançamentos.

Limitar inicialmente as classes de ativos ao que o SIM já suporta e ao
que o usuário possui. Não criar suporte universal a todos os
instrumentos financeiros.

### 3.2 Dashboard e relatórios

-   Patrimônio total e evolução.
-   Rentabilidade por período e por ativo.
-   Distribuição por ativo, classe, setor, país e moeda, conforme os
    dados existentes.
-   Concentração e maiores posições.
-   Proventos por mês, ano e ativo.
-   Comparação com índices adequados, quando houver dados e metodologia
    confiáveis.
-   Exportação e relatórios existentes, quando aproveitáveis.

Em consolidações BRL/USD, mostrar moeda original, taxa de câmbio e data
de referência.

### 3.3 Análise de ativos

Para cada ativo: - Cotação mais recente, fonte e horário/data. - Gráfico
histórico (ex.: 1 ano, 5 anos e máximo disponível). - Comparação do
preço atual com faixas e médias históricas. - Indicadores e fundamentos
fornecidos por fontes confiáveis. - Comparação com índice de referência
apropriado. - Fatores positivos, riscos e pontos que merecem
investigação.

Distinguir **dado observado**, **cálculo do SIM** e **interpretação da
IA**. Não classificar um ativo como barato/caro apenas por comparação
com a média histórica: considerar fundamentos, eventos corporativos,
juros, inflação e câmbio quando houver dados.

### 3.4 Notícias e radar de oportunidades

-   Notícias relevantes para ativos da carteira e mercados BR/EUA.
-   Título, fonte, data, link e resumo.
-   Associação a ativos/setores somente quando houver evidência.
-   Lista de ativos para acompanhar.
-   Sinais para investigação: variação incomum, região histórica
    relevante, notícia importante, mudança de fundamento ou concentração
    elevada.
-   Marcar itens como relevantes, ignorados ou em acompanhamento.

O radar não emite ordens nem promete retorno. Oportunidade é hipótese
para investigação, não garantia de valorização.

### 3.5 Analista de IA

Ações disponíveis: - Analisar minha carteira: diversificação,
concentração, riscos e pontos fortes. - Analisar este ativo: histórico,
dados recentes, notícias e riscos. - O que mudou desde a última
análise? - O que merece minha atenção? - Comparar ativos semelhantes com
métricas comparáveis.

Toda análise deve indicar data/hora dos dados, fontes e links, dados
ausentes ou desatualizados, riscos e argumentos contrários. Não inventar
números, notícias, indicadores ou fontes. Não executar compras ou
vendas.

Enviar à IA somente o contexto necessário (posições, transações
relevantes, séries, indicadores e notícias). Nunca enviar chaves,
credenciais ou dados pessoais desnecessários.

## 4. Fora do escopo

Não implementar nesta versão: - Android/iOS, sincronização entre
dispositivos ou servidor LAN. - Nuvem própria, multiusuário ou
colaboração. - Execução automática de ordens ou integração operacional
com corretoras. - Monitoramento contínuo em tempo real. - Treinamento de
modelo próprio ou IA local. - Suporte universal a todos os produtos
financeiros. - Migração tecnológica ampla ou reescrita completa sem
necessidade comprovada.

Não remover funcionalidades ou dados existentes sem avaliação,
justificativa e autorização.

## 5. Arquitetura

Decidir após inspecionar o repositório. Preferir manter linguagem,
framework, banco e estrutura atuais.

Princípios: - Aplicação local no Windows e banco local. - Serviços
separados para carteira, cálculos, relatórios e análises. - Adaptadores
independentes para cotações, notícias e IA. - Atualização sob demanda ou
em intervalos moderados. - Cache local, fonte e data de atualização. -
Chaves de API protegidas, fora do código e dos logs. - Falha de internet
não impede acesso aos dados locais.

``` text
Interface Windows
       |
Serviços do SIM
  |       |        |
Carteira Relatórios Análises
       |
Banco local e cache
       |
Integrações externas
  |          |          |
Cotações   Notícias    API de IA
```

Se o projeto já usa Python e uma interface funcional, manter essa base.
Streamlit pode ser avaliado se simplificar de verdade, mas não deve ser
imposto. SQLite pode ser suficiente para uso individual, mas não migrar
apenas por preferência.

## 6. Plano de execução

Cada etapa termina com entrega verificável. Atualizar este arquivo ao
concluir tarefas.

### Etapa 0 --- Diagnóstico e proteção

**Objetivo:** conhecer o SIM atual sem alterar seu funcionamento.

Tarefas: 1. Mapear repositório, tecnologias, dependências e comandos. 2.
Identificar telas e funcionalidades. 3. Identificar banco, tabelas,
relações, importações e exportações. 4. Mapear regras e cálculos
financeiros. 5. Identificar integrações de cotações, notícias e IA. 6.
Executar aplicação e testes existentes; registrar resultados. 7. Criar
backup verificável e instruções de restauração. 8. Criar
`docs/diagnostico-sim.md` com o que preservar, simplificar, corrigir ou
avaliar para remoção.

**Não fazer:** reescrever, migrar banco, trocar framework ou remover
funcionalidades.

**Conclusão:** inventário confiável, estado inicial documentado e
backup/restauração verificados.

**Prompt:**

> Leia `SIM_PLANO_ENXUTO.md`. Faça somente a Etapa 0. Inspecione o
> repositório sem alterar código de produção nem banco de dados.
> Identifique tecnologias, comandos, telas, funcionalidades, tabelas,
> regras financeiras, integrações e testes. Execute a aplicação e os
> testes possíveis. Registre resultados em `docs/diagnostico-sim.md`.
> Não invente informações e não implemente melhorias. Ao final, atualize
> o checklist da Etapa 0 e informe riscos e próxima tarefa recomendada.

### Etapa 1 --- Estabilizar a carteira

Tarefas: 1. Corrigir somente problemas comprovados. 2. Validar cadastro,
compras, vendas e proventos. 3. Conferir quantidade, preço médio, custo,
posição e resultados. 4. Validar taxas, impostos e eventos corporativos
conforme regras existentes. 5. Separar moedas BRL e USD. 6. Definir
metodologia e data de referência do câmbio. 7. Criar testes de regressão
dos cálculos. 8. Melhorar importação/exportação somente se necessário.

**Atenção:** não usar ponto flutuante binário para valores monetários
sem estratégia explícita de precisão/arredondamento. Não alterar regras
financeiras sem documentar e testar.

**Conclusão:** operações e posições conferem com exemplos conhecidos e
testes passam.

**Prompt:**

> Implemente somente a Etapa 1, respeitando `docs/diagnostico-sim.md`.
> Preserve o comportamento financeiro existente, salvo erro comprovado.
> Antes de alterar cálculos, apresente regra atual, problema e regra
> proposta. Crie testes para compras, vendas, proventos, moedas e taxas.
> Não implemente notícias, radar ou IA nesta etapa. Atualize o plano com
> arquivos alterados, testes e pendências.

### Etapa 2 --- Dashboard e relatórios

Tarefas: 1. Organizar tela inicial com patrimônio, resultado e
distribuição. 2. Filtros por período, país, moeda e classe, conforme
dados disponíveis. 3. Evolução patrimonial e rentabilidade. 4.
Composição e concentração. 5. Proventos por período. 6. Mostrar câmbio e
data usados na consolidação. 7. Reaproveitar relatórios/exportações
existentes.

**Conclusão:** totais do dashboard conciliam com registros e posições do
banco.

**Prompt:**

> Implemente somente a Etapa 2. Reaproveite componentes existentes e
> priorize clareza e conferência. Não invente dados. Em valores BRL/USD,
> mostre moeda original, taxa e data. Valide totais contra banco e casos
> de teste. Atualize o plano.

### Etapa 3 --- Dados de mercado, histórico e notícias

Tarefas: 1. Inventariar integrações existentes e testar funcionamento.
2. Definir provedores de preços/histórico para Brasil e EUA. 3. Definir
fonte de câmbio BRL/USD. 4. Definir fonte de notícias com links e datas.
5. Criar adaptadores substituíveis. 6. Armazenar cache, horário, origem
e estado do dado. 7. Falhas externas não podem bloquear consulta da
carteira. 8. Criar detalhe do ativo com gráfico e histórico. 9.
Documentar limites, custos, cobertura e termos dos provedores.

**Conclusão:** pequena seleção de ativos reais dos dois mercados
apresenta fonte, moeda e data identificadas.

**Prompt:**

> Implemente somente a Etapa 3. Reaproveite integrações existentes.
> Antes de escolher provedores, documente cobertura Brasil/EUA, campos,
> limites, custos, autenticação e termos. Não presuma dados gratuitos ou
> em tempo real. Implemente adaptadores, cache e última atualização. O
> app deve exibir dados armazenados se um provedor falhar. Não
> implemente IA ainda. Atualize o plano.

### Etapa 4 --- Radar e analista de IA

Tarefas: 1. Configurar API de IA por mecanismo seguro. 2. Criar tela
para configurar/testar conexão sem exibir chave. 3. Enviar somente dados
necessários a cada análise. 4. Análise de ativo com histórico,
indicadores e notícias. 5. Análise consolidada da carteira. 6.
Comparação entre ativos semelhantes, quando possível. 7. Radar de
notícias/eventos relevantes para carteira e watchlist. 8. Salvar
análises com data, parâmetros, fontes e versão do modelo/prompt quando
disponível. 9. Permitir refazer e comparar análises. 10. Alertar sobre
dados ausentes, antigos ou inconclusivos.

**Conclusão:** análises rastreáveis, com fontes, distinção entre fato e
interpretação e sem dados inventados.

**Prompt:**

> Implemente somente a Etapa 4. Use API configurável; nunca coloque
> chaves no código, frontend ou logs. A IA recebe dados estruturados e
> fontes recuperadas pelo sistema. Não pode inventar cotações,
> fundamentos, notícias ou links. Cada afirmação factual deve ser
> rastreável aos dados fornecidos. Inclua riscos, argumentos contrários
> e limitações. Não execute ordens. Salve histórico das análises. Teste
> dados completos, incompletos, antigos e falhas da API. Atualize o
> plano.

### Etapa 5 --- Acabamento e distribuição

Tarefas: 1. Revisar navegação e mensagens de erro. 2. Criar backup e
restauração simples. 3. Testar recuperação após falha. 4. Configurar
inicialização fácil no Windows. 5. Criar instalador/pacote compatível
com tecnologia atual. 6. Documentar provedores e configuração da chave
de IA. 7. Documentar atualização, backup e restauração. 8. Testar fluxo
completo com carteira real após backup.

**Conclusão:** usuário abre, usa, atualiza, faz backup e restaura sem
ferramentas de desenvolvimento.

**Prompt:**

> Implemente somente a Etapa 5. Não introduza nova arquitetura para
> empacotar. Escolha o método mais simples compatível com o projeto.
> Teste instalação, inicialização, atualização, backup e restauração no
> Windows. Escreva instruções objetivas. Não declare pronto sem executar
> e registrar testes.

## 7. Regras permanentes para agentes de IA

1.  Ler este plano e `docs/diagnostico-sim.md` antes de trabalhar.
2.  Fazer somente a tarefa solicitada.
3.  Reaproveitar código e integrações sempre que viável.
4.  Não reescrever nem trocar tecnologia sem justificativa e
    autorização.
5.  Não apagar dados ou funcionalidades sem autorização.
6.  Não alterar cálculos sem documentar regras e criar testes.
7.  Não inventar números ou fontes.
8.  Não expor chaves de API em código, frontend ou logs.
9.  Tratar falhas de internet como normais e mostrar última atualização.
10. Não implementar celular, sincronização, servidor remoto ou ordens
    automáticas.
11. Justificar dependências novas.
12. Não afirmar que testes passaram se não foram executados.
13. Não fazer commit automaticamente.
14. Ao terminar, informar arquivos alterados, decisões, testes,
    limitações e próxima tarefa.
15. Atualizar checklists sem apagar histórico.

## 8. Checklist geral

### Etapa 0 --- Diagnóstico

-   [ ] Inventário do repositório
-   [ ] Funcionalidades mapeadas
-   [ ] Banco e regras financeiras documentados
-   [ ] Integrações identificadas
-   [ ] Aplicação e testes iniciais executados
-   [ ] Backup/restauração verificados
-   [ ] `docs/diagnostico-sim.md` criado

### Etapa 1 --- Carteira

-   [ ] Cadastro e operações validados
-   [ ] Proventos validados
-   [ ] Posição e preço médio validados
-   [ ] Resultados realizados/não realizados validados
-   [ ] BRL e USD tratados corretamente
-   [ ] Testes de regressão passando

### Etapa 2 --- Dashboard

-   [ ] Patrimônio e evolução
-   [ ] Rentabilidade
-   [ ] Alocação e concentração
-   [ ] Proventos
-   [ ] Câmbio transparente
-   [ ] Exportações essenciais

### Etapa 3 --- Dados e notícias

-   [ ] Fontes Brasil documentadas
-   [ ] Fontes EUA documentadas
-   [ ] Câmbio documentado
-   [ ] Cache e última atualização
-   [ ] Gráfico histórico
-   [ ] Notícias com fonte, data e link
-   [ ] Falha externa não bloqueia o app

### Etapa 4 --- IA e radar

-   [ ] API configurável e chave protegida
-   [ ] Análise individual de ativo
-   [ ] Análise consolidada da carteira
-   [ ] Radar de notícias/oportunidades
-   [ ] Fontes e data exibidas
-   [ ] Riscos e limitações apresentados
-   [ ] Histórico de análises

### Etapa 5 --- Uso diário

-   [ ] Backup/restauração testados
-   [ ] Inicialização simples no Windows
-   [ ] Instalação/pacote validado
-   [ ] Manual criado
-   [ ] Teste completo realizado

## 9. Definição de pronto

O SIM estará pronto quando: - O usuário registrar e consultar a carteira
offline. - Posições, custos, resultados e moedas forem coerentes. -
Ativos do Brasil e EUA tiverem dados com fonte e data. - Houver
histórico, notícias e relatórios. - A IA analisar ativos e carteira com
dados identificados. - O radar destacar assuntos para investigação sem
prometer resultados. - Falhas externas não corromperem dados nem
impedirem uso básico. - Backup e restauração estiverem comprovados. - O
app iniciar no Windows sem terminal ou ambiente de desenvolvimento.

## 10. Prompt para retomar o trabalho

> Continue o SIM usando `SIM_PLANO_ENXUTO.md` e
> `docs/diagnostico-sim.md` como fontes de verdade. Verifique o
> checklist e identifique a primeira tarefa pendente. Antes de alterar
> arquivos, explique o que será feito e o que será reaproveitado.
> Implemente somente essa tarefa, execute testes relevantes, atualize o
> plano e informe o resultado. Não avance de etapa sem minha
> autorização.

Se a IA sugerir complexidade adicional, pergunte:

> Isso é indispensável para o objetivo principal? Existe uma forma menor
> reaproveitando o que já temos? Apresente a alternativa simples antes
> de implementar.

## 11. Primeira tarefa autorizada

Começar exclusivamente pela **Etapa 0 --- Diagnóstico e proteção do que
existe**.

Não implementar funcionalidades novas, não iniciar migração tecnológica
e não alterar o banco de produção. O resultado esperado é conhecer o SIM
atual e propor melhorias curtas com base no que realmente existe.
