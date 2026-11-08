from agents import Agent
from Rotinas.configuracao import carregar_instrucao
from Rotinas.execucao_agentes import executar_agente
from Rotinas.ferramentas_agentes import FERRAMENTAS_ATENA
from Rotinas.parecer_estruturado import ParecerAtena

# Limite de turnos (chamadas ao modelo) por execução; o padrão do SDK (10) não comporta a pesquisa completa.
MAX_TURNOS = 40

instrucao = carregar_instrucao("instrucoes_atena.md")

atena = Agent(
    name="Atena",
    instructions=instrucao,
    model="gpt-6.1-sol",
    tools=FERRAMENTAS_ATENA,
    output_type=ParecerAtena,
)

def executar_pesquisa_atena(id_projeto: int, prompt: str) -> int:
    """Executa a pesquisa e devolve o ID do retorno gravado."""
    return executar_agente(atena, id_projeto, prompt, MAX_TURNOS)
