from agents import Agent
from Rotinas.configuracao import carregar_instrucao
from Rotinas.execucao_agentes import executar_agente
from Rotinas.ferramentas_agentes import FERRAMENTAS_PROMETEU

# Limite de turnos (chamadas ao modelo) por execução; o padrão do SDK (10) não comporta a pesquisa completa.
MAX_TURNOS = 40

instrucao = carregar_instrucao("instrucoes_prometeu.md")

prometeu = Agent(
    name="Prometeu",
    instructions=instrucao,
    model="gpt-6.1-sol",
    tools=FERRAMENTAS_PROMETEU,
)

def executar_pesquisa_prometeu(id_projeto: int, prompt: str) -> int:
    """Executa a pesquisa e devolve o ID do retorno gravado."""
    return executar_agente(prometeu, id_projeto, prompt, MAX_TURNOS)
