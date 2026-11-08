"""Propriedades calculadas do AFLOW (API AFLUX, sem chave): elasticidade, energia de formação e mais.

Complementa a rotina OPTIMADE com o que ela não traz: módulos de volume, cisalhamento e Young,
coeficiente de Poisson, temperatura de Debye, expansão térmica e energia de formação.
Os dados são calculados por DFT para cristais ideais: não representam ligas comerciais.

Instalação: python -m pip install requests
Exemplos (na pasta dev):
  python -m Rotinas.aflow_api Al Ni
  python -m Rotinas.aflow_api Al Ni --formula Ni3Al --elasticidade
"""
######################### BIBLIOTECAS ###################################
import argparse
import json
import re
from datetime import datetime, timezone

import requests

import Rotinas.configuracao  # noqa: F401
from Rotinas.cache_fontes import registrar_consulta
from Rotinas.configuracao import user_agent
from Rotinas.optimade_api import _validar_elementos, formula_reduzida
#########################################################################

URL_AFLUX = "https://aflow.org/API/aflux/"
SERVICO = "aflow"
_MAX_MULTIPLO_CELULA = 16
# campo AFLUX: (nome no retorno, unidade)
PROPRIEDADES = {
    "enthalpy_formation_atom": ("energia_formacao", "eV/átomo"),
    "ael_bulk_modulus_vrh": ("modulo_volumetrico_vrh", "GPa"),
    "ael_shear_modulus_vrh": ("modulo_cisalhamento_vrh", "GPa"),
    "ael_youngs_modulus_vrh": ("modulo_young_vrh", "GPa"),
    "ael_poisson_ratio": ("coeficiente_poisson", None),
    "agl_debye": ("temperatura_debye", "K"),
    "agl_thermal_expansion_300K": ("expansao_termica_300K", "1/K"),
    "density": ("densidade", "g/cm³"),
    "Egap": ("band_gap", "eV"),
}
_CAMPOS = ["compound", "auid", "aurl", "spacegroup_relax", "Pearson_symbol_relax", *PROPRIEDADES]


def _compostos_equivalentes(formula: str) -> list[str]:
    """AFLOW guarda a fórmula da célula (ex.: NiAl como Al2Ni2); gera os múltiplos da fórmula reduzida."""
    partes = re.findall(r"([A-Z][a-z]?)(\d*)", formula_reduzida(formula))
    return ["".join(f"{e}{int(n or 1) * k}" for e, n in partes) for k in range(1, _MAX_MULTIPLO_CELULA + 1)]


def _material(item: dict) -> dict:
    aurl = item.get("aurl") or ""
    propriedades = {
        nome: {"valor": item.get(campo), "unidade": unidade}
        for campo, (nome, unidade) in PROPRIEDADES.items()
        if item.get(campo) is not None
    }
    return {
        "auid": item.get("auid"),
        "composto_celula": item.get("compound"),
        "formula_reduzida": formula_reduzida(item["compound"]) if item.get("compound") else None,
        "grupo_espacial": item.get("spacegroup_relax"),
        "simbolo_pearson": item.get("Pearson_symbol_relax"),
        "propriedades": propriedades,
        "url_registro": f"https://aflow.org/material/?id={item.get('auid')}",
        "url_dados": "http://" + aurl.replace(":", "/", 1) + "/" if aurl else None,
        "tipo_dado": "calculado",
    }


def consultar_propriedades_aflow(
    elementos: list[str],
    somente_estes_elementos: bool = True,
    formula: str | None = None,
    somente_com_elasticidade: bool = False,
    limite: int = 10,
) -> dict:
    """Consulta no AFLOW propriedades calculadas (DFT) de fases: elasticidade, energia de formação etc.

    Use para módulos elásticos (volume, cisalhamento, Young), Poisson, temperatura de Debye,
    expansão térmica e energia de formação de fases e intermetálicos. Todos os dados têm
    tipo_dado "calculado" e não representam ligas comerciais nem propriedades de engenharia.

    Args:
        elementos: Símbolos químicos que a fase deve conter. Ex.: ["Al", "Ni"].
        somente_estes_elementos: True para fases só com esses elementos; False para aceitar outros.
        formula: Fórmula da fase, opcional. Ex.: "Ni3Al".
        somente_com_elasticidade: True para trazer só fases com módulos elásticos calculados.
        limite: Número de materiais devolvidos, de 1 a 50.
    """
    simbolos = _validar_elementos(elementos)
    if not 1 <= limite <= 50:
        raise ValueError("limite deve estar entre 1 e 50.")
    reduzida = formula_reduzida(formula) if formula else None
    if reduzida and set(re.findall(r"[A-Z][a-z]?", reduzida)) != set(simbolos) and somente_estes_elementos:
        raise ValueError(f"A fórmula {reduzida} não tem exatamente os elementos {', '.join(simbolos)}.")

    filtros = [f"species(({','.join(simbolos)}))" if len(simbolos) > 1 else f"species({simbolos[0]})"]
    if somente_estes_elementos:
        filtros.append(f"nspecies({len(simbolos)})")
    campos = [
        f"compound({':'.join(_compostos_equivalentes(reduzida))})" if c == "compound" and reduzida
        else f"{c}(*)" if c == "ael_bulk_modulus_vrh" and somente_com_elasticidade
        else c
        for c in _CAMPOS
    ]
    consulta = ",".join(filtros + campos + [f"$paging(1,{limite})", "format(json)"])
    try:
        resposta = requests.get(URL_AFLUX + "?" + consulta, headers={"User-Agent": user_agent()}, timeout=(10, 90))
        resposta.raise_for_status()
        itens = resposta.json()
        if not isinstance(itens, list):
            raise ValueError(f"resposta inesperada: {str(itens)[:200]}")
    except (requests.RequestException, ValueError) as erro:
        registrar_consulta(SERVICO, "busca", consulta, ds_erro=str(erro)[:500])
        raise RuntimeError(f"Não foi possível consultar o AFLOW: {erro}"[:400]) from erro
    registrar_consulta(SERVICO, "busca", consulta)
    return {
        "fonte": "AFLOW (AFLUX)",
        "consulta": consulta,
        "parametros": {
            "elementos": simbolos, "somente_estes_elementos": somente_estes_elementos, "formula": reduzida,
            "somente_com_elasticidade": somente_com_elasticidade, "limite": limite,
        },
        "consultado_em_utc": datetime.now(timezone.utc).isoformat(),
        "observacao": "Dados calculados por DFT (cristal ideal); módulos elásticos pela média de Voigt-Reuss-Hill.",
        "dados": [_material(i) for i in itens],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("elementos", nargs="+")
    parser.add_argument("--formula")
    parser.add_argument("--elasticidade", action="store_true")
    parser.add_argument("--outros-elementos", action="store_true")
    parser.add_argument("--limite", type=int, default=10)
    args = parser.parse_args()
    r = consultar_propriedades_aflow(args.elementos, not args.outros_elementos, args.formula, args.elasticidade, args.limite)
    print(json.dumps(r, ensure_ascii=False, indent=2))
