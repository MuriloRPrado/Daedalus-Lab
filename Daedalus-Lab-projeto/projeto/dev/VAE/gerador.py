"""Gera composições (% em massa, soma 100) com o VAE e compara com a base de ligas reais usada no treino.

Para trocar o modelo, substitua modelo_vae.pt (os elementos e a arquitetura são lidos do próprio checkpoint).
"""
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from VAE.modelo import carregar

PASTA = Path(__file__).resolve().parent
MODELO = PASTA / "modelo_vae.pt"
BASE = PASTA / "dados" / "base_composicoes.csv"
TEMPERATURA = 0.7
AMOSTRAS = 1024
CASAS = 2


@lru_cache(maxsize=1)
def _modelo():
    return carregar(MODELO)


@lru_cache(maxsize=1)
def _base():
    vocab = elementos_modelo()
    df = pd.read_csv(BASE, keep_default_na=False, na_values={e: [""] for e in vocab})
    colunas = [c for c in df.columns if c in vocab]
    return df, df.reindex(columns=vocab, fill_value=0.0).to_numpy(), colunas


def elementos_modelo() -> list[str]:
    return list(_modelo()[1]["elementos"])


def descricao_modelo() -> dict:
    ck = _modelo()[1]
    cfg = ck["config"]
    return {"arquivo": MODELO.name, "parametros": cfg.get("parametros"), "epoca": cfg.get("epoca"),
            "erro_massa_val_pp": (ck.get("metricas_val") or {}).get("erro_massa_val_pp")}


def ocorrencias(elemento: str) -> int:
    return int(_modelo()[1]["ocorrencias"].get(elemento, 0))


def arredondar_soma_100(fracoes, casas=CASAS):
    """Arredonda por maiores restos para que a soma seja exatamente 100."""
    escala = 10 ** casas
    f = np.asarray(fracoes, dtype=np.float64)
    bruto = f / f.sum() * 100 * escala
    base = np.floor(bruto)
    falta = round(100 * escala - base.sum())
    ordem = np.argsort(-(bruto - base))
    base[ordem[:falta]] += 1
    return base / escala


def _escolher_diversas(amostras, n):
    """Primeira = composição mais típica (z = 0); demais = as mais distantes das já escolhidas."""
    escolhidas = [0]
    dist = np.abs(amostras - amostras[0]).sum(1)
    while len(escolhidas) < min(n, len(amostras)):
        i = int(dist.argmax())
        if dist[i] <= 0:
            break
        escolhidas.append(i)
        dist = np.minimum(dist, np.abs(amostras - amostras[i]).sum(1))
    return escolhidas


def gerar_composicoes(elementos: list[str], n: int = 3, semente: int | None = None) -> list[dict[str, float]]:
    """Devolve n composições {elemento: % em massa} (soma 100) usando só os elementos informados."""
    modelo, ck = _modelo()
    vocab = ck["elementos"]
    desconhecidos = [e for e in elementos if e not in vocab]
    if desconhecidos or not elementos:
        raise ValueError(f"Elementos inválidos para o modelo: {desconhecidos or 'lista vazia'}")
    gerador = torch.Generator().manual_seed(semente) if semente is not None else None
    mascara = torch.zeros(AMOSTRAS, len(vocab))
    mascara[:, [vocab.index(e) for e in elementos]] = 1.0
    z = torch.randn(AMOSTRAS, modelo.latente, generator=gerador) * TEMPERATURA
    z[0] = 0.0
    with torch.no_grad():
        p = modelo.decodificar(z, mascara).numpy()
    arred = np.stack([arredondar_soma_100(x) for x in p])
    _, unicos = np.unique(arred, axis=0, return_index=True)
    unicos = np.sort(unicos)
    escolha = [unicos[i] for i in _escolher_diversas(arred[unicos], n)]
    return [{vocab[j]: float(arred[i, j]) for j in np.argsort(-arred[i]) if arred[i, j] > 0} for i in escolha]


def ligas_mais_proximas(composicao: dict[str, float], quantidade: int = 3) -> list[dict]:
    """Ligas da base de treino mais parecidas com a composição (% em massa).

    distancia_pp = metade da soma das diferenças absolutas = massa (pp) que precisa mudar de elemento.
    """
    df, ref, colunas = _base()
    vocab = elementos_modelo()
    alvo = np.array([float(composicao.get(e, 0.0)) for e in vocab])
    dist = 0.5 * np.abs(ref - alvo).sum(1)
    dif_max = np.abs(ref - alvo).max(1)
    saida = []
    for i in np.argsort(dist, kind="stable")[:quantidade]:
        linha = df.iloc[i]
        saida.append({
            "id_base": int(linha["id"]),
            "nome": str(linha["nome"]) or None,
            "familia": str(linha["familia"]),
            "fonte": str(linha["fonte"]),
            "referencia": str(linha["referencia"]),
            "distancia_pp": round(float(dist[i]), 2),
            "maior_diferenca_pp": round(float(dif_max[i]), 4),
            "composicao": {e: round(float(ref[i, vocab.index(e)]), 4)
                           for e in sorted(colunas, key=lambda e: -ref[i, vocab.index(e)]) if ref[i, vocab.index(e)] > 0},
        })
    return saida
