# app.py
import json
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
import markdown as markdown_lib
from backend import (
    PROMPT_KEYS,
    executar_revisao,
    graph,
    load_prompt_config,
    save_prompt_config,
)
from rag import build_rag_stores
import uuid


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


def preload_rag():
    """Carrega a base RAG somente quando o usuário solicita, via botão "Gerar Base"."""
    yield (
        status_html("Carregando base de conhecimento...", color="#d32f2f"),
        gr.update(interactive=False),
        gr.update(),
    )
    build_rag_stores()
    yield (
        status_html("Base de conhecimento pronta. Você pode incluir o relato e gerar o registro.", color="#2e7d32"),
        gr.update(visible=False),
        gr.update(visible=True, interactive=False),
    )


def update_generate_button(topic: str, rag_ready: bool):
    can_generate = bool(rag_ready) and bool((topic or "").strip())
    return gr.update(interactive=can_generate)


def load_prompts_for_editor():
    return json.dumps(load_prompt_config(), ensure_ascii=False, indent=2)


def render_about_html() -> str:
    """Converte Sobre.md em HTML, embutindo a imagem do grafo como data URI."""
    about_text = Path("Sobre.md").read_text(encoding="utf-8")
    image_path = Path("grafo_projeto.png")
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
def generate_essay(topic: str, temperatura: float):
    """
    Roda o grafo do agente para gerar uma redação e transmite as saídas em tempo real.
    A aba principal mostra apenas o rascunho final; a aba de processo mostra o log completo.
    """
    build_rag_stores()
    yield "", "", status_html("Carregando base de conhecimento e gerando registro...", color="#d32f2f"), None, gr.update(interactive=False)

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
    }

    process_log = ""
    final_draft = ""
    status = status_html("Base pronta. Iniciando o processo de geração...", color="#ef6c00")

    for s in graph.stream(initial_state, thread_config):
        step_output = list(s.values())[0]
        initial_state.update(step_output)

        if 'plano' in step_output:
            status = status_html("Planejando a redação...", color="#ef6c00")
            process_log += f"PASSO 1: 📝 PLANO GERADO:\n{step_output['plano'][0]['text']}\n\n"
        elif 'conteudo' in step_output:
            status = status_html("Buscando e organizando o contexto de pesquisa...", color="#f9a825")
            search_content = "\n".join(step_output['conteudo'])
            process_log += f"PASSO 2: 🔍 CONTEÚDO DE PESQUISA:\n{search_content}\n\n"
        elif 'rascunho' in step_output:
            status = status_html("Gerando o rascunho final...", color="#ef6c00")
            final_draft = step_output['rascunho'][0]['text']
            process_log += f"PASSO 3: ✍️ RASCUNHO GERADO:\n{final_draft}\n\n"
        elif 'critica' in step_output:
            status = status_html("Revisando e avaliando o texto...", color="#ef6c00")
            process_log += f"PASSO 4: 🧐 CRÍTICA E REVISÃO:\n{step_output['critica'][0]['text']}\n\n"

        process_log += "---" * 20 + "\n\n"
        initial_state["_process_log"] = process_log
        yield final_draft, process_log, status, initial_state, gr.update(interactive=False)

    status = status_html("Registro concluído com sucesso.", color="#2e7d32")
    initial_state["_process_log"] = process_log
    yield final_draft, process_log, status, initial_state, gr.update(interactive=True)


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
        state["rascunho"],
        state.get("_process_log", ""),
        status,
        state,
        gr.update(interactive=False),
        gr.update(visible=True),
    )

    updated_state = executar_revisao(state, material_revisao.strip())
    process_log = state.get("_process_log", "") + (
        f"MATERIAL ADICIONAL PARA A REVISÃO:\n{material_revisao.strip() or '[Nenhum material adicional informado]'}\n\n"
        f"PASSO 4: 🧐 CRÍTICA E REVISÃO:\n{updated_state['critica']}\n\n"
        f"PASSO 3: ✍️ RASCUNHO REVISADO:\n{updated_state['rascunho']}\n\n"
        + "---" * 20
        + "\n\n"
    )
    status = status_html("Revisão concluída. Você pode solicitar outra revisão.", color="#2e7d32")
    yield updated_state["rascunho"], process_log, status, updated_state, gr.update(interactive=True), gr.update(visible=False)

# --- Criação da Interface Gradio ---
with gr.Blocks(
    css="#process-output textarea { overflow-y: auto !important; }",
    theme=gr.themes.Default(spacing_size="sm", text_size="lg"),
) as demo:

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
                new_revision_button = gr.Button("Solicitar revisão", interactive=False, visible=False)
            with gr.Column(scale=2, min_width=0):
                generate_button = gr.Button("Gerar Registro", variant="primary", interactive=False)

        output_textbox = gr.Textbox(label="Redação Final", lines=10, max_lines=12)
        execution_state = gr.State(value=None)
        rag_ready_state = gr.State(value=False)

        with Modal(visible=False) as review_modal:
            gr.Markdown("### Material adicional para a revisão")
            revision_material = gr.Textbox(
                label="Texto para acrescentar",
                placeholder="Informe fatos, dados ou orientações que devem ser considerados na revisão.",
                lines=5,
            )
            apply_revision_button = gr.Button("Aplicar revisão", variant="primary")

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

    with gr.Tab("Sobre"):
        gr.HTML(render_about_html())

    # Associa o botão à função Python
    generate_button.click(
        fn=generate_essay,
        inputs=[essay_topic, temperature_slider],
        outputs=[output_textbox, process_output, status_box, execution_state, new_revision_button]
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
        outputs=[status_box, gerar_base_button, new_revision_button]
    ).then(
        fn=lambda: True,
        outputs=[rag_ready_state]
    ).then(
        fn=update_generate_button,
        inputs=[essay_topic, rag_ready_state],
        outputs=[generate_button]
    )

    essay_topic.change(
        fn=update_generate_button,
        inputs=[essay_topic, rag_ready_state],
        outputs=[generate_button]
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