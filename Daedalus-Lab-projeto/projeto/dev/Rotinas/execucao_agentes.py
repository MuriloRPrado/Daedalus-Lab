######################### BIBLIOTECAS ###################################
from agents import Agent, RunConfig, Runner
from Rotinas.cache_fontes import definir_contexto
from Rotinas.retorno_cientistas import salvar_retorno
#########################################################################

NOME_FLUXO = "Daedalus Lab"


def executar_agente(agente: Agent, id_projeto: int, prompt: str, max_turnos: int) -> int:
    """Executa o agente, grava o retorno e devolve o id_ret_cientistas.

    As execuções de um mesmo projeto ficam agrupadas no rastreamento da OpenAI
    (group_id "projeto-<id>").
    """
    definir_contexto(id_projeto, agente.name)
    configuracao = RunConfig(
        workflow_name=f"{NOME_FLUXO} - {agente.name}",
        group_id=f"projeto-{id_projeto}",
        trace_metadata={"id_projeto": str(id_projeto), "agente": agente.name},
    )
    retorno = Runner.run_sync(agente, prompt, max_turns=max_turnos, run_config=configuracao)
    saida = retorno.final_output
    texto = saida.em_markdown() if hasattr(saida, "em_markdown") else str(saida)
    return salvar_retorno(id_projeto, agente.name, texto)
