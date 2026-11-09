######################### BIBLIOTECAS ###################################
from agents import Agent, RunConfig, Runner
from Rotinas.cache_fontes import definir_contexto
from Rotinas.retorno_cientistas import salvar_retorno
#########################################################################

NOME_FLUXO = "Daedalus Lab"


def executar_saida(agente: Agent, id_projeto: int, prompt: str, max_turnos: int):
    """Executa o agente e devolve a saída final (texto ou objeto do output_type), sem gravar.

    As execuções de um mesmo projeto ficam agrupadas no rastreamento da OpenAI
    (group_id "projeto-<id>").
    """
    definir_contexto(id_projeto, agente.name)
    configuracao = RunConfig(
        workflow_name=f"{NOME_FLUXO} - {agente.name}",
        group_id=f"projeto-{id_projeto}",
        trace_metadata={"id_projeto": str(id_projeto), "agente": agente.name},
    )
    return Runner.run_sync(agente, prompt, max_turns=max_turnos, run_config=configuracao).final_output


def em_texto(saida) -> str:
    return saida.em_markdown() if hasattr(saida, "em_markdown") else str(saida)


def executar_agente(agente: Agent, id_projeto: int, prompt: str, max_turnos: int) -> int:
    """Executa o agente, grava o retorno e devolve o id_ret_cientistas."""
    saida = executar_saida(agente, id_projeto, prompt, max_turnos)
    return salvar_retorno(id_projeto, agente.name, em_texto(saida))
