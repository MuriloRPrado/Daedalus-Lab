"""Estruturas cristalinas de bases abertas via OPTIMADE (padrão comum de API, sem chave).

Bases: Materials Project, Alexandria, OQMD, JARVIS-DFT (NIST), Materials Cloud (MC3D), AFLOW,
NOMAD e COD. Exceto o COD (estruturas experimentais), os dados são calculados por DFT para
cristais ideais a 0 K: não representam ligas comerciais nem propriedades de engenharia.

Instalação: python -m pip install requests
Exemplos (na pasta dev):
  python -m Rotinas.optimade_api buscar Al Ni
  python -m Rotinas.optimade_api buscar Al Ni --formula Ni3Al --bases oqmd cod
  python -m Rotinas.optimade_api estrutura oqmd 4062279
"""
######################### BIBLIOTECAS ###################################
import argparse
import contextvars
import json
import math
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from functools import reduce
from urllib.parse import quote, urljoin, urlparse

import requests

import Rotinas.configuracao  # noqa: F401
from Rotinas.cache_fontes import registrar_consulta
#########################################################################

BASES = {
    "materials_project": ("Materials Project", "https://optimade.materialsproject.org/v1", "calculado"),
    "alexandria": ("Alexandria (PBE)", "https://alexandria.icams.rub.de/pbe/v1", "calculado"),
    "oqmd": ("OQMD", "https://oqmd.org/optimade/v1", "calculado"),
    "jarvis": ("JARVIS-DFT (NIST)", "https://jarvis.nist.gov/optimade/jarvisdft/v1", "calculado"),
    "materials_cloud": ("Materials Cloud MC3D (PBE)", "https://optimade.materialscloud.org/main/mc3d-pbe-v1/v1", "calculado"),
    "aflow": ("AFLOW", "https://aflow.org/API/optimade/v1", "calculado"),
    "nomad": ("NOMAD", "https://nomad-lab.eu/prod/v1/optimade/v1", "calculado"),
    "cod": ("Crystallography Open Database", "https://www.crystallography.net/cod/optimade/v1", "experimental"),
}
_MAX_PAGINA = {"cod": 10}
_MAX_PAGINAS_FILTRO_LOCAL = 5
BASES_PADRAO = ["materials_project", "alexandria", "oqmd", "jarvis", "materials_cloud", "cod"]
_CAMPOS_RESUMO = "chemical_formula_reduced,chemical_formula_descriptive,elements,nelements,nsites,lattice_vectors,last_modified"
_ELEMENTOS = set(
    "H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se Br Kr "
    "Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm "
    "Yb Lu Hf Ta W Re Os Ir Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf Es Fm Md No "
    "Lr Rf Db Sg Bh Hs Mt Ds Rg Cn Nh Fl Mc Lv Ts Og".split()
)


def _validar_elementos(elementos: list[str]) -> list[str]:
    if not elementos:
        raise ValueError("Informe pelo menos um elemento. Ex.: ['Al', 'Ni'].")
    simbolos = [str(e).strip().capitalize() for e in elementos]
    invalidos = [s for s in simbolos if s not in _ELEMENTOS]
    if invalidos:
        raise ValueError(f"Símbolos químicos inválidos: {', '.join(invalidos)}.")
    return sorted(set(simbolos))


def formula_reduzida(formula: str) -> str:
    """Converte uma fórmula (ex.: 'Ni3Al', 'Al2Ni6') para o formato OPTIMADE ('AlNi3')."""
    partes = re.findall(r"([A-Z][a-z]?)(\d*)", formula.replace(" ", ""))
    if not partes or "".join(e + n for e, n in partes) != formula.replace(" ", ""):
        raise ValueError(f"Fórmula inválida: {formula}. Use o formato Ni3Al.")
    contagem: dict[str, int] = {}
    for elemento, numero in partes:
        _validar_elementos([elemento])
        quantidade = int(numero or 1)
        if quantidade <= 0:
            raise ValueError(f"Fórmula inválida: {formula}. A quantidade de cada elemento deve ser maior que zero.")
        contagem[elemento] = contagem.get(elemento, 0) + quantidade
    divisor = reduce(math.gcd, contagem.values())
    return "".join(f"{e}{n // divisor if n // divisor > 1 else ''}" for e, n in sorted(contagem.items()))


def _mesma_formula(atributos: dict, formula: str) -> bool:
    if atributos.get("chemical_formula_reduced") == formula:
        return True
    try:
        return formula_reduzida(atributos.get("chemical_formula_descriptive") or "") == formula
    except ValueError:
        return False


def _parametros_rede(vetores) -> dict:
    """Calcula a, b, c (Å), alfa, beta, gama (graus) e volume (Å³) a partir de lattice_vectors."""
    try:
        a, b, c = ([float(x) for x in v] for v in vetores)
    except (TypeError, ValueError):
        return {}
    norma = lambda v: math.sqrt(sum(x * x for x in v))
    ponto = lambda u, v: sum(x * y for x, y in zip(u, v, strict=True))
    angulo = lambda u, v: math.degrees(math.acos(max(-1.0, min(1.0, ponto(u, v) / (norma(u) * norma(v))))))
    volume = abs(a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0]) + a[2] * (b[0] * c[1] - b[1] * c[0]))
    return {
        "a_angstrom": round(norma(a), 4), "b_angstrom": round(norma(b), 4), "c_angstrom": round(norma(c), 4),
        "alfa_graus": round(angulo(b, c), 3), "beta_graus": round(angulo(a, c), 3), "gama_graus": round(angulo(a, b), 3),
        "volume_celula_angstrom3": round(volume, 4),
    }


def _resumo_estrutura(chave_base: str, item: dict) -> dict:
    nome, url_base, tipo_dado = BASES[chave_base]
    atributos = item.get("attributes") or {}
    return {
        "base": chave_base,
        "nome_base": nome,
        "id": item.get("id"),
        "url_registro": f"{url_base}/structures/{quote(str(item.get('id')), safe='')}",
        "tipo_dado": tipo_dado,
        "formula_reduzida": atributos.get("chemical_formula_reduced"),
        "formula_descritiva": atributos.get("chemical_formula_descriptive"),
        "elementos": atributos.get("elements"),
        "numero_sitios": atributos.get("nsites"),
        "rede": _parametros_rede(atributos.get("lattice_vectors")),
        "atualizado_em": atributos.get("last_modified"),
    }


def _requisitar_estruturas(chave_base: str, filtro: str, limite: int) -> dict:
    limite = min(limite, _MAX_PAGINA.get(chave_base, limite))
    parametros = {"filter": filtro, "page_limit": limite, "response_fields": _CAMPOS_RESUMO}
    resposta = requests.get(f"{BASES[chave_base][1]}/structures", params=parametros, timeout=45)
    resposta.raise_for_status()
    return resposta.json()


def _proxima_pagina(chave_base: str, corpo: dict) -> str | None:
    """Link da próxima página, aceito só se apontar para o mesmo servidor da base."""
    proxima = (corpo.get("links") or {}).get("next")
    proxima = proxima.get("href") if isinstance(proxima, dict) else proxima
    if not proxima or not isinstance(proxima, str):
        return None
    url_base = BASES[chave_base][1]
    url = urljoin(url_base + "/", proxima)
    origem, destino = urlparse(url_base), urlparse(url)
    if (destino.scheme, destino.netloc) != (origem.scheme, origem.netloc):
        return None
    return url


def _buscar_com_filtro_local(chave_base: str, filtro: str, limite: int, formula: str) -> tuple[list[dict], str | None]:
    """Percorre até _MAX_PAGINAS_FILTRO_LOCAL páginas filtrando a fórmula aqui; devolve (itens, motivo_busca_incompleta)."""
    corpo = _requisitar_estruturas(chave_base, filtro, 50)
    encontrados = []
    for pagina in range(_MAX_PAGINAS_FILTRO_LOCAL):
        encontrados += [i for i in corpo.get("data") or [] if _mesma_formula(i.get("attributes") or {}, formula)]
        proxima = _proxima_pagina(chave_base, corpo)
        if len(encontrados) >= limite or not proxima:
            return encontrados, None
        if pagina == _MAX_PAGINAS_FILTRO_LOCAL - 1:
            break
        try:
            resposta = requests.get(proxima, timeout=45)
            resposta.raise_for_status()
            corpo = resposta.json()
        except (requests.RequestException, ValueError) as erro:
            return encontrados, f"a página {pagina + 2} falhou ({erro})"[:300]
    return encontrados, f"só as primeiras {_MAX_PAGINAS_FILTRO_LOCAL} páginas de resultados foram verificadas"


def _consultar_base(chave_base: str, filtro: str, limite: int, formula: str | None) -> dict:
    filtro_completo = filtro + (f' AND chemical_formula_reduced="{formula}"' if formula else "")
    filtrado_localmente, busca_incompleta = False, None
    try:
        try:
            corpo = _requisitar_estruturas(chave_base, filtro_completo, limite)
            itens = corpo.get("data") or []
            total = (corpo.get("meta") or {}).get("data_returned")
        except requests.HTTPError as erro:
            # Algumas bases (ex.: COD, AFLOW) não aceitam filtro por fórmula: filtra aqui.
            if not formula or erro.response is None or erro.response.status_code not in (400, 501):
                raise
            itens, busca_incompleta = _buscar_com_filtro_local(chave_base, filtro, limite, formula)
            total, filtrado_localmente = None, True
    except (requests.RequestException, ValueError) as erro:
        registrar_consulta(f"optimade:{chave_base}", "busca", filtro_completo, ds_erro=str(erro)[:500])
        return {"base": chave_base, "erro": f"Base indisponível ou consulta recusada: {erro}"[:300], "estruturas": []}
    registrar_consulta(f"optimade:{chave_base}", "busca", filtro_completo, ds_erro=busca_incompleta)
    retorno = {
        "base": chave_base,
        "total_na_base": total,
        "estruturas": [_resumo_estrutura(chave_base, i) for i in itens[:limite]],
    }
    if busca_incompleta:
        retorno["observacao"] = (
            f"A base não aceita filtro por fórmula e a busca ficou incompleta: {busca_incompleta}. "
            "Pode haver outras estruturas com essa fórmula."
        )
    elif filtrado_localmente:
        retorno["observacao"] = "A base não aceita filtro por fórmula; o filtro foi aplicado localmente."
    return retorno


def _retorno(consulta: str, dados, **parametros) -> dict:
    return {
        "fonte": "OPTIMADE",
        "consulta": consulta,
        "parametros": parametros,
        "consultado_em_utc": datetime.now(timezone.utc).isoformat(),
        "dados": dados,
    }


def buscar_estruturas_calculadas(
    elementos: list[str],
    somente_estes_elementos: bool = True,
    formula: str | None = None,
    bases: list[str] | None = None,
    limite_por_base: int = 5,
) -> dict:
    """Busca estruturas cristalinas de fases em várias bases abertas ao mesmo tempo (OPTIMADE).

    Use para fases, intermetálicos, estrutura cristalina e parâmetros de rede. Exceto o COD
    (tipo_dado "experimental"), os dados são calculados por DFT (tipo_dado "calculado") e não
    representam ligas comerciais nem propriedades mecânicas de engenharia.

    Args:
        elementos: Símbolos químicos que a fase deve conter. Ex.: ["Al", "Ni"].
        somente_estes_elementos: True para fases só com esses elementos; False para aceitar outros.
        formula: Fórmula da fase, opcional. Ex.: "Ni3Al".
        bases: Bases a consultar. Opções: materials_project, alexandria, oqmd, jarvis,
            materials_cloud, aflow, nomad, cod. Padrão: todas menos aflow e nomad.
        limite_por_base: Estruturas devolvidas por base, de 1 a 20.
    """
    simbolos = _validar_elementos(elementos)
    if not 1 <= limite_por_base <= 20:
        raise ValueError("limite_por_base deve estar entre 1 e 20.")
    bases = bases or BASES_PADRAO
    desconhecidas = [b for b in bases if b not in BASES]
    if desconhecidas:
        raise ValueError(f"Bases desconhecidas: {', '.join(desconhecidas)}. Opções: {', '.join(BASES)}.")

    filtro = "elements HAS ALL " + ",".join(f'"{s}"' for s in simbolos)
    if somente_estes_elementos:
        filtro += f" AND nelements={len(simbolos)}"
    reduzida = formula_reduzida(formula) if formula else None

    # Cada thread recebe uma cópia do contexto para o log manter o projeto e o agente.
    contextos = [contextvars.copy_context() for _ in bases]
    with ThreadPoolExecutor(max_workers=len(bases)) as executor:
        resultados = list(executor.map(
            lambda ctx, b: ctx.run(_consultar_base, b, filtro, limite_por_base, reduzida), contextos, bases,
        ))
    return _retorno(
        "structures", resultados,
        elementos=simbolos, somente_estes_elementos=somente_estes_elementos,
        formula=reduzida, bases=bases, limite_por_base=limite_por_base,
    )


def consultar_estrutura_calculada(base: str, id_estrutura: str) -> dict:
    """Consulta o registro completo de uma estrutura: rede, espécies e posições atômicas.

    Args:
        base: Base de origem, como devolvida por buscar_estruturas_calculadas. Ex.: "oqmd".
        id_estrutura: ID da estrutura na base. Ex.: "4062279".
    """
    if base not in BASES:
        raise ValueError(f"Base desconhecida: {base}. Opções: {', '.join(BASES)}.")
    if not str(id_estrutura).strip():
        raise ValueError("Informe o ID da estrutura.")
    url = f"{BASES[base][1]}/structures/{quote(str(id_estrutura).strip(), safe='')}"
    try:
        resposta = requests.get(url, timeout=45)
        resposta.raise_for_status()
        item = resposta.json().get("data")
    except (requests.RequestException, ValueError) as erro:
        registrar_consulta(f"optimade:{base}", "leitura", url, ds_erro=str(erro)[:500])
        raise RuntimeError(f"Não foi possível consultar {url}: {erro}") from erro
    registrar_consulta(f"optimade:{base}", "leitura", url)
    if isinstance(item, list):
        item = item[0] if item else None
    if not item:
        return _retorno("structures/id", None, base=base, id_estrutura=id_estrutura)
    atributos = item.get("attributes") or {}
    dados = _resumo_estrutura(base, item)
    dados.update({
        "vetores_rede_angstrom": atributos.get("lattice_vectors"),
        "especies": atributos.get("species"),
        "especies_por_sitio": atributos.get("species_at_sites"),
        "posicoes_cartesianas_angstrom": atributos.get("cartesian_site_positions"),
        "dimensoes_periodicas": atributos.get("dimension_types"),
        "campos_especificos_base": {k: v for k, v in atributos.items() if k.startswith("_")},
    })
    return _retorno("structures/id", dados, base=base, id_estrutura=id_estrutura)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="comando", required=True)
    p = sub.add_parser("buscar")
    p.add_argument("elementos", nargs="+")
    p.add_argument("--formula")
    p.add_argument("--bases", nargs="+")
    p.add_argument("--limite", type=int, default=5)
    p.add_argument("--outros-elementos", action="store_true")
    p = sub.add_parser("estrutura")
    p.add_argument("base")
    p.add_argument("id")
    args = parser.parse_args()
    if args.comando == "buscar":
        r = buscar_estruturas_calculadas(args.elementos, not args.outros_elementos, args.formula, args.bases, args.limite)
    else:
        r = consultar_estrutura_calculada(args.base, args.id)
    print(json.dumps(r, ensure_ascii=False, indent=2))
