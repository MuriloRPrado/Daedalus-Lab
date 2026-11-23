"""Calíope - Comparação: verifica se as composições geradas pelo VAE existem em materiais metálicos reais
e monta o relatório final.

1. Compara com a base de ligas reais do VAE (sem custo). A agente só pesquisa na web as composições
   sem liga a até 10 pp nessa base.
2. Calíope - Relatório escreve a Introdução e a Conclusão a partir das tabelas do projeto.
O relatório vai para retorno_cientistas e para Arquivos/Retornos.
"""
from agents import Agent

from Cientista_Caliope.promptCaliopeComparacao import gerar_prompt_caliope_relatorio
from Rotinas import comparacao_composicoes as cc
from Rotinas.configuracao import carregar_instrucao
from Rotinas.execucao_agentes import executar_saida
from Rotinas.fases_composicoes import fases_projeto
from Rotinas.ferramentas_agentes import FERRAMENTAS_CALIOPE_COMPARACAO
from Rotinas.retorno_cientistas import salvar_retorno

MODELO = "gpt-6.1-sol"
MAX_TURNOS_COMPARACAO = 40
MAX_TURNOS_RELATORIO = 3

caliope_comparacao = Agent(
    name="Calíope - Comparação",
    instructions=carregar_instrucao("instrucao_caliope_comparacao.md"),
    model=MODELO,
    tools=FERRAMENTAS_CALIOPE_COMPARACAO,
    output_type=cc.SaidaComparacao,
)

caliope_relatorio = Agent(
    name="Calíope - Relatório",
    instructions=carregar_instrucao("instrucao_caliope_relatorio.md"),
    model=MODELO,
    output_type=cc.TextosRelatorio,
)


def executar_caliope_comparacao(id_projeto: int, prompt: str) -> int:
    analise = cc.analisar_base(id_projeto)
    saida = None
    if cc.sem_correspondencia(analise):
        saida = executar_saida(caliope_comparacao, id_projeto, prompt, MAX_TURNOS_COMPARACAO)
    consolidado = cc.consolidar(analise, saida)
    fases = fases_projeto(id_projeto)
    textos = executar_saida(caliope_relatorio, id_projeto,
                            gerar_prompt_caliope_relatorio(id_projeto, consolidado, fases), MAX_TURNOS_RELATORIO)
    return salvar_retorno(id_projeto, caliope_comparacao.name,
                          cc.montar_relatorio(id_projeto, consolidado, fases, textos), gerar_arquivo=True)
