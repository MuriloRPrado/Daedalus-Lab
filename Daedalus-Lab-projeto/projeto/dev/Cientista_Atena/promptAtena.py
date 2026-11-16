######################### BIBLIOTECAS ###################################
from Rotinas.dados_prompt import dados_projeto, em_json, requisitos_projeto, restricoes_projeto
#########################################################################

bloco_um = '''Execute a pesquisa de elementos químicos com base no projeto abaixo. Use suas instruções permanentes e seu formato de relatório.

Sua pergunta de pesquisa é: Quais elementos químicos contribuem ou podem auxiliar para que um material metálico depois de fabricado tenhas os valores de propriedades informados?'''

def gerar_prompt_atena(id_projeto: int) -> str:
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