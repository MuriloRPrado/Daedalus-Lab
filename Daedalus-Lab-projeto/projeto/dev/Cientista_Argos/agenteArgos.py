from agents import Agent, Runner
from Rotinas.cache_fontes import definir_contexto
from Rotinas.configuracao import carregar_instrucao
from Rotinas.ferramentas_agentes import FERRAMENTAS_ARGOS
from Rotinas.retorno_cientistas import salvar_retorno

# Limite de turnos (chamadas ao modelo) por execução; o padrão do SDK (10) não comporta a pesquisa completa.
MAX_TURNOS = 40

instrucao = carregar_instrucao("instrucoes_argos.md")

argos = Agent(
    name="Argos",
    instructions=instrucao,
    model="gpt-6.1-sol",
    tools=FERRAMENTAS_ARGOS,
)

def executar_pesquisa_argos(id_projeto: int, prompt: str) -> str:
    definir_contexto(id_projeto, "Argos")
    retorno = Runner.run_sync(argos, prompt, max_turns=MAX_TURNOS)
    salvar_retorno(id_projeto, "Argos", retorno.final_output)
    return "Pesquisa do agente Argos foi concluída"
