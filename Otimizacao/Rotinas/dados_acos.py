"""Dataset de aços de alta resistência (composição → propriedades mecânicas).

Fonte: "Mechanical properties of some steels", Citrine Informatics (citrination.com/datasets/153092),
distribuído pelo matminer como `steel_strength` (312 aços deduplicados).
Composição em % em massa de 13 elementos de liga (Fe por balanço); limite de escoamento e de
resistência em MPa (1006 a 2570 MPa) e alongamento em %. Ou seja, o domínio é aço de alta resistência
(maraging, aços ferramenta, aços inoxidáveis endurecíveis etc.).

O arquivo é baixado uma vez para dados/cache/ (fora do Git).
"""
######################### BIBLIOTECAS ###################################
import gzip
import json

import pandas as pd
import requests

from configuracao import PASTA_CACHE
#########################################################################

URL_DATASET = "https://ndownloader.figshare.com/files/13354691"
ARQUIVO_CACHE = PASTA_CACHE / "steel_strength.json.gz"
NOME_DATASET = "matminer steel_strength (Citrine Informatics, citrination.com/datasets/153092)"

ELEMENTOS_LIGA = ["C", "Mn", "Si", "Cr", "Ni", "Mo", "V", "N", "Nb", "Co", "W", "Al", "Ti"]
ALVOS = {
    "limite_escoamento": ("yield strength", "MPa"),
    "limite_resistencia": ("tensile strength", "MPa"),
    "alongamento": ("elongation", "%"),
}


def baixar_dataset(forcar: bool = False) -> None:
    if ARQUIVO_CACHE.is_file() and not forcar:
        return
    PASTA_CACHE.mkdir(parents=True, exist_ok=True)
    resposta = requests.get(URL_DATASET, timeout=60)
    resposta.raise_for_status()
    ARQUIVO_CACHE.write_bytes(resposta.content)


def carregar_dataset() -> pd.DataFrame:
    """Colunas: os ELEMENTOS_LIGA (% em massa) e as chaves de ALVOS."""
    baixar_dataset()
    with gzip.open(ARQUIVO_CACHE, "rt", encoding="utf-8") as arquivo:
        bruto = json.load(arquivo)
    tabela = pd.DataFrame(bruto["data"], columns=bruto["columns"])
    renomear = {e.lower(): e for e in ELEMENTOS_LIGA}
    renomear.update({coluna: alvo for alvo, (coluna, _) in ALVOS.items()})
    tabela = tabela.rename(columns=renomear)[ELEMENTOS_LIGA + list(ALVOS)]
    return tabela.astype(float)
