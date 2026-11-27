"""Preço, pegada de CO2 e concentração de produção (HHI) por elemento, e indicadores de uma composição.

Dados em dados/elementos_referencia.csv:
  preço  pymatgen costdb_elements.csv (Wolfram Alpha / Wikipedia, set/2013), USD/kg do elemento puro;
  CO2    Nuss & Eckelman (2014), PLoS ONE 9(7): e101298, Supporting Information S1, linhas "TOTAL"
         (média ponderada pela produção global de todas as formas, inclusive ferroligas), GWP 100a
         em kg CO2-eq/kg, com intervalo de 2,5% a 97,5%; C, Si e N não constam no estudo;
  HHI    Gaultois et al. (2013), Chem. Mater. 25, 2911 (pymatgen hhi_data.csv), produção e reservas.
Elemento crítico: HHI de produção acima de 2500 (mercado altamente concentrado).

Indicadores de uma composição (% em massa, Fe por balanço) são médias ponderadas pela fração em massa.
"""
######################### BIBLIOTECAS ###################################
import csv
from functools import lru_cache

from configuracao import PASTA_DADOS
#########################################################################

ARQUIVO_REFERENCIAS = PASTA_DADOS / "elementos_referencia.csv"
LIMITE_HHI_CRITICO = 2500
ELEMENTO_BALANCO = "Fe"

FONTE_PRECO = "pymatgen costdb_elements.csv (Wolfram Alpha / Wikipedia, set/2013), USD/kg do elemento puro"
FONTE_CO2 = ("Nuss P, Eckelman MJ (2014) Life Cycle Assessment of Metals: A Scientific Synthesis. "
             "PLoS ONE 9(7): e101298, doi:10.1371/journal.pone.0101298, Supporting Information S1, linha TOTAL, "
             "GWP 100a (IPCC 2007)")
FONTE_HHI = ("Gaultois MW et al. (2013) Data-Driven Review of Thermoelectric Materials: Performance and Resource "
             "Considerations. Chem. Mater. 25, 2911, doi:10.1021/cm400893e (pymatgen hhi_data.csv)")

_INTEIROS = ("vl_hhi_producao", "vl_hhi_reserva")


def _valor(campo: str, texto: str):
    if texto == "":
        return None
    return int(texto) if campo in _INTEIROS else float(texto)


@lru_cache(maxsize=1)
def carregar_referencias() -> dict[str, dict]:
    """Devolve {sigla: {campo: valor}} a partir do CSV, com fl_critico calculado."""
    referencias = {}
    with open(ARQUIVO_REFERENCIAS, encoding="utf-8", newline="") as arquivo:
        for linha in csv.DictReader(arquivo):
            dados = {k: (v if k in ("nm_sigla", "nm_elemento") else _valor(k, v)) for k, v in linha.items()}
            dados["fl_critico"] = dados["vl_hhi_producao"] > LIMITE_HHI_CRITICO
            referencias[dados["nm_sigla"]] = dados
    return referencias


def completar_balanco(composicao: dict[str, float]) -> dict[str, float]:
    """Valida a composição (% em massa) e acrescenta o Fe por balanço."""
    referencias = carregar_referencias()
    liga = {}
    for sigla, teor in composicao.items():
        if sigla == ELEMENTO_BALANCO:
            continue
        if sigla not in referencias:
            raise ValueError(f"Elemento sem dados de referência: {sigla}.")
        teor = float(teor)
        if teor < 0:
            raise ValueError(f"Teor negativo para {sigla}: {teor}.")
        liga[sigla] = teor
    soma = sum(liga.values())
    if soma >= 100:
        raise ValueError(f"A soma dos elementos de liga ({soma:.2f}%) não deixa saldo de Fe.")
    liga[ELEMENTO_BALANCO] = 100 - soma
    return liga


def indicadores_composicao(composicao: dict[str, float]) -> dict:
    """Custo (USD/kg), CO2 (kg CO2-eq/kg, com faixa) e HHI ponderados pela fração em massa."""
    referencias = carregar_referencias()
    completa = completar_balanco(composicao)
    custo = co2 = co2_min = co2_max = hhi = 0.0
    sem_co2, criticos = [], []
    for sigla, teor in completa.items():
        fracao = teor / 100
        ref = referencias[sigla]
        custo += fracao * ref["vl_preco_usd_kg"]
        hhi += fracao * ref["vl_hhi_producao"]
        if ref["vl_co2_kg_kg"] is None:
            if teor > 0:
                sem_co2.append(sigla)
        else:
            co2 += fracao * ref["vl_co2_kg_kg"]
            co2_min += fracao * ref["vl_co2_p2_5"]
            co2_max += fracao * ref["vl_co2_p97_5"]
        if ref["fl_critico"] and teor > 0 and sigla != ELEMENTO_BALANCO:
            criticos.append(sigla)
    return {
        "composicao": completa,
        "custo_usd_kg": custo,
        "co2_kg_kg": co2,
        "co2_faixa_kg_kg": (co2_min, co2_max),
        "hhi": hhi,
        "elementos_sem_co2": sem_co2,
        "elementos_criticos": criticos,
    }


def popular_tabela(sessao) -> int:
    """Insere ou atualiza elemento_referencia a partir do CSV. Devolve o número de elementos."""
    from database import ElementoReferencia

    referencias = carregar_referencias()
    for sigla, dados in referencias.items():
        registro = sessao.get(ElementoReferencia, sigla) or ElementoReferencia(nm_sigla=sigla)
        for campo, valor in dados.items():
            setattr(registro, campo, valor)
        registro.ds_fonte_preco = FONTE_PRECO
        registro.ds_fonte_co2 = FONTE_CO2 if dados["vl_co2_kg_kg"] is not None else None
        registro.ds_fonte_hhi = FONTE_HHI
        sessao.add(registro)
    sessao.commit()
    return len(referencias)
