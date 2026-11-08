from agents import Agent, Runner
from Rotinas.cache_fontes import definir_contexto
from Rotinas.configuracao import carregar_instrucao
from Rotinas.ferramentas_agentes import FERRAMENTAS_TEMIS
from Rotinas.retorno_cientistas import salvar_retorno

# Limite de turnos (chamadas ao modelo) por execução; o padrão do SDK (10) não comporta a pesquisa completa.
MAX_TURNOS = 80

instrucao = carregar_instrucao("instrucoes_temis.md")

temis = Agent(
    name="Têmis",
    instructions=instrucao,
    model="gpt-6.1-sol",
    tools=FERRAMENTAS_TEMIS,
)

def executar_pesquisa_temis(id_projeto: int, prompt: str) -> str:
    definir_contexto(id_projeto, "Têmis")
    retorno = Runner.run_sync(temis, prompt, max_turns=MAX_TURNOS)
    salvar_retorno(id_projeto, "Têmis", retorno.final_output)
    return "Registro da agente Têmis foi concluído"
