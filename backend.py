# backend.py
import warnings
warnings.filterwarnings("ignore", message=".*TqdmWarning.*")

import os
from dotenv import load_dotenv

from typing import TypedDict, Annotated, List
import operator

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from tavily import TavilyClient

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver

import sqlite3

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# Define as variáveis de ambiente
os.environ['GOOGLE_API_KEY'] = os.getenv('GEMINI_API_KEY')
if not os.getenv('TAVILY_API_KEY'):
    raise RuntimeError("TAVILY_API_KEY não configurada. Defina a variável no arquivo .env antes de iniciar o backend.")
os.environ['TAVILY_API_KEY'] = os.getenv('TAVILY_API_KEY')


# Define o estado do agente (AgentState)
class AgentState(TypedDict):
    tarefa: str
    plano: str
    rascunho: str
    critica: str
    conteudo: List[str]
    numero_revisao: int
    maximo_revisoes: int


# Define o modelo Pydantic para a saída estruturada
class Queries(BaseModel):
    queries: List[str]


# Inicializa o banco de dados para os checkpoints
conn = sqlite3.connect("checkpoints.db", check_same_thread=False)
memory = SqliteSaver(conn)

# Inicializa o modelo de linguagem
nome_modelo = os.getenv("GOOGLE_MODEL", "gemini-3-flash-preview")
model = ChatGoogleGenerativeAI(model=nome_modelo, temperature=0)

# Cria um Runnable para a saída estruturada (forma correta para Gemini)
structured_model = model.with_structured_output(Queries)


# Prompts
PLANEJAMENTO_PROMPT = """Você é um escritor especialista em organizar textos e criar esboços de alto nível a partir do relato do usuário. \
Escreva esse esboço baseado no relato fornecido pelo usuário, organizando-o como um diário de bordo claro. \
Apresente um plano da redação junto com quaisquer notas ou instruções relevantes."""

REDIGIR_PROMPT = """Você é um assistente de redação com a tarefa de escrever excelentes redações curtas.\
Gere a melhor redação possível para o esboço inicial. \
Esta redação será o registro de execução do usuário. \
Se o usuário fornecer críticas, responda com uma versão revisada das suas tentativas anteriores. \
Utilize todas as informações abaixo conforme necessário:

------

{content}"""

ANALISAR_PROMPT = """Você é um chefe analisando o registro de execução do usuário. \
Gere uma crítica e recomendações para o registro de execução do usuário. \
Forneça recomendações detalhadas, incluindo pedidos sobre extensão, profundidade, estilo etc."""

PESQUISA_PLANEJAMENTO_PROMPT = """Você é um pesquisador encarregado de fornecer informações que podem \
ser usadas ao escrever o seguinte registro de execução do usuário. Gere uma lista de consultas de pesquisa que \
recolham quaisquer informações relevantes. Gere no máximo 3 consultas."""

PESQUISAR_CRITICA_PROMPT = """Você é um pesquisador encarregado de fornecer informações que podem \
ser usadas ao fazer quaisquer revisões solicitadas (conforme descrito abaixo). \
Gere uma lista de consultas de pesquisa que recolham quaisquer informações relevantes. Gere no máximo 3 consultas."""

# Inicializa o cliente Tavily
tavily = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])


# Definição dos nós do LangGraph
def plano_node(state: AgentState):
    messages = [
        SystemMessage(content=PLANEJAMENTO_PROMPT),
        HumanMessage(content=state['tarefa'])
    ]
    response = model.invoke(messages)
    return {"plano": response.content}


def pesquisa_plano_node(state: AgentState):
    queries = structured_model.invoke([
        SystemMessage(content=PESQUISA_PLANEJAMENTO_PROMPT),
        HumanMessage(content=state['tarefa'])
    ])
    content = state['conteudo'] or []
    for q in queries.queries:
        response = tavily.search(query=q, max_results=2)
        for r in response['results']:
            content.append(r['content'])
    return {"conteudo": content}


def geracao_node(state: AgentState):
    content = "\n\n".join(state['conteudo'] or [])
    user_message = HumanMessage(
        content=f"{state['tarefa']}\n\nAqui está o meu plano:\n\n{state['plano']}")
    messages = [
        SystemMessage(
            content=REDIGIR_PROMPT.format(content=content)
        ),
        user_message
    ]
    response = model.invoke(messages)
    return {
        "rascunho": response.content,
        "numero_revisao": state.get("numero_revisao", 0) + 1
    }


def reflexao_node(state: AgentState):
    messages = [
        SystemMessage(content=ANALISAR_PROMPT),
        HumanMessage(content=state['rascunho'])
    ]
    response = model.invoke(messages)
    return {"critica": response.content}


def pesquisa_critica_node(state: AgentState):
    queries = structured_model.invoke([
        SystemMessage(content=PESQUISAR_CRITICA_PROMPT),
        HumanMessage(content=state['critica'])
    ])
    content = state['conteudo'] or []
    for q in queries.queries:
        response = tavily.search(query=q, max_results=2)
        for r in response['results']:
            content.append(r['content'])
    return {"conteudo": content}


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
builder.add_node("pesquisa_critica", pesquisa_critica_node)

builder.set_entry_point("planejador")

builder.add_conditional_edges(
    "gerar",
    deve_continuar,
    {END: END, "refletir": "refletir"}
)

builder.add_edge("planejador", "pesquisa_plano")
builder.add_edge("pesquisa_plano", "gerar")
builder.add_edge("refletir", "pesquisa_critica")
builder.add_edge("pesquisa_critica", "gerar")

graph = builder.compile(checkpointer=memory)

