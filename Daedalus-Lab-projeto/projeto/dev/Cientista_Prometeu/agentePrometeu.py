from agents import Agent, Runner
from Rotinas.cache_fontes import definir_contexto
from Rotinas.configuracao import carregar_instrucao
from Rotinas.ferramentas_agentes import FERRAMENTAS_PROMETEU
from Rotinas.retorno_cientistas import salvar_retorno

# Limite de turnos (chamadas ao modelo) por execução; o padrão do SDK (10) não comporta a pesquisa completa.
MAX_TURNOS = 40

instrucao = carregar_instrucao("instrucoes_prometeu.md")

prometeu = Agent(
    name="Prometeu",
    instructions=instrucao,
    model="gpt-6.1-sol",
    tools=FERRAMENTAS_PROMETEU,
)

def executar_pesquisa_prometeu(id_projeto: int, prompt: str) -> str:
    definir_contexto(id_projeto, "Prometeu")
    retorno = Runner.run_sync(prometeu, prompt, max_turns=MAX_TURNOS)
    salvar_retorno(id_projeto, "Prometeu", retorno.final_output)
    return "Pesquisa do agente Prometeu foi concluída"
