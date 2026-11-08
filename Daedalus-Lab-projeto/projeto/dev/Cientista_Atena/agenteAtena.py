from pathlib import Path
from Rotinas.retorno_cientistas import salvar_retorno
from Rotinas.exportar_retorno import consulta_arquivo
from Consultas_Externas.consensus_api import buscar_artigos, perguntar_estudos, pesquisa_aprofundada
from Consultas_Externas.consultaMP import buscar_materiais, buscar_materiais_por_elementos, consultar_material_por_id, consultar_estabilidade
from agents import Agent, Runner, function_tool, WebSearchTool

caminho = Path(r"C:\Users\Usuário\Desktop\Portfólio\Daedalus-Lab\Arquivos\Instrução\instrucoes_atena.md")
instrucao = caminho.read_text(encoding="utf-8")

@function_tool
def perguntar_estudos_tool(
    pergunta: str,
    ids_artigos: list[str] | None = None,
    tempo_limite: float | None = None,
) -> dict:
    """Consulta estudos no Consensus e retorna uma resposta com fontes.

    Args:
        pergunta: Pergunta científica a pesquisar.
        ids_artigos: IDs internos do Consensus, quando disponíveis.
        tempo_limite: Tempo máximo de espera local, em segundos.
    """
    return perguntar_estudos(
        pergunta=pergunta,
        ids_artigos=ids_artigos,
        tempo_limite=tempo_limite,
    )

@function_tool
def pesquisa_aprofundada_tool(
    pergunta: str,
    ids_artigos: list[str] | None = None,
    tempo_limite: float | None = None,
) -> dict:
    """Realiza pesquisa aprofundada no Consensus com fontes.

    Args:
        pergunta: Pergunta científica a investigar.
        ids_artigos: IDs internos de artigos do Consensus, quando disponíveis.
        tempo_limite: Tempo máximo de espera local, em segundos.
    """
    return pesquisa_aprofundada(
        pergunta=pergunta,
        ids_artigos=ids_artigos,
        tempo_limite=tempo_limite,
    )

@function_tool
def buscar_materiais_por_elementos_tool(
    elementos: list[str],
    elementos_excluidos: list[str] | None = None,
    limite: int = 10,
    densidade_min: float | None = None,
    densidade_max: float | None = None,
) -> list[dict]:
    """Busca materiais por elementos e faixa opcional de densidade.

    Args:
        elementos: Símbolos dos elementos obrigatórios, como Al e Mg.
        elementos_excluidos: Símbolos dos elementos que devem ser excluídos.
        limite: Quantidade máxima de resultados.
        densidade_min: Densidade mínima em g/cm³. Informe junto da máxima.
        densidade_max: Densidade máxima em g/cm³. Informe junto da mínima.
    """
    if (densidade_min is None) != (densidade_max is None):
        raise ValueError(
            "Informe as duas densidades ou deixe ambas sem valor."
        )

    densidade = None

    if densidade_min is not None and densidade_max is not None:
        densidade = (densidade_min, densidade_max)

    return buscar_materiais_por_elementos(
        elementos=elementos,
        elementos_excluidos=elementos_excluidos,
        limite=limite,
        densidade=densidade,
    )

atena = Agent(
    name="Atena",
    instructions=instrucao,
    model="gpt-6.1-sol",
    tools=[WebSearchTool(), function_tool(consulta_arquivo), function_tool(buscar_artigos), perguntar_estudos_tool, pesquisa_aprofundada_tool, function_tool(buscar_materiais), buscar_materiais_por_elementos_tool, function_tool(consultar_material_por_id), function_tool(consultar_estabilidade)]
)

def executar_pesquisa_atena(id_projeto: int, prompt: str) -> str:
    retorno = Runner.run_sync(atena, prompt)
    salvar_retorno(id_projeto, "Atena", retorno.final_output)
    return "Pesquisa da agente Atena foi concluída"