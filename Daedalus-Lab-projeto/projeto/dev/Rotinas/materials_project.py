"""Consultas ao Materials Project (API oficial, exige a chave gratuita na variável MaterialsProject).

Dados calculados por DFT para fases ideais: não representam ligas comerciais.
Instalação: python -m pip install mp-api pymatgen
"""
# BIBLIOTECAS
import json
import re
import os
from datetime import datetime, timezone
from mp_api.client import MPRester
from monty.json import MontyEncoder
from pymatgen.analysis.phase_diagram import PhaseDiagram
from pymatgen.core import Element
from pprint import pprint

import Rotinas.configuracao  # noqa: F401
##############################################################################

chave = os.getenv("MaterialsProject")

if not chave:
    raise ValueError("A variável MaterialsProject não foi configurada")

##############################################################################
"""FUNÇÃO PARA VALIDAR SE O ID INFORMADO ESTÁ NO FORMATO CORRETO"""
def _validar_id(material_id: str) -> None:
    if not isinstance(material_id, str) or not re.fullmatch(r"mp-\d+", material_id):
        raise ValueError("Informe um material_id no formato mp-1234.")

"""CONVERTE MODELOS, ESTRUTURAS E ARRAYS EM TIPOS ACEITOS POR JSON"""
def _json_simples(valor):
    if hasattr(valor, "model_dump"):
        valor = valor.model_dump(exclude_unset=True)
    return json.loads(json.dumps(valor, cls=MontyEncoder, allow_nan=False))

"""ORGANIZA AS INFORMAÇÕES QUE FORAM RETORNADAS PARA RASTREAR DE ONDE VIERAM"""
def _retorno(mpr, consulta: str, dados, **parametros) -> dict:
    return {
        "fonte": "Materials Project",
        "consulta": consulta,
        "parametros": parametros,
        "consultado_em_utc": datetime.now(timezone.utc).isoformat(),
        "versao_banco": getattr(mpr, "db_version", None),
        "dados": _json_simples(dados),
    }

"""FUNÇÃO ORGANIZA OS DADOS A SEREM BUSCADOS
- Recebe:
    - material_id: qual material buscar
    - campos: quais informados devem ser retornados da consulta"""
def _consultar_resumo(material_id: str, campos: list[str]) -> dict | None:
    _validar_id(material_id)
    with MPRester(chave) as mpr:
        resultados = mpr.materials.summary.search(
            material_ids=[material_id],
            deprecated=False,
            fields=campos,
            all_fields=False,
            num_chunks=1,
            chunk_size=1,
        )
        if not resultados:
            return None
        return _retorno(mpr, "materials.summary", resultados[0], material_id=material_id)
##############################################################################

##############################################################################
"""FUNÇAO PARA CONSULTAR MATERIAIS PELA COMPOSIÇÃO
- Dados para a consulta:
    - sistema_quimico: composiçao química desejada. Ex: "Al-Mg"
    - limite: quantidade de registros que devem ser retornados. Ex: 3. Se não informado, a função retornará 10 registros por padrão."""
def buscar_materiais(sistema_quimico: str, limite: int = 10) -> list[dict]:

    if limite <= 0:                                                             # Validar o limite para garantir que seja um número positivo e maior que zero
        raise ValueError("O limite deve ser maior que zero")

    materiais = []

    with MPRester(chave) as mpr:
        resultados = mpr.materials.summary.search(
            chemsys=sistema_quimico,                                            # Composição química para a busca
            deprecated=False,
            fields=[                                                            # Informações que devem ser retornadas
                "material_id",
                "formula_pretty",
                "density",
            ],
            all_fields=False,
            num_chunks=1,
            chunk_size=limite,                                                  # Quantidade de registros que devem ser retornados
        )

    for material in resultados:                                                 # Laço para apresentar os dados retornados na consulta
        materiais.append({
            "material_id": str(material.material_id),
            "formula": material.formula_pretty,
            "Densidade(g/cm3)": material.density,
    })

    return materiais
##############################################################################

##############################################################################
"""FUNÇÃO PARA CONSULTAR OS MATERIAIS POR ELEMENTOS
- Dados para a consulta:
    - elementos: o elemento desejado para a busca. Ex: "Al", "Mg"
    - elementos_excluidos: retornar materiais que não contenham este elemento informado. Ex: "O"
    - limite: quantidade de registros que devem ser retornados. Ex: 3. Se não informado, a função retornará 10 registros por padrão
    - densidade: informa o range de densidade que os registros retornados devem possuir. Ex: (1.5, 3.0)"""
def buscar_materiais_por_elementos(elementos: list[str], elementos_excluidos: list[str] | None = None, limite: int = 10, densidade: tuple[float, float] | None = None) -> list[dict]:

    if limite <= 0:                                                                     # Validar o limite para garantir que seja um número positivo e maior que zero
        raise ValueError("O limite deve ser maior que zero")

    if densidade is not None:
        minimo, maximo = densidade
        if minimo <= 0 or maximo <= 0:                                                  # Garante que o mínimo e máximo serão positivos e maiores que zero
            raise ValueError("Os valores de densidade devem ser positivos.")
        if minimo > maximo:                                                             # Garante que o mínimo nunca será maior que o máximo
            raise ValueError("A densidade mínima não pode ser maior que a máxima.")

    if not elementos:                                                                   # Se não for informado nenhum elemento retorna erro
        raise ValueError("Informe pelo menos um elemento para a busca.")

    conflitos = set(elementos) & set(elementos_excluidos or [])                         # Se elemento a ser consultado for o mesmo que o excluído retorna erro

    if conflitos:
        raise ValueError(
            f"Elementos presentes e excluídos ao mesmo tempo: "
            f"{', '.join(sorted(conflitos))}"
        )

    materiais = []

    with MPRester(chave) as mpr:
        resultados = mpr.materials.summary.search(
            elements=elementos,                                                         # Elementos a ser consultados
            exclude_elements=elementos_excluidos,                                       # Elementos que os materiais retornados não devem possuir
            density=densidade,                                                          # range de densidade que os materiais retornados devem possuir
            deprecated=False,
            fields=[                                                                    # Quantidade de registros que devem ser retornados
                "material_id",
                "formula_pretty",
                "density",
            ],
            all_fields=False,
            num_chunks=1,
            chunk_size=limite,
        )

    for material in resultados:                                                         # Laço para apresentar os dados retornados na consulta
        materiais.append({
            "material_id": str(material.material_id),
            "formula": material.formula_pretty,
            "Densidade(g/cm3)": material.density,
    })

    return materiais
##############################################################################

##############################################################################
"""FUNÇÃO PARA CONSULTAR MATERIAIS POR ID, RETORNANDO UM RESUMO DO REGISTRO"""
def consultar_material_por_id(material_id: str) -> dict | None:
    return _consultar_resumo(material_id, [
        "material_id", "formula_pretty", "density", "volume",
        "nsites", "symmetry", "has_props", "last_updated", "origins",
    ])
##############################################################################

##############################################################################
"""CONSULTA DADOS DA ESTRUTURA CRISTALINA DO MATERIAL
- Estrutura do registro: lattice, sites, ocupacoes e coordenadas.
- Na estrutura serializada, abc sao coordenadas fracionarias e xyz sao
- cartesianas em angstrom. lattice inclui parametros e matriz da rede.
- Nao converte automaticamente para uma celula convencional."""
def consultar_estrutura_cristalina(material_id: str) -> dict | None:
    resultado = _consultar_resumo(
        material_id,
        [
            "material_id",
            "formula_pretty",
            "structure",
            "symmetry",
            "density",
            "origins",
        ],
    )

    if resultado is None:
        return None

    dados = resultado["dados"]

    estrutura = dados.get("structure") or {}
    rede = estrutura.get("lattice") or {}
    simetria = dados.get("symmetry") or {}

    resultado["dados"] = {
        "material_id": dados.get("material_id"),
        "formula_fase": dados.get("formula_pretty"),

        # Exigem identificação complementar; não inferir pela fórmula.
        "nm_fase": None,
        "nm_estrutura_cristalina": None,

        # Simetria informada pelo Materials Project.
        "sistema_cristalino": simetria.get("crystal_system"),
        "ds_grupo_espacial": simetria.get("symbol"),
        "numero_grupo_espacial": simetria.get("number"),

        # Comprimentos em ångströms (Å).
        "a_angstrom": rede.get("a"),
        "b_angstrom": rede.get("b"),
        "c_angstrom": rede.get("c"),

        # Ângulos em graus.
        "alfa_graus": rede.get("alpha"),
        "beta_graus": rede.get("beta"),
        "gama_graus": rede.get("gamma"),

        # Densidade da estrutura consultada, não da liga multifásica.
        "densidade_teorica_fase_g_cm3": dados.get("density"),

        # Não informadas por esta consulta.
        "temperatura_K": None,
        "pressao_Pa": None,

        # Preserva a célula e as posições atômicas para rastreabilidade.
        "estrutura": dados.get("structure"),
        "origens": dados.get("origins"),
        "representacao_celula": "Como retornada pelo Materials Project",
    }

    return resultado
##############################################################################

##############################################################################
"""FUNÇÃO PARA CONSULTAR A ESTABILIDADE DO MATERIAL
- Energias em eV/atomo; estabilidade no modelo calculado do MP.
- is_stable nao garante sintetizabilidade ou estabilidade em servico.
- origins preserva as referencias aos calculos do resumo."""
def consultar_estabilidade(material_id: str) -> dict | None:
    return _consultar_resumo(material_id, [
        "material_id", "formula_pretty", "formation_energy_per_atom",
        "energy_above_hull", "is_stable", "origins", "last_updated",
    ])
##############################################################################

##############################################################################
"""FUNÇÃO PARA CONSULTAR PROPRIEDADES ELÁSTICAS DISPONÍVEIS
- Documentos elasticos disponiveis; modulos/tensor em GPa.
- Preserva todos os registros, sem escolher silenciosamente um calculo.
- Nao fornece limite de escoamento ou resistencia a fadiga de uma liga"""
def consultar_elasticidade(material_id: str) -> dict | None:
    _validar_id(material_id)
    with MPRester(chave) as mpr:
        documentos = mpr.materials.elasticity.search(
            material_ids=[material_id], all_fields=True,
        )
        if not documentos:
            return None
        return _retorno(mpr, "materials.elasticity",
                        [_json_simples(d) for d in documentos], material_id=material_id)
##############################################################################

##############################################################################
"""FUNÇÃO PARA CONSULTAR A ORIGEM DOS DADOS
- Proveniencia disponivel no MP; nao comprova ensaio experimental.
- Para rastrear uma propriedade ate seu calculo, combine este retorno com origins do resumo e, quando necessario, consulte o task_id."""
def consultar_proveniencia(material_id: str) -> dict | None:
    _validar_id(material_id)
    with MPRester(chave) as mpr:
        documentos = mpr.materials.provenance.search(
            material_ids=[material_id], all_fields=True,
        )
        if not documentos:
            return None
        return _retorno(mpr, "materials.provenance",
                        [_json_simples(d) for d in documentos], material_id=material_id)
##############################################################################"
#resultado = consultar_estrutura_cristalina("mp-12766")

#if resultado is None:
#    print("Registro não encontrado.")
#else:
#    pprint(resultado["dados"])

#pprint(consultar_material_por_id(material_id))
#pprint(consultar_estrutura_cristalina(material_id))
#pprint(consultar_estabilidade("mp-12766"))
#pprint(consultar_elasticidade(material_id))
#pprint(consultar_proveniencia(material_id))