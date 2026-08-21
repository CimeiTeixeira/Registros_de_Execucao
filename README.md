# Gerador de Registros PGD (Branch bundle)

Esta branch reúne a versão preparada para empacotamento e distribuição do aplicativo Gerador de Registros de Execução (PGD).

## Visão geral

A aplicação recebe um relato informal e gera um registro de execução formal com apoio de:

- fluxo de agente com LangGraph;
- modelo Gemini para planejamento, redação e revisão;
- base RAG com conteúdo web permitido e documentos locais.

## Principais diferenças desta branch

- inclui arquivo de build do executável: `GeradorRegistrosPGD.spec`;
- inclui script de build: `build_bundle.ps1`;
- inclui utilitário de caminhos de runtime: `runtime_paths.py`;
- inclui dependência `pyinstaller` em `requirements.txt`.

## Requisitos

- Python 3.11+;
- ambiente com dependências instaladas;
- chave do Gemini (obrigatória para gerar registros).

## Instalação

PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

CMD:

```cmd
python -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
```

## Execução em desenvolvimento

```powershell
python app.py
```

A interface abre localmente via Gradio (endereço exibido no terminal).

## Uso rápido

1. Na aba Chaves, informe a GEMINI_API_KEY.
2. Na aba Base Adicional, adicione arquivos .md, .txt e .pdf.
3. Na aba Principal, clique em Gerar Base.
4. Informe o relato e clique em Gerar Registro.
5. Use Solicitar revisão quando precisar refinar o resultado.

## Build do executável (PyInstaller)

### Opção 1: script pronto

```powershell
.\build_bundle.ps1
```

Se precisar informar outro ambiente conda:

```powershell
.\build_bundle.ps1 -EnvironmentName nome_do_ambiente
```

### Opção 2: comando direto

```powershell
pyinstaller --noconfirm --clean GeradorRegistrosPGD.spec
```

## Estrutura essencial

```text
app.py
backend.py
rag.py
runtime_paths.py
GeradorRegistrosPGD.spec
build_bundle.ps1
prompts.json
base_adicional/
```

## Observações

- A chave Gemini pode ser cadastrada pela própria interface na aba Chaves.
- Arquivos persistentes (como .env e checkpoints) são tratados para funcionar em modo empacotado.
- Documentos adicionais em base_adicional enriquecem o contexto do RAG.
