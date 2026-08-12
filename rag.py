import io
import os
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

from langchain_text_splitters import RecursiveCharacterTextSplitter
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from pypdf import PdfReader
from tavily import TavilyClient
from langchain_core.documents import Document

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_huggingface import HuggingFaceEmbeddings

load_dotenv()

#######
# Definição da base de documentação e caminhos para páginas específicas
##################

DOCS_BASE = "https://www.gov.br/servidor/pt-br/assuntos/programa-de-gestao"

DOC_PATHS = [
    "nova-in-2023/legislacao",
    "nova-in-2023/faq",
    "minimanuais-de-orientacoes-especificas",
]

LOCAL_DOCS = [
    "Plano_de_Entregas.md",
]

#######
# Funções auxiliares para limpeza de nomes de documentos, normalização de URLs,  
# carregamento de PDFs e páginas web
###################

def clean_document_name(source: str) -> str:
    """Converte uma URL ou nome de arquivo em um nome mais legível."""
    if not source:
        return "Documento sem nome"

    value = source.rstrip("/")
    filename = value.split("/")[-1]
    if not filename or filename in {"legislacao", "faq", "minimanuais-de-orientacoes-especificas"}:
        return filename or "Página documental"

    cleaned = filename.replace("%20", " ").replace("_", " ")
    cleaned = cleaned.replace(".pdf", "")
    cleaned = cleaned.replace(".PDF", "")
    cleaned = cleaned.replace("view", "").strip()
    return cleaned


def normalize_pdf_url(url: str) -> str:
    """Normaliza URLs como /arquivo.pdf/view para o caminho real do PDF."""
    parts = urlsplit(url)
    path = parts.path
    lowered = path.lower()

    if lowered.endswith("/view"):
        path = path[:-5]
    elif lowered.endswith("/download"):
        path = path[:-9]

    if path.lower().endswith(".pdf"):
        return urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))
    return url


def is_probably_pdf(content: bytes) -> bool:
    """Verifica se o conteúdo baixado tem um cabeçalho PDF plausível antes de parsear."""
    if len(content) < 5:
        return False
    header = content[:5].lower()
    return header.startswith(b"%pdf-") or header.startswith(b"%pdk-") or content[:4] == b"%PDF"


def load_pdf_documents(pdf_url: str, error_messages: list[str]) -> list[Document]:
    """Baixa e extrai texto de um PDF sem depender do pacote opcional unstructured."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(pdf_url, timeout=25, headers=headers)
        response.raise_for_status()
    except requests.RequestException as exc:
        error_messages.append(f"Arquivo PDF indisponível: {clean_document_name(pdf_url)} ({exc})")
        return []

    if not is_probably_pdf(response.content):
        error_messages.append(f"URL ignorada por não parecer um PDF válido: {clean_document_name(pdf_url)}")
        return []

    try:
        reader = PdfReader(io.BytesIO(response.content))
        pages: list[str] = []
        for page in reader.pages:
            text = page.extract_text() or ""
            if text.strip():
                pages.append(text.strip())

        if not pages:
            return []

        return [
            Document(
                page_content="\n\n".join(pages),
                metadata={"source": pdf_url, "content_type": "pdf"},
            )
        ]
    except Exception as exc:
        error_messages.append(f"Não foi possível extrair o texto de {clean_document_name(pdf_url)}: {exc}")
        return []


def extract_web_documents(url: str, error_messages: list[str]) -> list[Document]:
    """Usa o Tavily para extrair conteúdo de uma página web sem depender de langchain-community."""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        error_messages.append("TAVILY_API_KEY não configurada. Ignorando extração web via Tavily.")
        return []

    client = TavilyClient(api_key=api_key)
    try:
        response = client.extract(
            urls=[url],
            format="markdown",
            extract_depth="basic",
            timeout=30,
        )
    except Exception as exc:
        error_messages.append(f"Erro ao extrair a página web {clean_document_name(url)}: {exc}")
        return []

    items = response.get("results", []) if isinstance(response, dict) else []
    docs: list[Document] = []
    for item in items:
        content = item.get("content") or item.get("raw_content") or ""
        if content.strip():
            docs.append(
                Document(
                    page_content=content,
                    metadata={"source": url, "content_type": "web"},
                )
            )
    return docs


def load_local_documents(local_doc_paths: list[str] | None = None) -> list[Document]:
    """Carrega documentos locais do projeto, como Markdown, TXT ou PDF."""
    local_paths = local_doc_paths or LOCAL_DOCS
    docs: list[Document] = []
    project_dir = Path(__file__).resolve().parent

    for relative_path in local_paths:
        file_path = (project_dir / relative_path).resolve()
        if not file_path.exists():
            continue

        suffix = file_path.suffix.lower()

        try:
            if suffix in {".md", ".txt"}:
                text = file_path.read_text(encoding="utf-8")
                docs.append(
                    Document(
                        page_content=text,
                        metadata={"source": str(file_path), "content_type": "local_text"},
                    )
                )
            elif suffix == ".pdf":
                with file_path.open("rb") as fh:
                    reader = PdfReader(fh)
                    pages = []
                    for page in reader.pages:
                        text = page.extract_text() or ""
                        if text.strip():
                            pages.append(text.strip())
                    if pages:
                        docs.append(
                            Document(
                                page_content="\n\n".join(pages),
                                metadata={"source": str(file_path), "content_type": "local_pdf"},
                            )
                        )
        except Exception as exc:
            print(f"Não foi possível ler o documento local {file_path.name}: {exc}")

    return docs


def load_url_documents(doc_paths: list[str] | None = None) -> tuple[list[Document], list[str]]:
    """Carrega apenas os documentos obtidos a partir das URLs da documentação oficial."""
    paths = doc_paths or DOC_PATHS
    docs: list[Document] = []
    error_messages: list[str] = []
    seen_urls: set[str] = set()

    for path in paths:
        url = f"{DOCS_BASE}/{path.strip('/')}"
        try:
            resposta = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
            resposta.raise_for_status()
        except requests.RequestException:
            continue

        docs_web = extract_web_documents(url, error_messages)
        if not docs_web:
            try:
                soup = BeautifulSoup(resposta.text, "html.parser")
                content = soup.get_text("\n", strip=True)
                if content:
                    docs_web = [
                        Document(
                            page_content=content,
                            metadata={"source": url, "content_type": "html"},
                        )
                    ]
            except Exception as exc:
                error_messages.append(f"Erro ao converter a página em texto {clean_document_name(url)}: {exc}")

        soup = BeautifulSoup(resposta.text, "html.parser")
        seen_pdfs: set[str] = set()

        for link in soup.find_all("a", href=True):
            href = link["href"]
            href = href.strip()
            if not href:
                continue
            if not href.lower().endswith(".pdf") and not href.lower().endswith("/view") and not href.lower().endswith("/download"):
                continue

            pdf_url = normalize_pdf_url(urljoin(url, href))
            if not pdf_url.lower().endswith(".pdf"):
                continue
            if pdf_url in seen_pdfs or pdf_url in seen_urls:
                continue
            seen_pdfs.add(pdf_url)
            seen_urls.add(pdf_url)

            docs.extend(load_pdf_documents(pdf_url, error_messages))

        docs.extend(docs_web)

    return docs, error_messages

########
# Carregando documentos por origem para manter fontes separadas por agente
#################

web_docs, web_errors = load_url_documents()
local_docs = load_local_documents(LOCAL_DOCS)

print(f"Carregados {len(web_docs)} documentos das URLs.")
print(f"Carregados {len(local_docs)} documentos locais.")

print("\nDocumentos das URLs:")
for i, doc in enumerate(web_docs, start=1):
    source = doc.metadata.get("source") if isinstance(doc.metadata, dict) else str(doc.metadata)
    title = clean_document_name(source)
    print(f"{i}. {title} -> {source}")

print("\nDocumentos locais:")
for i, doc in enumerate(local_docs, start=1):
    source = doc.metadata.get("source") if isinstance(doc.metadata, dict) else str(doc.metadata)
    title = clean_document_name(source)
    print(f"{i}. {title} -> {source}")

if web_errors:
    print("\nMensagens registradas para documentos das URLs:")
    for message in web_errors:
        print(f"- {message}")

#############
# Dividindo os documentos em chunks menores para processamento posterior
###########################

text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
web_splits = text_splitter.split_documents(web_docs)
local_splits = text_splitter.split_documents(local_docs)
print(f"Split web docs into {len(web_splits)} chunks.")
print(f"Split local docs into {len(local_splits)} chunks.")

###########
# Criando embeddings e armazenando os chunks em stores separados por origem
############################

#embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
#embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-2")
embeddings = HuggingFaceEmbeddings(
    model_name="tardellirs/colibri-embed-ptbr",
    model_kwargs={"device": "cpu"},
    encode_kwargs={"normalize_embeddings": False},
)

web_vector_store = InMemoryVectorStore(embeddings)
local_vector_store = InMemoryVectorStore(embeddings)

web_vector_store.add_documents(documents=web_splits)
local_vector_store.add_documents(documents=local_splits)
print(f"Indexed {len(web_splits)} web chunks.")
print(f"Indexed {len(local_splits)} local chunks.")