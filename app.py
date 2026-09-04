# app.py
import json
import os
import shutil
import warnings

import gradio as gr

# Gradio 5.50.0 ainda não aceita theme/css em launch(); avisos são sobre o Gradio 6.0.
warnings.filterwarnings(
    "ignore",
    message=r"The '(theme|css)' parameter in the Blocks constructor.*",
    category=DeprecationWarning,
)
# padding=True já é passado explicitamente; Gradio ainda assim avisa nesta versão.
warnings.filterwarnings(
    "ignore",
    message=r"The default value of 'padding' in gr\.HTML.*",
    category=DeprecationWarning,
)

from gradio_modal import Modal
from pathlib import Path
import base64
import sys
from datetime import datetime
import markdown as markdown_lib
from dotenv import dotenv_values, set_key
from backend import (
    PROMPT_KEYS,
    executar_revisao,
    graph,
    load_prompt_config,
    refresh_api_keys,
    save_prompt_config,
)
from rag import (
    ADDITIONAL_BASE_DIR,
    LOCAL_DOCUMENT_SUFFIXES,
    build_rag_stores,
    discover_local_documents,
    get_rag_index_status,
)
import uuid


def resource_path(*parts: str) -> Path:
    """Resolve arquivos de dados empacotados (_internal no PyInstaller) ou do script."""
    if getattr(sys, "frozen", False):
        # PyInstaller onedir coloca os dados em <pasta_do_exe>\_internal
        return Path(sys.executable).resolve().parent / "_internal" / Path(*parts)
    return Path(__file__).resolve().parent.joinpath(*parts)


def app_data_path(*parts: str) -> Path:
    """Resolve arquivos criados em runtime ao lado do executável ou do script."""
    base = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
    return base.joinpath(*parts)


ENV_PATH = app_data_path(".env")


def extract_text(content) -> str:
    """Normaliza response.content: lista de blocos (Gemini) ou string simples (Azure/OpenAI)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list) and content:
        first_block = content[0]
        if isinstance(first_block, dict):
            return first_block.get("text", "")
        return str(first_block)
    return ""


def list_additional_files() -> list[str]:
    """Retorna os arquivos suportados atualmente disponíveis na base adicional."""
    return [
        str(file_path.relative_to(ADDITIONAL_BASE_DIR))
        for file_path in discover_local_documents()
    ]


def refresh_additional_files(message: str = ""):
    files = list_additional_files()
    status = status_html(message, color="#2e7d32") if message else ""
    return gr.update(choices=files, value=None), status


def upload_additional_files(uploaded_files):
    if not uploaded_files:
        return refresh_additional_files("Nenhum arquivo foi selecionado.")

    ADDITIONAL_BASE_DIR.mkdir(parents=True, exist_ok=True)
    copied_files = []
    ignored_files = []

    for uploaded_file in uploaded_files:
        source_path = Path(getattr(uploaded_file, "name", uploaded_file))
        if source_path.suffix.lower() not in LOCAL_DOCUMENT_SUFFIXES:
            ignored_files.append(source_path.name)
            continue

        destination = ADDITIONAL_BASE_DIR / source_path.name
        shutil.copy2(source_path, destination)
        copied_files.append(source_path.name)

    messages = []
    if copied_files:
        messages.append(f"{len(copied_files)} arquivo(s) adicionado(s) à base adicional.")
    if ignored_files:
        messages.append(
            "Ignorados por formato não suportado: " + ", ".join(ignored_files) + "."
        )
    if not messages:
        messages.append("Nenhum arquivo compatível foi adicionado.")

    messages.append("Clique em 'Gerar Base' para reindexar os documentos.")
    return refresh_additional_files(" ".join(messages))


def delete_additional_file(selected_file: str):
    if not selected_file:
        return refresh_additional_files("Selecione um arquivo para excluir.")

    base_dir = ADDITIONAL_BASE_DIR.resolve()
    candidate = (base_dir / selected_file).resolve()
    try:
        candidate.relative_to(base_dir)
    except ValueError:
        return refresh_additional_files("Arquivo inválido para exclusão.")

    if not candidate.is_file():
        return refresh_additional_files("O arquivo selecionado não foi encontrado.")

    candidate.unlink()
    return refresh_additional_files(
        f"Arquivo excluído: {selected_file}. Clique em 'Gerar Base' para reindexar.",
    )


def load_api_key_settings() -> tuple[str, str, str, str, str]:
    values = dotenv_values(str(ENV_PATH))
    gemini_key = (values.get("GEMINI_API_KEY") or "").strip()
    tavily_key = (values.get("TAVILY_API_KEY") or "").strip()
    azure_endpoint = (values.get("AZURE_OPENAI_ENDPOINT") or "").strip()
    azure_deployment = (values.get("AZURE_OPENAI_DEPLOYMENT") or "").strip()
    azure_api_version = (values.get("AZURE_OPENAI_API_VERSION") or "2024-10-21").strip()
    return gemini_key, tavily_key, azure_endpoint, azure_deployment, azure_api_version


def save_api_key_settings(
    gemini_key: str,
    tavily_key: str,
    azure_endpoint: str,
    azure_deployment: str,
    azure_api_version: str,
):
    gemini_value = (gemini_key or "").strip()
    tavily_value = (tavily_key or "").strip()
    azure_endpoint_value = (azure_endpoint or "").strip()
    azure_deployment_value = (azure_deployment or "").strip()
    azure_api_version_value = (azure_api_version or "2024-10-21").strip()

    if not ENV_PATH.exists():
        ENV_PATH.touch()

    set_key(str(ENV_PATH), "GEMINI_API_KEY", gemini_value, quote_mode="never")
    set_key(str(ENV_PATH), "TAVILY_API_KEY", tavily_value, quote_mode="never")
    set_key(str(ENV_PATH), "AZURE_OPENAI_ENDPOINT", azure_endpoint_value, quote_mode="never")
    set_key(str(ENV_PATH), "AZURE_OPENAI_DEPLOYMENT", azure_deployment_value, quote_mode="never")
    set_key(str(ENV_PATH), "AZURE_OPENAI_API_VERSION", azure_api_version_value, quote_mode="never")

    if gemini_value:
        os.environ["GEMINI_API_KEY"] = gemini_value
        os.environ["GOOGLE_API_KEY"] = gemini_value
    if tavily_value:
        os.environ["TAVILY_API_KEY"] = tavily_value
    os.environ["AZURE_OPENAI_ENDPOINT"] = azure_endpoint_value
    os.environ["AZURE_OPENAI_DEPLOYMENT"] = azure_deployment_value
    os.environ["AZURE_OPENAI_API_VERSION"] = azure_api_version_value

    refresh_api_keys()

    return status_html(
        "Configurações salvas e aplicadas. O Tavily é opcional no fluxo atual do RAG.",
        color="#2e7d32",
    )


def status_html(message: str, color: str = "#d32f2f") -> str:
    """Retorna uma mensagem formatada em HTML para status visual na interface."""
    bg_map = {
        "#d32f2f": "#fff5f5",
        "#ef6c00": "#fff7ed",
        "#f9a825": "#fff8e1",
        "#2e7d32": "#edf7ed",
    }
    background = bg_map.get(color, "#fff5f5")
    return (
        "<div style='padding: 8px 10px; border-radius: 8px; "
        + f"background: {background}; color: {color}; font-weight: 500; "
        + f"border-left: 4px solid {color}; border: 1px solid rgba(15, 23, 42, 0.08); "
        + "line-height: 1.4; width: 100%; box-sizing: border-box;'>"
        + f"{message}</div>"
    )


def format_generated_at(iso_str: str | None) -> str:
    """Formata o timestamp ISO da base RAG para exibição em pt-BR."""
    if not iso_str:
        return "data desconhecida"
    try:
        return datetime.fromisoformat(iso_str).strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return iso_str


def initial_rag_status():
    """Define o status e o rótulo do botão de base RAG ao carregar a página."""
    status = get_rag_index_status()
    if status.get("exists"):
        generated_at = format_generated_at(status.get("generated_at"))
        return (
            status_html(
                f"Base de conhecimento carregada (gerada em {generated_at}). "
                "Clique em 'Regerar Base' para atualizá-la, se necessário.",
                color="#2e7d32",
            ),
            gr.update(value="Regerar Base"),
            True,
        )
    return (
        status_html("Clique em \"Gerar Base\" para carregar a base de conhecimento.", color="#d32f2f"),
        gr.update(value="Gerar Base"),
        False,
    )


def preload_rag():
    """Gera ou regera a base RAG, mantendo o botão disponível para reindexar depois."""
    yield (
        status_html("Carregando base de conhecimento...", color="#d32f2f"),
        gr.update(interactive=False),
    )
    build_rag_stores(force_reload=True)
    generated_at = format_generated_at(get_rag_index_status().get("generated_at"))
    yield (
        status_html(
            f"Base de conhecimento pronta (gerada em {generated_at}). "
            "Você pode incluir o relato e gerar o registro.",
            color="#2e7d32",
        ),
        gr.update(value="Regerar Base", interactive=True),
    )


def rag_info_html() -> str:
    """Indicador fixo e discreto com a data/hora da última base RAG gerada."""
    status = get_rag_index_status()
    if status.get("exists"):
        text = f"Base de conhecimento gerada em {format_generated_at(status.get('generated_at'))}."
    else:
        text = "Nenhuma base de conhecimento gerada ainda."
    return (
        "<div style='text-align:center; font-size:0.8em; color:#6b7280; margin-top:4px;'>"
        f"{text}</div>"
    )


def update_generate_button(topic: str, rag_ready: bool):
    can_generate = bool(rag_ready) and bool((topic or "").strip())
    return (
        gr.update(visible=True, interactive=can_generate),
        gr.update(visible=False, interactive=False),
    )


def load_prompts_for_editor():
    return json.dumps(load_prompt_config(), ensure_ascii=False, indent=2)


def render_about_html() -> str:
    """Converte Sobre.md em HTML, embutindo a imagem do grafo como data URI."""
    about_text = resource_path("Sobre.md").read_text(encoding="utf-8")
    image_path = resource_path("grafo_projeto.png")
    if image_path.exists():
        encoded_image = base64.b64encode(image_path.read_bytes()).decode("ascii")
        about_text = about_text.replace(
            "(grafo_projeto.png)",
            f"(data:image/png;base64,{encoded_image})",
        )
    return markdown_lib.markdown(about_text)


def update_prompts(prompt_text: str):
    try:
        prompts = json.loads(prompt_text)
    except json.JSONDecodeError as error:
        return prompt_text, status_html(
            f"JSON inválido na linha {error.lineno}, coluna {error.colno}: {error.msg}",
            color="#d32f2f",
        )

    if not isinstance(prompts, dict):
        return prompt_text, status_html("O conteúdo deve ser um objeto JSON.", color="#d32f2f")

    missing_keys = [key for key in PROMPT_KEYS if key not in prompts]
    extra_keys = [key for key in prompts if key not in PROMPT_KEYS]
    non_text_keys = [key for key in PROMPT_KEYS if key in prompts and not isinstance(prompts[key], str)]
    if missing_keys or extra_keys or non_text_keys:
        problems = []
        if missing_keys:
            problems.append(f"ausentes: {', '.join(missing_keys)}")
        if extra_keys:
            problems.append(f"não reconhecidas: {', '.join(extra_keys)}")
        if non_text_keys:
            problems.append(f"devem ser texto: {', '.join(non_text_keys)}")
        return prompt_text, status_html(
            "Configuração inválida: " + "; ".join(problems),
            color="#d32f2f",
        )

    save_prompt_config(prompts)
    formatted_prompts = json.dumps(prompts, ensure_ascii=False, indent=2)
    return formatted_prompts, status_html("Prompts atualizados com sucesso.", color="#2e7d32")


# --- Função que será chamada pelo Gradio para rodar o agente ---
def generate_essay(topic: str, temperatura: float, provedor_modelo: str):
    """
    Roda o grafo do agente para gerar uma redação e transmite as saídas em tempo real.
    A aba principal mostra apenas o rascunho final; a aba de processo mostra o log completo.
    """
    build_rag_stores()
    yield "", "", status_html("Carregando base de conhecimento e gerando registro...", color="#d32f2f"), None, gr.update(visible=False), gr.update(visible=True, interactive=False)

    thread_id = str(uuid.uuid4())
    thread_config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        'tarefa': topic,
        "maximo_revisoes": 1,
        "numero_revisao": 0,
        "plano": "",
        "rascunho": "",
        "critica": "",
        "conteudo": [],
        "temperatura": temperatura,
        "material_revisao": "",
        "provedor_modelo": provedor_modelo,
    }

    process_log = ""
    final_draft = ""
    status = status_html("Base pronta. Iniciando o processo de geração...", color="#ef6c00")

    for s in graph.stream(initial_state, thread_config):
        step_output = list(s.values())[0]
        initial_state.update(step_output)

        if 'plano' in step_output:
            status = status_html("Planejando a redação...", color="#ef6c00")
            process_log += f"📝 PLANO GERADO:\n{extract_text(step_output['plano'])}\n\n"
        elif 'conteudo' in step_output:
            status = status_html("Buscando e organizando o contexto de pesquisa...", color="#f9a825")
            search_content = "\n".join(step_output['conteudo'])
            process_log += f"🔍 CONTEÚDO DE PESQUISA:\n{search_content}\n\n"
        elif 'rascunho' in step_output:
            draft = extract_text(step_output['rascunho'])
            process_log += f"✍️ RASCUNHO GERADO:\n{draft}\n\n"
            if initial_state["numero_revisao"] > initial_state["maximo_revisoes"]:
                final_draft = draft
                status = status_html("Redação final gerada. Finalizando...", color="#ef6c00")
            else:
                status = status_html("Rascunho gerado. Iniciando revisão...", color="#ef6c00")
        elif 'critica' in step_output:
            status = status_html("Revisão concluída. Gerando redação final...", color="#ef6c00")
            process_log += f"🧐 CRÍTICA E REVISÃO:\n{extract_text(step_output['critica'])}\n\n"

        process_log += "---" * 20 + "\n\n"
        initial_state["_process_log"] = process_log
        yield final_draft, process_log, status, initial_state, gr.update(visible=False), gr.update(visible=True, interactive=False)

    status = status_html("Registro concluído com sucesso.", color="#2e7d32")
    initial_state["_process_log"] = process_log
    yield final_draft, process_log, status, initial_state, gr.update(visible=True, interactive=True), gr.update(visible=False)


def open_revision_modal():
    return gr.update(visible=True)


def apply_revision(state: dict, material_revisao: str):
    if not state or not state.get("rascunho"):
        return (
            "",
            "",
            status_html("Gere um registro antes de solicitar uma revisão."),
            state,
            gr.update(interactive=False),
            gr.update(visible=False),
        )

    status = status_html("Analisando o registro para uma nova revisão...", color="#ef6c00")
    yield (
        extract_text(state["rascunho"]),
        state.get("_process_log", ""),
        status,
        state,
        gr.update(interactive=False),
        gr.update(visible=True),
    )

    updated_state = executar_revisao(state, material_revisao.strip())
    process_log = state.get("_process_log", "") + (
        f"MATERIAL ADICIONAL PARA A REVISÃO:\n{material_revisao.strip() or '[Nenhum material adicional informado]'}\n\n"
        f"REVISANDO: 🧐 CRÍTICA E REVISÃO:\n{extract_text(updated_state['critica'])}\n\n"
        f"REVISANDO: ✍️ RASCUNHO REVISADO:\n{extract_text(updated_state['rascunho'])}\n\n"
        + "---" * 20
        + "\n\n"
    )
    status = status_html("Revisão concluída. Você pode solicitar outra revisão.", color="#2e7d32")
    yield extract_text(updated_state["rascunho"]), process_log, status, updated_state, gr.update(interactive=True), gr.update(visible=False)

# --- Criação da Interface Gradio ---
with gr.Blocks(
    css="#process-output textarea { overflow-y: auto !important; }",
    theme=gr.themes.Default(spacing_size="sm", text_size="lg"),
) as demo:

    with gr.Tab("Sobre"):
        gr.HTML(render_about_html())

    with gr.Tab("Principal"):

        with gr.Row():
            with gr.Column(scale=8, min_width=0):
                gr.Markdown("# 🤖 Gerador de Registro de Execução (PGD)")
            with gr.Column(scale=12, min_width=0):
                status_box = gr.HTML(status_html("Clique em \"Gerar Base\" para carregar a base de conhecimento.", color="#d32f2f"), padding=True)

        gr.Markdown(
            "Diga-me o que você, ou sua unidade, fez no período de tempo em questão (hoje, ou esta semana, por exemplo)."
            "Seja tão informal quanto quiser. O agente vai planejar, pesquisar, rascunhar, revisar e gerar o texto final."
        )

        with gr.Row():
            with gr.Column(scale=12, min_width=0):
                essay_topic = gr.Textbox(label="Relato", placeholder="Ex: Tal coisa, feita em tal dia. N reuniões realizadas com assuntos x y z..., M atividades concluídas, etc.", lines=2, max_lines=4)
            with gr.Column(scale=3, min_width=0):
                model_provider = gr.Dropdown(
                    label="Provedor de modelo",
                    choices=["Azure OpenAI", "Gemini"],
                    value="Azure OpenAI",
                    interactive=True,
                )
            with gr.Column(scale=3, min_width=0):
                temperature_slider = gr.Slider(
                    minimum=0,
                    maximum=2,
                    step=0.1,
                    value=0,
                    label="Criatividade",
                    info="0 é sóbrio; 2 é alucinado"
                )
            with gr.Column(scale=2, min_width=0):
                gerar_base_button = gr.Button("Gerar Base", elem_id="gerar-base-button")
            with gr.Column(scale=2, min_width=0):
                generate_button = gr.Button("Gerar Registro", variant="primary", interactive=False)
                new_revision_button = gr.Button("Solicitar revisão", interactive=False, visible=False)

        output_textbox = gr.Textbox(label="Redação Final", lines=10, max_lines=12)
        rag_info_box = gr.HTML(rag_info_html(), padding=False)
        execution_state = gr.State(value=None)
        rag_ready_state = gr.State(value=False)

        with Modal(visible=False) as review_modal:
            gr.Markdown("### Solicitar uma revisão")
            revision_material = gr.Textbox(
                label="O que deve se revisado",
                placeholder="Informe fatos, dados ou orientações que devem ser considerados na revisão.",
                lines=5,
            )
            with gr.Row():
                with gr.Column(scale=8, min_width=0):
                    pass
                with gr.Column(scale=4, min_width=0):
                    apply_revision_button = gr.Button("Aplicar revisão", variant="primary")
                with gr.Column(scale=8, min_width=0):
                    pass

    with gr.Tab("Processo"):
        gr.Markdown("# 📝 Processo de Geração do Registro")
        gr.Markdown(
            "Nesta aba, você pode acompanhar o passo a passo do processo de geração do registro de execução."
            "Cada etapa será exibida conforme o agente avança na criação do texto final."
        )
        
        process_output = gr.Textbox(
            label="Saída do Processo",
            lines=20,
            max_lines=20,
            interactive=False,
            elem_id="process-output",
        )

    with gr.Tab("Prompts"):
        gr.Markdown("# Configuração dos prompts")
        gr.Markdown(
            "Edite os quatro prompts abaixo mantendo o formato JSON. "
            "As alterações serão usadas nas próximas gerações e revisões."
        )
        with gr.Row():
            with gr.Column(scale=20, min_width=0):
                prompts_editor = gr.Textbox(
                    label="Prompts (JSON)",
                    lines=15,
                    max_lines=18,
                    elem_id="prompts-editor",
                )
        with gr.Row():
            with gr.Column(scale=8, min_width=0):
                pass
            with gr.Column(scale=4, min_width=0):        
                update_prompts_button = gr.Button("Atualizar", variant="primary")
                prompts_status = gr.HTML(padding=True)
            with gr.Column(scale=8, min_width=0):
                pass    

    with gr.Tab("Base Adicional"):
        gr.Markdown("# Gerenciamento da base adicional")
        gr.Markdown(
            "Adicione documentos locais que serão usados pelo RAG. São aceitos arquivos .md, .txt e .pdf; "
            "subpastas não são necessárias para os uploads feitos aqui."
        )
        with gr.Row():
            with gr.Column(scale=4, min_width=0):
                pass
            with gr.Column(scale=8, min_width=0):
                additional_file_upload = gr.File(
                    label="Arquivos para adicionar",
                    file_count="multiple",
                    file_types=[".md", ".txt", ".pdf"],
                    type="filepath",
                )
            with gr.Column(scale=4, min_width=0):
                pass

        with gr.Row():
            with gr.Column(scale=8, min_width=0):
                pass
            with gr.Column(scale=4, min_width=0):
                upload_additional_button = gr.Button("Adicionar arquivos", variant="primary")
            with gr.Column(scale=8, min_width=0):
                pass

        with gr.Row():
            with gr.Column(scale=4, min_width=0):
                pass
            with gr.Column(scale=8, min_width=0):
                additional_files = gr.Dropdown(
                    label="Arquivos atualmente na base_adicional",
                    choices=list_additional_files(),
                    value=None,
                    interactive=True,
                )
            with gr.Column(scale=4, min_width=0):
                pass

        with gr.Row():
            with gr.Column(scale=8, min_width=0):
                pass
            with gr.Column(scale=4, min_width=0):
                delete_additional_button = gr.Button("Excluir arquivo selecionado")
            with gr.Column(scale=8, min_width=0):
                pass

        additional_files_status = gr.HTML(
            status_html(
                "Os arquivos só entram no RAG depois que você clicar em 'Gerar Base' na aba Principal.",
                color="#ef6c00",
            ),
            padding=True,
        )

    with gr.Tab("Chaves"):
        gr.Markdown("# Chaves de acesso")
        gr.Markdown(
            "Configure a chave do Gemini e, opcionalmente, a chave do Tavily. Para Azure OpenAI, configure "
            "endpoint e deployment; a autenticação é feita com a conta autenticada no Azure CLI."
        )

        with gr.Row():
            with gr.Column(scale=1):
                pass
            with gr.Column(scale=10):
                gemini_key_input = gr.Textbox(
                    label="GEMINI_API_KEY",
                    type="password",
                    placeholder="Cole sua chave do Gemini",
                )
            with gr.Column(scale=1):
                pass

        with gr.Row():
            with gr.Column(scale=1):
                pass
            with gr.Column(scale=10):
                azure_endpoint_input = gr.Textbox(
                    label="AZURE_OPENAI_ENDPOINT",
                    placeholder="https://ai-cdata-llmapi-csb-brs-001.cognitiveservices.azure.com/",
                )
            with gr.Column(scale=1):
                pass

        with gr.Row():
            with gr.Column(scale=1):
                pass
            with gr.Column(scale=10):
                azure_deployment_input = gr.Textbox(
                    label="AZURE_OPENAI_DEPLOYMENT",
                    placeholder="gpt41mini-regexec",
                )
            with gr.Column(scale=1):
                pass

        with gr.Row():
            with gr.Column(scale=1):
                pass
            with gr.Column(scale=10):
                azure_api_version_input = gr.Textbox(
                    label="AZURE_OPENAI_API_VERSION",
                    value="2024-10-21",
                )
            with gr.Column(scale=1):
                pass

        with gr.Row():
            with gr.Column(scale=1):
                pass
            with gr.Column(scale=10):
                tavily_key_input = gr.Textbox(
                    label="TAVILY_API_KEY",
                    type="password",
                    placeholder="Opcional: cole sua chave do Tavily",
                )
            with gr.Column(scale=1):
                pass

        with gr.Row():
            with gr.Column(scale=8, min_width=0):
                pass
            with gr.Column(scale=4):
                save_keys_button = gr.Button("Salvar chaves", variant="primary")
            with gr.Column(scale=8, min_width=0):
                pass

        with gr.Row():
            with gr.Column(scale=12):
                keys_status = gr.HTML(
                    status_html(
                        "As chaves ficam salvas em .env e são aplicadas na sessão atual. O Tavily é opcional neste fluxo.",
                        color="#ef6c00",
                    ),
                    padding=True,
                )

    demo.load(
        fn=initial_rag_status,
        outputs=[status_box, gerar_base_button, rag_ready_state],
    ).then(
        fn=update_generate_button,
        inputs=[essay_topic, rag_ready_state],
        outputs=[generate_button, new_revision_button],
    )

    demo.load(fn=rag_info_html, outputs=[rag_info_box])

    demo.load(
        fn=lambda: load_api_key_settings(),
        outputs=[
            gemini_key_input,
            tavily_key_input,
            azure_endpoint_input,
            azure_deployment_input,
            azure_api_version_input,
        ],
    )

    save_keys_button.click(
        fn=save_api_key_settings,
        inputs=[
            gemini_key_input,
            tavily_key_input,
            azure_endpoint_input,
            azure_deployment_input,
            azure_api_version_input,
        ],
        outputs=[keys_status],
    )

    upload_additional_button.click(
        fn=upload_additional_files,
        inputs=[additional_file_upload],
        outputs=[additional_files, additional_files_status],
    )

    delete_additional_button.click(
        fn=delete_additional_file,
        inputs=[additional_files],
        outputs=[additional_files, additional_files_status],
    )

    demo.load(
        fn=lambda: refresh_additional_files(),
        outputs=[additional_files, additional_files_status],
    )

    # Associa o botão à função Python
    generate_button.click(
        fn=generate_essay,
        inputs=[essay_topic, temperature_slider, model_provider],
        outputs=[output_textbox, process_output, status_box, execution_state, new_revision_button, generate_button]
    )

    new_revision_button.click(
        fn=open_revision_modal,
        inputs=[],
        outputs=[review_modal]
    )

    apply_revision_button.click(
        fn=apply_revision,
        inputs=[execution_state, revision_material],
        outputs=[output_textbox, process_output, status_box, execution_state, new_revision_button, review_modal]
    )

    gerar_base_button.click(
        fn=preload_rag,
        outputs=[status_box, gerar_base_button]
    ).then(
        fn=lambda: True,
        outputs=[rag_ready_state]
    ).then(
        fn=update_generate_button,
        inputs=[essay_topic, rag_ready_state],
        outputs=[generate_button, new_revision_button]
    ).then(
        fn=rag_info_html,
        outputs=[rag_info_box]
    )

    essay_topic.change(
        fn=update_generate_button,
        inputs=[essay_topic, rag_ready_state],
        outputs=[generate_button, new_revision_button]
    )

    demo.load(fn=load_prompts_for_editor, outputs=[prompts_editor])
    demo.load(
        fn=None,
        js="""
        () => {
            const btn = document.querySelector('#gerar-base-button button') || document.querySelector('#gerar-base-button');
            if (btn) { btn.title = 'Gerar base do conhecimento'; }
        }
        """
    )

    update_prompts_button.click(
        fn=update_prompts,
        inputs=[prompts_editor],
        outputs=[prompts_editor, prompts_status],
    )


# Lança a interface
if __name__ == "__main__":
    demo.launch(
        share=False,
        show_error=True,
        inbrowser=False,
        allowed_paths=["."],
    )