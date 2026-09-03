# Gerador de Registro de Execução (PGD)

Aplicação em Python com interface Gradio que transforma relatos informais em um registro de execução formal, alinhado ao Programa de Gestão (PGD), usando um fluxo de agente com LangGraph. O usuário escolhe, a cada geração, entre dois provedores de modelo: **Gemini** (chave de API) ou **Azure OpenAI** (autenticação via Microsoft Entra ID).

## O que o projeto faz

- Recebe um relato livre do usuário sobre atividades realizadas.
- Planeja, pesquisa contexto e redige automaticamente um registro de execução.
- Realiza revisão automática e permite revisões adicionais sob demanda.
- Permite escolher o provedor do modelo de linguagem (Gemini ou Azure OpenAI) a cada geração.
- Usa RAG com fontes controladas:
  - páginas normativas oficiais do PGD;
  - PDFs encontrados nessas páginas;
  - arquivos locais em `base_adicional` (`.md`, `.txt`, `.pdf`).

## Tecnologias

- Python 3.11+ (recomendado)
- Gradio
- LangGraph
- LangChain
- Gemini (Google) e Azure OpenAI
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
2. Ter acesso a uma chave do Gemini (`GEMINI_API_KEY`) e/ou a um recurso Azure OpenAI configurado (veja a seção abaixo).
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
AZURE_OPENAI_ENDPOINT=https://seu-recurso.cognitiveservices.azure.com/
AZURE_OPENAI_DEPLOYMENT=nome-do-deployment
AZURE_OPENAI_API_VERSION=2024-10-21
```

### Usando o provedor Azure OpenAI

O provedor **Azure OpenAI** autentica pela identidade do usuário no Microsoft Entra ID (via `azure-identity`), em vez de uma chave de API. Antes de rodar a aplicação com essa opção selecionada:

1. Instale o [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) (o comando `az` precisa estar disponível no terminal).
2. Faça login uma vez por sessão de trabalho: `az login --tenant SEU_TENANT`.
3. Preencha `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT` e `AZURE_OPENAI_API_VERSION`, seja no `.env`, seja pela aba **Chaves** da interface.
4. Garanta que sua conta tenha a role apropriada (ex.: *Cognitive Services OpenAI User*) no recurso Azure OpenAI.

O login do Azure CLI é reaproveitado entre execuções da aplicação; refaça o `az login` quando a sessão expirar. O provedor **Gemini** continua disponível normalmente, bastando a `GEMINI_API_KEY`.

## Como executar

```powershell
python app.py
```

Depois, abra no navegador o endereço exibido pelo Gradio (normalmente `http://127.0.0.1:7860`).

## Fluxo de uso recomendado

1. Abrir a aba **Chaves** e salvar a `GEMINI_API_KEY` e/ou as configurações do Azure OpenAI (e, neste último caso, ter feito `az login` antes de abrir a aplicação).
2. Na aba **Base Adicional**, adicionar arquivos que ajudem na geração.
3. Voltar para a aba **Principal** e clicar em **Gerar Base** na primeira execução. A base gerada fica persistida em disco (pasta `rag_index/`) e é reaproveitada automaticamente nas próximas execuções — não é preciso gerar novamente só porque a aplicação foi reiniciada.
4. Sempre que anexar ou remover documentos na aba **Base Adicional**, clique em **Regerar Base** para que o RAG reflita as mudanças.
5. Escolher o **Provedor de modelo** (Gemini ou Azure OpenAI), informar o relato e clicar em **Gerar Registro**.
6. Acompanhar detalhes na aba **Processo**.
7. Usar **Solicitar revisão** quando quiser refinar o texto.

## Personalização de prompts

- Os prompts ficam em `prompts.json`.
- A aba **Prompts** permite editar os quatro prompts obrigatórios sem sair da interface.
- Mantenha o formato JSON válido ao salvar.

## Observações

- O arquivo `checkpoints.db` armazena checkpoints do fluxo do agente.
- O log de RAG é salvo em `rag.log`.
- A base RAG indexada fica persistida em `rag_index/` e é ignorada no Git; use **Regerar Base** para atualizá-la após mudanças na pasta `base_adicional`.
- A pasta `base_adicional` é ignorada no Git por padrão (`.gitignore`).


## Licença

Este projeto está licenciado sob a Licença MIT.

- Texto oficial em inglês: [LICENSE](LICENSE)
- Tradução de referência em português: [LICENSE.pt-BR](LICENSE.pt-BR)
