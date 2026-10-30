# Diretrizes do Projeto SIM

## Fluxo de Versionamento Git
- **Commit & Push Contínuo:** Toda nova funcionalidade (*feature*) ou correção de bug (*bugfix*) concluída e validada por testes deve ser comitada com mensagem semântica e enviada diretamente para o repositório remoto (`git push origin main`), garantindo que o código em produção/remoto esteja sempre sincronizado.
- **Padrão de Mensagens:** Seguir o padrão de *Conventional Commits* (ex.: `feat: ...`, `fix: ...`, `refactor: ...`, `test: ...`, `docs: ...`).
- **Segurança e Privacidade:** Nunca comitar arquivos contendo credenciais ativas, chaves privadas (`.key`), senhas ou bancos de dados SQLite locais (`.env`, `*.db`).
