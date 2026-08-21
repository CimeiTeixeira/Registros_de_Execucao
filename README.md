# Gerador de Registro de Execução (PGD)

Aplicação em Python com interface Gradio que transforma relatos informais em um registro de execução formal, alinhado ao Programa de Gestão (PGD), usando um fluxo de agente com LangGraph e Gemini.

## O que o projeto faz

- Recebe um relato livre do usuário sobre atividades realizadas.
- Planeja, pesquisa contexto e redige automaticamente um registro de execução.
- Realiza revisão automática e permite revisões adicionais sob demanda.
- Usa RAG com fontes controladas:
  - páginas normativas oficiais do PGD;
  - PDFs encontrados nessas páginas;
  - arquivos locais em `base_adicional` (`.md`, `.txt`, `.pdf`).

## Tecnologias

- Python 3.11+ (recomendado)
- Gradio
- LangGraph
- LangChain
- Gemini (Google)
- Embeddings Hugging Face (`tardellirs/colibri-embed-ptbr`)

## Estrutura principal

```text
app.py          # Interface Gradio e fluxo de interação com o usuário
backend.py      # Grafo do agente (planejamento, pesquisa, geração, reflexão)
rag.py          # Coleta de documentos, indexação e recuperação de contexto
prompts.json    # Prompts configuráveis do agente
base_adicional/ # Documentos locais usados no RAG
Sobre.md        # Conteúdo da aba "Sobre"
```

## Pré-requisitos

1. Ter Python instalado.
2. Ter acesso a uma chave do Gemini (`GEMINI_API_KEY`).
3. Chave do Tavily (`TAVILY_API_KEY`) é opcional no fluxo atual.

## Instalação

No diretório do projeto:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Se usar terminal CMD:

```cmd
python -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
```

## Configuração de ambiente

Você pode configurar as chaves pela própria aba **Chaves** na interface.

Se preferir, crie/edite o arquivo `.env` na raiz:

```env
GEMINI_API_KEY=sua_chave_aqui
TAVILY_API_KEY=sua_chave_opcional_aqui
GOOGLE_MODEL=gemini-3-flash-preview
```

## Como executar

```powershell
python app.py
```

Depois, abra no navegador o endereço exibido pelo Gradio (normalmente `http://127.0.0.1:7860`).

## Fluxo de uso recomendado

1. Abrir a aba **Chaves** e salvar a `GEMINI_API_KEY`.
2. Na aba **Base Adicional**, adicionar arquivos que ajudem na geração.
3. Voltar para a aba **Principal** e clicar em **Gerar Base**.
4. Informar o relato e clicar em **Gerar Registro**.
5. Acompanhar detalhes na aba **Processo**.
6. Usar **Solicitar revisão** quando quiser refinar o texto.

## Personalização de prompts

- Os prompts ficam em `prompts.json`.
- A aba **Prompts** permite editar os quatro prompts obrigatórios sem sair da interface.
- Mantenha o formato JSON válido ao salvar.

## Observações

- O arquivo `checkpoints.db` armazena checkpoints do fluxo do agente.
- O log de RAG é salvo em `rag.log`.
- A pasta `base_adicional` é ignorada no Git por padrão (`.gitignore`).

## Publicação no GitHub

Passo a passo básico:

```bash
git init
git add .
git commit -m "feat: estrutura inicial do gerador de registros PGD"
git branch -M main
git remote add origin https://github.com/SEU_USUARIO/SEU_REPOSITORIO.git
git push -u origin main
```

## Licença

Este projeto está licenciado sob a Licença MIT.

- Texto oficial em inglês: [LICENSE](LICENSE)
- Tradução de referência em português: [LICENSE.pt-BR](LICENSE.pt-BR)
