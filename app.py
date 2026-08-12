# app.py
import gradio as gr
from backend import graph  # Importa o grafo do seu novo backend
import uuid

# --- Função que será chamada pelo Gradio para rodar o agente ---
def generate_essay(topic: str, maximo_revisoes: int):
    """
    Roda o grafo do agente para gerar uma redação e transmite as saídas em tempo real.
    """
    thread_id = str(uuid.uuid4())
    thread_config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        'tarefa': topic,
        "maximo_revisoes": maximo_revisoes,
        "numero_revisao": 0,
        "plano": "",
        "rascunho": "",
        "critica": "",
        "conteudo": []
    }

    full_output = ""
    # Itera sobre o stream do grafo para obter as saídas passo a passo
    for s in graph.stream(initial_state, thread_config):
        # A API do LangGraph retorna um dicionário de dicionários
        step_output = list(s.values())[0]

        # Formata a saída para ser mais legível na interface
        if 'plano' in step_output:
            full_output += f"### 📝 Plano Gerado:\n{step_output['plano'][0]['text']}\n\n"
        elif 'conteudo' in step_output:
            # Exibe o conteúdo da pesquisa
            search_content = "\n".join(step_output['conteudo'])
            full_output += f"### 🔍 Conteúdo de Pesquisa:\n{search_content}\n\n"
        elif 'rascunho' in step_output:
            full_output += f"### ✍️ Rascunho Gerado:\n{step_output['rascunho'][0]['text']}\n\n"
        elif 'critica' in step_output:
            full_output += f"### 🧐 Crítica e Revisão:\n{step_output['critica'][0]['text']}\n\n"

        # Adiciona uma linha divisória para separar os passos
        full_output += "---" * 20 + "\n\n"

        yield full_output
    
    yield full_output

# --- Criação da Interface Gradio ---
with gr.Blocks(theme=gr.themes.Default(spacing_size='sm', text_size="lg")) as demo:
    gr.Markdown("# 🤖 Gerador de Registro de Execução de Plano de Trabalho (PGD)")
    gr.Markdown(
        "Diga-me o que fez no período de tempo em questão (hoje, ou esta semana, por exemplo)."
        "Seja tão informal quanto quiser. O agente vai planejar, pesquisar, rascunhar, revisar e gerar o texto final."
    )

    with gr.Row():
        with gr.Column(scale=15, min_width=0):
            essay_topic = gr.Textbox(label="Relato", placeholder="Ex: Participei de N reuniões, fiz X atividades, etc.", lines=2, max_lines=4)
        with gr.Column(scale=3, min_width=0):
            maximo_revisoes_slider = gr.Slider(minimum=0, maximum=3, step=1, value=1, label="Número Máximo de Revisões")
        with gr.Column(scale=2, min_width=0):
            generate_button = gr.Button("Gerar Registro", variant="primary")

    output_textbox = gr.Textbox(label="Processo e Redação Final", lines=12, max_lines=20)

    # Associa o botão à função Python
    generate_button.click(
        fn=generate_essay,
        inputs=[essay_topic, maximo_revisoes_slider],
        outputs=output_textbox
    )

# Lança a interface
if __name__ == "__main__":
    demo.launch(share=False)