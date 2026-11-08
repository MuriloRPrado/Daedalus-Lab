from agents import Agent
from Rotinas.configuracao import carregar_instrucao
from Rotinas.execucao_agentes import executar_agente
from Rotinas.ferramentas_agentes import FERRAMENTAS_TEMIS

# Limite de turnos (chamadas ao modelo) por execução; o padrão do SDK (10) não comporta a pesquisa completa.
MAX_TURNOS = 80

instrucao = carregar_instrucao("instrucoes_temis.md")

temis = Agent(
    name="Têmis",
    instructions=instrucao,
    model="gpt-6.1-sol",
    tools=FERRAMENTAS_TEMIS,
)

def executar_pesquisa_temis(id_projeto: int, prompt: str) -> int:
    """Executa a pesquisa e devolve o ID do retorno gravado."""
    return executar_agente(temis, id_projeto, prompt, MAX_TURNOS)
