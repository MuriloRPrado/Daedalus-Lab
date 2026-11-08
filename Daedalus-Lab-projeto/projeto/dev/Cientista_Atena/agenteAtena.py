from agents import Agent, Runner
from Rotinas.cache_fontes import definir_contexto
from Rotinas.configuracao import carregar_instrucao
from Rotinas.ferramentas_agentes import FERRAMENTAS_ATENA
from Rotinas.retorno_cientistas import salvar_retorno

# Limite de turnos (chamadas ao modelo) por execução; o padrão do SDK (10) não comporta a pesquisa completa.
MAX_TURNOS = 40

instrucao = carregar_instrucao("instrucoes_atena.md")

atena = Agent(
    name="Atena",
    instructions=instrucao,
    model="gpt-6.1-sol",
    tools=FERRAMENTAS_ATENA,
)

def executar_pesquisa_atena(id_projeto: int, prompt: str) -> str:
    definir_contexto(id_projeto, "Atena")
    retorno = Runner.run_sync(atena, prompt, max_turns=MAX_TURNOS)
    salvar_retorno(id_projeto, "Atena", retorno.final_output)
    return "Pesquisa da agente Atena foi concluída"
