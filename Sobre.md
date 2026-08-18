# Sobre o Gerador de Registro de Execução (PGD)

Esta aplicação ajuda o usuário a transformar um relato informal de atividades em um **registro de execução** formal, alinhado ao Programa de Gestão (PGD), utilizando um agente construído com LangGraph e o modelo Gemini.

## Como funciona

1. **Gerar Base**: antes de gerar qualquer registro, o usuário carrega a base de conhecimento (RAG), composta por:
   - páginas normativas oficiais (e seus PDFs vinculados);
   - todos os arquivos `.md`, `.txt` e `.pdf` colocados na pasta `base_adicional` (incluindo os documentos fornecidos no projeto).
2. **Relato**: o usuário descreve, de forma livre, o que fez ou o que sua unidade fez no período.
3. **Geração do registro**: o agente segue o fluxo abaixo para planejar, pesquisar, redigir e revisar automaticamente o registro.
4. **Revisão sob demanda**: após a primeira geração, o usuário pode solicitar novas revisões a qualquer momento, podendo acrescentar material adicional por meio de um modal.
5. **Prompts configuráveis**: os quatro prompts que orientam o agente podem ser editados diretamente pela interface, na aba "Prompts", e ficam armazenados em `prompts.json`.

## Fluxo do agente (LangGraph)

![Grafo do agente](grafo_projeto.png)

- **planejador**: organiza o relato do usuário em um esboço estruturado.
- **pesquisa_plano**: gera consultas e recupera contexto relevante, restrito às fontes normativas e aos documentos locais indexados.
- **gerar**: redige o registro de execução, incorporando o plano, o contexto pesquisado e, quando houver, o rascunho anterior, a crítica e material adicional informado pelo usuário.
- **refletir**: analisa o rascunho gerado e produz uma crítica com recomendações.
- O ciclo `gerar -> refletir -> gerar` ocorre automaticamente uma vez na primeira geração, e pode ser repetido manualmente pelo usuário por meio do botão "Solicitar revisão".

## Principais controles da interface

- **Criatividade**: ajusta a temperatura do modelo, de respostas mais sóbrias a mais criativas.
- **Solicitar revisão**: abre um modal para que o usuário, opcionalmente, acrescente material adicional antes de uma nova revisão.
- **Aba Processo**: mostra o passo a passo completo da geração, incluindo o contexto de pesquisa recuperado e as críticas realizadas.
- **Aba Prompts**: permite editar e validar, em formato JSON, os prompts usados pelo agente.
- **Pasta base_adicional**: permite acrescentar quantos documentos locais forem necessários para enriquecer o contexto do RAG. Subpastas também são lidas.

## Restrições de pesquisa

A pesquisa do agente é restrita às fontes configuradas no RAG (páginas normativas, PDFs vinculados e documentos locais do projeto). Não há busca livre na internet.
