"""Estabilidade de fases do OQMD (API REST, sem chave): energia de formação e distância da envoltória convexa.

Complementa a rotina OPTIMADE: indica se uma fase (ex.: um intermetálico) tende a ser estável.
stability = 0 eV/átomo significa que a fase está na envoltória convexa (estável a 0 K); valores
maiores indicam fases metaestáveis ou instáveis. Dados calculados por DFT, licença CC-BY 4.0.

Instalação: python -m pip install requests
Exemplos (na pasta dev):
  python -m Rotinas.oqmd_api Al Ni --estaveis
  python -m Rotinas.oqmd_api Al Ni --formula Ni3Al
"""
######################### BIBLIOTECAS ###################################
import argparse
import json
from datetime import datetime, timezone

import requests

import Rotinas.configuracao  # noqa: F401
from Rotinas.cache_fontes import registrar_consulta
from Rotinas.configuracao import user_agent
from Rotinas.optimade_api import _validar_elementos, formula_reduzida
#########################################################################

URL_OQMD = "https://oqmd.org/oqmdapi/formationenergy"
SERVICO = "oqmd"
_CAMPOS = "name,entry_id,spacegroup,prototype,delta_e,stability,band_gap,volume,natoms"


def _fase(item: dict) -> dict:
    estabilidade = item.get("stability")
    return {
        "id_entrada": item.get("entry_id"),
        "formula_reduzida": item.get("name"),
        "grupo_espacial": item.get("spacegroup"),
        "prototipo": item.get("prototype"),
        "energia_formacao_eV_atomo": item.get("delta_e"),
        "distancia_envoltoria_eV_atomo": estabilidade,
        "estavel_0K": estabilidade is not None and estabilidade <= 1e-6,
        "band_gap_eV": item.get("band_gap"),
        "volume_celula_angstrom3": item.get("volume"),
        "numero_atomos_celula": item.get("natoms"),
        "url_registro": f"https://oqmd.org/materials/entry/{item.get('entry_id')}",
        "tipo_dado": "calculado",
    }


def consultar_estabilidade_oqmd(
    elementos: list[str],
    somente_estes_elementos: bool = True,
    formula: str | None = None,
    somente_estaveis: bool = False,
    limite: int = 10,
) -> dict:
    """Consulta no OQMD a energia de formação e a estabilidade (distância da envoltória convexa) de fases.

    Use para saber quais fases/intermetálicos de um sistema são estáveis e quão favorável é a
    formação. Resultados ordenados da mais estável para a menos estável. Todos os dados têm
    tipo_dado "calculado" (DFT, 0 K) e não representam ligas comerciais.

    Args:
        elementos: Símbolos químicos que a fase deve conter. Ex.: ["Al", "Ni"].
        somente_estes_elementos: True para fases só com esses elementos; False para aceitar outros.
        formula: Fórmula da fase, opcional. Ex.: "Ni3Al".
        somente_estaveis: True para trazer só as fases na envoltória convexa (estáveis a 0 K).
        limite: Número de fases devolvidas, de 1 a 50.
    """
    simbolos = _validar_elementos(elementos)
    if not 1 <= limite <= 50:
        raise ValueError("limite deve estar entre 1 e 50.")
    reduzida = formula_reduzida(formula) if formula else None

    condicoes = [f"element_set=({','.join(simbolos)})"]
    if somente_estes_elementos:
        condicoes.append(f"ntypes={len(simbolos)}")
    if somente_estaveis:
        condicoes.append("stability<=0")
    parametros = {"filter": " AND ".join(condicoes), "fields": _CAMPOS, "limit": limite, "sort_by": "stability"}
    if reduzida:
        parametros["composition"] = reduzida
    consulta = json.dumps(parametros, ensure_ascii=False)
    try:
        resposta = requests.get(URL_OQMD, params=parametros, headers={"User-Agent": user_agent()}, timeout=(10, 120))
        resposta.raise_for_status()
        corpo = resposta.json()
    except (requests.RequestException, ValueError) as erro:
        registrar_consulta(SERVICO, "busca", consulta, ds_erro=str(erro)[:500])
        raise RuntimeError(f"Não foi possível consultar o OQMD: {erro}"[:400]) from erro
    registrar_consulta(SERVICO, "busca", consulta)
    fases = [_fase(i) for i in corpo.get("data") or []]
    fases.sort(key=lambda f: (f["distancia_envoltoria_eV_atomo"] is None, f["distancia_envoltoria_eV_atomo"] or 0))
    return {
        "fonte": "OQMD",
        "consulta": consulta,
        "parametros": {
            "elementos": simbolos, "somente_estes_elementos": somente_estes_elementos, "formula": reduzida,
            "somente_estaveis": somente_estaveis, "limite": limite,
        },
        "consultado_em_utc": datetime.now(timezone.utc).isoformat(),
        "ha_mais_resultados": bool((corpo.get("meta") or {}).get("more_data_available")),
        "licenca": "CC-BY 4.0 (citar o OQMD)",
        "observacao": "Dados calculados por DFT a 0 K; distância da envoltória 0 indica fase estável.",
        "dados": fases,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("elementos", nargs="+")
    parser.add_argument("--formula")
    parser.add_argument("--estaveis", action="store_true")
    parser.add_argument("--outros-elementos", action="store_true")
    parser.add_argument("--limite", type=int, default=10)
    args = parser.parse_args()
    r = consultar_estabilidade_oqmd(args.elementos, not args.outros_elementos, args.formula, args.estaveis, args.limite)
    print(json.dumps(r, ensure_ascii=False, indent=2))
