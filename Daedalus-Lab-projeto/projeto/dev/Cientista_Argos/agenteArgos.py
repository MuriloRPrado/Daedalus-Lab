from agents import Agent
from Rotinas.configuracao import carregar_instrucao
from Rotinas.execucao_agentes import executar_agente
from Rotinas.ferramentas_agentes import FERRAMENTAS_ARGOS
from Rotinas.parecer_estruturado import ParecerArgos

# Limite de turnos (chamadas ao modelo) por execução; o padrão do SDK (10) não comporta a pesquisa completa.
MAX_TURNOS = 40

instrucao = carregar_instrucao("instrucoes_argos.md")

argos = Agent(
    name="Argos",
    instructions=instrucao,
    model="gpt-6.1-sol",
    tools=FERRAMENTAS_ARGOS,
    output_type=ParecerArgos,
)

def executar_pesquisa_argos(id_projeto: int, prompt: str) -> int:
    """Executa a pesquisa e devolve o ID do retorno gravado."""
    return executar_agente(argos, id_projeto, prompt, MAX_TURNOS)
