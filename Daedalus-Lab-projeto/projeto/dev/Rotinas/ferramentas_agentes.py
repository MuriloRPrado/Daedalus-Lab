"""Ferramentas (function tools) expostas aos agentes, montadas a partir das rotinas de Rotinas/.

Cada agente importa a sua lista (FERRAMENTAS_PROMETEU, FERRAMENTAS_ATENA etc.).
Ao incluir ou retirar uma ferramenta, atualize também a seção "Ferramentas" do arquivo
de instrução do agente em Arquivos/Instrução.
"""
######################### BIBLIOTECAS ###################################
import re
from functools import partial

from agents import WebSearchTool, function_tool
from sqlalchemy.exc import SQLAlchemyError

from Rotinas import materials_project as mp
from Rotinas.aflow_api import consultar_propriedades_aflow
from Rotinas.consulta_artigos import buscar_artigos_openalex, ler_artigo, localizar_pdf_aberto
from Rotinas.exportar_retorno import consultar_retorno_agente
from Rotinas.firecrawl_api import buscar_fichas_tecnicas, buscar_web, ler_pagina
from Rotinas.optimade_api import buscar_estruturas_calculadas, consultar_estrutura_calculada
from Rotinas.oqmd_api import consultar_estabilidade_oqmd
from Rotinas.registro_materiais import (
    listar_materiais_projeto, registrar_composicao, registrar_estado_material, registrar_fase_estrutura,
    registrar_fonte, registrar_material, registrar_valor_propriedade,
)
from Rotinas.wiki_api import buscar_material_wikidata, buscar_wikipedia, consultar_material_wikidata, ler_wikipedia
#########################################################################

_SEGREDO_NA_URL = re.compile(r"((?:api_?key|key|token|mailto)=)[^&\s]+", re.IGNORECASE)


def _erro_para_agente(ctx, erro: Exception) -> str:
    """Devolve ao agente o motivo da falha (validação, limite de créditos etc.), sem expor dados sensíveis."""
    if isinstance(erro, SQLAlchemyError):
        return "Falha ao acessar o banco de dados. Não repita a gravação; registre a falha no relatório."
    mensagem = _SEGREDO_NA_URL.sub(r"\1***", str(erro))[:1500]
    return f"Erro na ferramenta ({type(erro).__name__}): {mensagem}"


ferramenta = partial(function_tool, failure_error_function=_erro_para_agente)


@ferramenta
def buscar_materiais_mp(sistema_quimico: str, limite: int = 10) -> dict:
    """Busca fases no Materials Project pelo sistema químico (dados calculados por DFT).

    Args:
        sistema_quimico: Sistema químico com elementos separados por hífen (ex.: "Al-Mg"). Não aceita designação comercial.
        limite: Quantidade máxima de resultados (1 a 50).
    """
    return mp.buscar_materiais(sistema_quimico=sistema_quimico, limite=limite)


@ferramenta
def buscar_materiais_por_elementos_mp(
    elementos: list[str],
    elementos_excluidos: list[str] | None = None,
    limite: int = 10,
    densidade_min: float | None = None,
    densidade_max: float | None = None,
) -> dict:
    """Busca fases no Materials Project que contenham os elementos, com exclusões e faixa opcional de densidade (dados calculados por DFT).

    Args:
        elementos: Símbolos dos elementos que a fase deve conter (ex.: ["Al", "Mg"]).
        elementos_excluidos: Símbolos dos elementos que não podem estar na fase.
        limite: Quantidade máxima de resultados (1 a 50).
        densidade_min: Densidade mínima em g/cm³. Informe junto da máxima.
        densidade_max: Densidade máxima em g/cm³. Informe junto da mínima.
    """
    if (densidade_min is None) != (densidade_max is None):
        raise ValueError("Informe as duas densidades ou deixe ambas sem valor.")
    densidade = (densidade_min, densidade_max) if densidade_min is not None else None
    return mp.buscar_materiais_por_elementos(
        elementos=elementos, elementos_excluidos=elementos_excluidos, limite=limite, densidade=densidade
    )


@ferramenta
def consultar_material_mp(material_id: str) -> dict | None:
    """Consulta o resumo de um registro do Materials Project (fórmula, densidade, simetria, propriedades disponíveis).

    Args:
        material_id: ID retornado por uma busca, no formato "mp-1234".
    """
    return mp.consultar_material_por_id(material_id)


@ferramenta
def consultar_estrutura_cristalina_mp(material_id: str) -> dict | None:
    """Consulta a estrutura cristalina calculada de um registro do Materials Project (sistema cristalino, grupo espacial, parâmetros de rede).

    Args:
        material_id: ID retornado por uma busca, no formato "mp-1234".
    """
    return mp.consultar_estrutura_cristalina(material_id)


@ferramenta
def consultar_estabilidade_mp(material_id: str) -> dict | None:
    """Consulta a energia de formação e a estabilidade calculadas (energy above hull) de um registro do Materials Project.

    Args:
        material_id: ID retornado por uma busca, no formato "mp-1234".
    """
    return mp.consultar_estabilidade(material_id)


@ferramenta
def consultar_elasticidade_mp(material_id: str) -> dict | None:
    """Consulta as propriedades elásticas calculadas (módulos e tensor elástico, em GPa) de um registro do Materials Project.

    Args:
        material_id: ID retornado por uma busca, no formato "mp-1234".
    """
    return mp.consultar_elasticidade(material_id)


@ferramenta
def consultar_proveniencia_mp(material_id: str) -> dict | None:
    """Consulta a proveniência (origem e referências) dos dados de um registro do Materials Project.

    Args:
        material_id: ID retornado por uma busca, no formato "mp-1234".
    """
    return mp.consultar_proveniencia(material_id)


WEB = [
    WebSearchTool(),
    ferramenta(buscar_web),
    ferramenta(buscar_fichas_tecnicas),
    ferramenta(ler_pagina),
]
ARTIGOS = [
    ferramenta(buscar_artigos_openalex),
    ferramenta(localizar_pdf_aberto),
    ferramenta(ler_artigo),
]
WIKI = [
    ferramenta(buscar_wikipedia),
    ferramenta(ler_wikipedia),
    ferramenta(buscar_material_wikidata),
    ferramenta(consultar_material_wikidata),
]
MATERIALS_PROJECT = [
    buscar_materiais_mp,
    buscar_materiais_por_elementos_mp,
    consultar_material_mp,
    consultar_estrutura_cristalina_mp,
    consultar_estabilidade_mp,
    consultar_elasticidade_mp,
    consultar_proveniencia_mp,
]
CALCULADOS = [
    ferramenta(buscar_estruturas_calculadas),
    ferramenta(consultar_estrutura_calculada),
    ferramenta(consultar_propriedades_aflow),
    ferramenta(consultar_estabilidade_oqmd),
]
RELATORIO_ANTERIOR = ferramenta(consultar_retorno_agente)
FONTES_BANCO = ferramenta(registrar_fonte)
LISTAR_MATERIAIS = ferramenta(listar_materiais_projeto)

FERRAMENTAS_PROMETEU = [*WEB, *ARTIGOS, *WIKI, *MATERIALS_PROJECT, *CALCULADOS]

FERRAMENTAS_ATENA = [
    RELATORIO_ANTERIOR, *WEB, *ARTIGOS, *WIKI,
    buscar_materiais_mp, buscar_materiais_por_elementos_mp, consultar_material_mp,
    consultar_elasticidade_mp, consultar_estabilidade_mp,
    ferramenta(consultar_propriedades_aflow), ferramenta(consultar_estabilidade_oqmd),
]

FERRAMENTAS_ARGOS = [RELATORIO_ANTERIOR, *WEB, *ARTIGOS, *WIKI, buscar_materiais_por_elementos_mp]

FERRAMENTAS_TEMIS = [
    LISTAR_MATERIAIS, FONTES_BANCO, ferramenta(registrar_material), ferramenta(registrar_estado_material),
]

FERRAMENTAS_CALIOPE_COMPOSICAO = [
    *WEB, *ARTIGOS, *WIKI, LISTAR_MATERIAIS, FONTES_BANCO, ferramenta(registrar_composicao),
]

FERRAMENTAS_CALIOPE_PROPRIEDADES = [
    *WEB, *ARTIGOS, *WIKI, *MATERIALS_PROJECT,
    ferramenta(consultar_propriedades_aflow), ferramenta(consultar_estabilidade_oqmd),
    LISTAR_MATERIAIS, FONTES_BANCO, ferramenta(registrar_valor_propriedade),
]

FERRAMENTAS_CALIOPE_ESTRUTURA = [
    *WEB, *ARTIGOS, *WIKI, *MATERIALS_PROJECT,
    ferramenta(buscar_estruturas_calculadas), ferramenta(consultar_estrutura_calculada),
    ferramenta(consultar_estabilidade_oqmd),
    LISTAR_MATERIAIS, FONTES_BANCO, ferramenta(registrar_fase_estrutura),
]
