# backend.py
import warnings
warnings.filterwarnings("ignore", message=".*TqdmWarning.*")

import json
import os
from pathlib import Path
from dotenv import load_dotenv

from typing import TypedDict, Annotated, List
import operator

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from rag import build_rag_stores, retrieve_rag_context

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver

import sqlite3

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# Define as variáveis de ambiente
os.environ['GOOGLE_API_KEY'] = os.getenv('GEMINI_API_KEY')


def refresh_api_keys() -> None:
    """Atualiza as chaves em memória e recria o cliente Gemini quando a configuração mudar."""
    gemini_key = (os.getenv("GEMINI_API_KEY") or "").strip()
    if gemini_key:
        os.environ["GEMINI_API_KEY"] = gemini_key
        os.environ["GOOGLE_API_KEY"] = gemini_key

    global model, structured_model
    model = ChatGoogleGenerativeAI(model=nome_modelo, temperature=1)
    structured_model = model.with_structured_output(Queries)


# Define o estado do agente (AgentState)
class AgentState(TypedDict):
    tarefa: str
    plano: str
    rascunho: str
    critica: str
    conteudo: List[str]
    numero_revisao: int
    maximo_revisoes: int
    temperatura: float
    material_revisao: str


# Define o modelo Pydantic para a saída estruturada
class Queries(BaseModel):
    queries: List[str]


# Inicializa o banco de dados para os checkpoints
conn = sqlite3.connect("checkpoints.db", check_same_thread=False)
memory = SqliteSaver(conn)

# Inicializa o modelo de linguagem
nome_modelo = os.getenv("GOOGLE_MODEL", "gemini-3-flash-preview")
model = ChatGoogleGenerativeAI(model=nome_modelo, temperature=1)

# Cria um Runnable para a saída estruturada (forma correta para Gemini)
structured_model = model.with_structured_output(Queries)

PROMPTS_FILE = Path(__file__).resolve().parent / "prompts.json"
PROMPT_KEYS = (
    "PLANEJAMENTO_PROMPT",
    "PESQUISA_PLANEJAMENTO_PROMPT",
    "REDIGIR_PROMPT",
    "ANALISAR_PROMPT",
)


def load_prompt_config() -> dict[str, str]:
    with PROMPTS_FILE.open("r", encoding="utf-8") as prompt_file:
        prompts = json.load(prompt_file)

    missing_keys = [key for key in PROMPT_KEYS if key not in prompts]
    extra_keys = [key for key in prompts if key not in PROMPT_KEYS]
    if missing_keys or extra_keys or any(not isinstance(prompts[key], str) for key in PROMPT_KEYS):
        raise ValueError("prompts.json deve conter somente as quatro chaves com valores de texto.")
    return prompts


def save_prompt_config(prompts: dict[str, str]) -> None:
    missing_keys = [key for key in PROMPT_KEYS if key not in prompts]
    extra_keys = [key for key in prompts if key not in PROMPT_KEYS]
    if missing_keys or extra_keys or any(not isinstance(prompts[key], str) for key in PROMPT_KEYS):
        raise ValueError("A configuração deve conter somente as quatro chaves de prompt com valores de texto.")

    with PROMPTS_FILE.open("w", encoding="utf-8") as prompt_file:
        json.dump(prompts, prompt_file, ensure_ascii=False, indent=2)
        prompt_file.write("\n")


def modelo_da_execucao(state: AgentState):
    return ChatGoogleGenerativeAI(
        model=nome_modelo,
        temperature=state.get("temperatura", 1),
    )

# Definição dos nós do LangGraph
def plano_node(state: AgentState):
    prompts = load_prompt_config()
    messages = [
        SystemMessage(content=prompts["PLANEJAMENTO_PROMPT"]),
        HumanMessage(content=state['tarefa'])
    ]
    response = modelo_da_execucao(state).invoke(messages)
    return {"plano": response.content}


def pesquisa_plano_node(state: AgentState):
    prompts = load_prompt_config()
    structured_model_execucao = modelo_da_execucao(state).with_structured_output(Queries)
    queries = structured_model_execucao.invoke([
        SystemMessage(content=prompts["PESQUISA_PLANEJAMENTO_PROMPT"]),
        HumanMessage(content=state['tarefa'])
    ])
    content = state['conteudo'] or []
    for q in queries.queries:
        rag_context = retrieve_rag_context(q, source="all", k=3)
        if rag_context.strip():
            content.append(f"Contexto do RAG para: {q}\n\n{rag_context}")
    return {"conteudo": content}


def geracao_node(state: AgentState):
    prompts = load_prompt_config()
    content = "\n\n".join(state['conteudo'] or [])
    revision_context = ""
    if state.get("rascunho"):
        revision_context += f"\n\nAqui está o rascunho anterior:\n\n{state['rascunho']}"
    if state.get("critica"):
        revision_context += f"\n\nAqui está a crítica a ser aplicada:\n\n{state['critica']}"
    if state.get("material_revisao"):
        revision_context += (
            "\n\nMaterial adicional fornecido pelo usuário para esta revisão:\n\n"
            f"{state['material_revisao']}"
        )

    user_message = HumanMessage(
        content=(
            f"{state['tarefa']}\n\n"
            f"Aqui está o meu plano:\n\n{state['plano']}"
            f"{revision_context}"
        )
    )
    messages = [
        SystemMessage(
            content=prompts["REDIGIR_PROMPT"].replace("{content}", content)
        ),
        user_message
    ]
    response = modelo_da_execucao(state).invoke(messages)
    return {
        "rascunho": response.content,
        "numero_revisao": state.get("numero_revisao", 0) + 1
    }


def reflexao_node(state: AgentState):
    prompts = load_prompt_config()
    messages = [
        SystemMessage(content=prompts["ANALISAR_PROMPT"]),
        HumanMessage(content=state['rascunho'])
    ]
    response = modelo_da_execucao(state).invoke(messages)
    return {"critica": response.content}


def executar_revisao(state: AgentState, material_revisao: str = ""):
    state_com_material = {**state, "material_revisao": material_revisao}
    critica = reflexao_node(state_com_material)
    state_atualizado = {**state_com_material, **critica}
    rascunho = geracao_node(state_atualizado)
    return {**state_atualizado, **rascunho}


def deve_continuar(state):
    if state["numero_revisao"] > state["maximo_revisoes"]:
        return END
    return "refletir"


# Construção do Grafo
builder = StateGraph(AgentState)
builder.add_node("planejador", plano_node)
builder.add_node("pesquisa_plano", pesquisa_plano_node)
builder.add_node("gerar", geracao_node)
builder.add_node("refletir", reflexao_node)

builder.set_entry_point("planejador")

builder.add_conditional_edges(
    "gerar",
    deve_continuar,
    {END: END, "refletir": "refletir"}
)

builder.add_edge("planejador", "pesquisa_plano")
builder.add_edge("pesquisa_plano", "gerar")
builder.add_edge("refletir", "gerar")

graph = builder.compile(checkpointer=memory)

