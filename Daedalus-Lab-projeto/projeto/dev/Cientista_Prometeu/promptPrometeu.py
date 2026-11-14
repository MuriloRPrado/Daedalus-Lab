######################### BIBLIOTECAS ###################################
from Rotinas.dados_prompt import dados_projeto, restricoes_projeto, requisitos_projeto, em_json
#########################################################################

bloco_um = '''Execute a pesquisa conforme as informações descritas abaixo. Use suas instruções permanentes.

Sua pergunta de pesquisa é: Com base nas informações recebidas, quais materiais existentes atendem aos requisitos fornecidos e qual a composição química de cada material encontrado?
Se não houver evidência suficiente para indicar candidatos, diga isso e explique o impedimento. Se faltarem dados do projeto, avance apenas nas verificações independentes; não invente condições ou atendimento para concluir a sua pesquisa.'''

def gerar_prompt_prometeu(id_projeto: int) -> str:
    dados_json = em_json(dados_projeto(id_projeto))
    restricao_json = em_json(restricoes_projeto(id_projeto))
    requisitos_json = em_json(requisitos_projeto(id_projeto))

    partes = [
        bloco_um,
        "## Dados do Projeto",
        dados_json,
        "### Restrições Químicas",
        restricao_json,
        "### Requisitos de Propriedades",
        requisitos_json
    ]
    return "\n\n".join(partes)

