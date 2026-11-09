"""Calíope em quatro etapas sequenciais: Composição, Propriedades, Estrutura Cristalina e Relatório.

As três primeiras pesquisam e gravam no banco e devolvem a cobertura estruturada. Depois de cada
uma, o código confere no banco os itens sem dado e sem lacuna justificada e roda a etapa mais uma
vez, só para eles. O Relatório não pesquisa: escreve as seções de análise, e as seções com dados
gravados são montadas direto do banco.
"""
import logging

from agents import Agent
from Cientista_Caliope.promptCaliope import complemento_pendencias
from Rotinas import caracterizacao_estruturada as ce
from Rotinas.configuracao import carregar_instrucao
from Rotinas.execucao_agentes import executar_saida
from Rotinas.ferramentas_agentes import (
    FERRAMENTAS_CALIOPE_COMPOSICAO, FERRAMENTAS_CALIOPE_ESTRUTURA, FERRAMENTAS_CALIOPE_PROPRIEDADES,
)
from Rotinas.registro_materiais import listar_materiais_projeto
from Rotinas.relatorio_final import RelatorioCaliope, montar_relatorio
from Rotinas.retorno_cientistas import salvar_retorno

MODELO = "gpt-6.1-sol"

# Limite de turnos (chamadas ao modelo) por execução; o padrão do SDK (10) não comporta a pesquisa.
MAX_TURNOS_COMPOSICAO = 60
MAX_TURNOS_PROPRIEDADES = 120
MAX_TURNOS_ESTRUTURA = 80
MAX_TURNOS_RELATORIO = 5

caliope_composicao = Agent(
    name="Calíope - Composição",
    instructions=carregar_instrucao("instrucao_caliope_composicao.md"),
    model=MODELO,
    tools=FERRAMENTAS_CALIOPE_COMPOSICAO,
    output_type=ce.CoberturaComposicao,
)

caliope_propriedades = Agent(
    name="Calíope - Propriedades",
    instructions=carregar_instrucao("instrucao_caliope_propriedades.md"),
    model=MODELO,
    tools=FERRAMENTAS_CALIOPE_PROPRIEDADES,
    output_type=ce.CoberturaPropriedades,
)

caliope_estrutura = Agent(
    name="Calíope - Estrutura Cristalina",
    instructions=carregar_instrucao("instrucao_caliope_estrutura.md"),
    model=MODELO,
    tools=FERRAMENTAS_CALIOPE_ESTRUTURA,
    output_type=ce.CoberturaEstrutura,
)

caliope_relatorio = Agent(
    name="Calíope - Relatório",
    instructions=carregar_instrucao("instrucao_caliope_relatorio.md"),
    model=MODELO,
    output_type=RelatorioCaliope,
)

SEM_MATERIAIS = "Nenhum material registrado por Têmis para este projeto: a etapa não foi executada."


def _executar_com_cobertura(agente: Agent, id_projeto: int, prompt: str, max_turnos: int,
                            pendencias, chave: str, descricao: str) -> int:
    """Executa a etapa, repete uma vez para os itens pendentes e grava o retorno combinado."""
    if not listar_materiais_projeto(id_projeto)["materiais"]:
        return salvar_retorno(id_projeto, agente.name, SEM_MATERIAIS)
    saida = executar_saida(agente, id_projeto, prompt, max_turnos)
    pendentes = pendencias(id_projeto, saida)
    if pendentes:
        print(f"{agente.name}: {len(pendentes)} item(ns) sem dado e sem justificativa; executando de novo só para eles")
        try:
            complemento = executar_saida(agente, id_projeto, complemento_pendencias(prompt, pendentes), max_turnos)
        except Exception as erro:
            # Os dados da primeira execução já estão gravados: segue com eles e registra a falha.
            logging.exception("Falha na segunda execução de %s do projeto %s", agente.name, id_projeto)
            complemento = None
            saida.observacoes_gerais = "\n\n".join(t for t in (
                saida.observacoes_gerais.strip(), f"A segunda execução, restrita às pendências, falhou: {type(erro).__name__}.") if t)
        saida = ce.combinar(saida, complemento, chave)
        pendentes = pendencias(id_projeto, saida)
    texto = "\n\n".join(t for t in (saida.em_markdown(), ce.markdown_pendencias(pendentes, descricao)) if t)
    return salvar_retorno(id_projeto, agente.name, texto)


def executar_caliope_composicao(id_projeto: int, prompt: str) -> int:
    return _executar_com_cobertura(caliope_composicao, id_projeto, prompt, MAX_TURNOS_COMPOSICAO,
                                   ce.pendencias_composicao, "id_material", "composição")


def executar_caliope_propriedades(id_projeto: int, prompt: str) -> int:
    return _executar_com_cobertura(caliope_propriedades, id_projeto, prompt, MAX_TURNOS_PROPRIEDADES,
                                   ce.pendencias_propriedades, "id_mat_estado", "propriedades")


def executar_caliope_estrutura(id_projeto: int, prompt: str) -> int:
    return _executar_com_cobertura(caliope_estrutura, id_projeto, prompt, MAX_TURNOS_ESTRUTURA,
                                   ce.pendencias_estrutura, "id_mat_estado", "estrutura cristalina")


def executar_caliope_relatorio(id_projeto: int, prompt: str) -> int:
    """Gera as seções de análise, monta o relatório final e grava no banco e na pasta Arquivos/Retornos."""
    analise = executar_saida(caliope_relatorio, id_projeto, prompt, MAX_TURNOS_RELATORIO)
    return salvar_retorno(id_projeto, caliope_relatorio.name, montar_relatorio(id_projeto, analise), gerar_arquivo=True)
