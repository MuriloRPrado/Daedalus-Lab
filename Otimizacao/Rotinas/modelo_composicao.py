"""Modelo substituto composição → propriedades mecânicas de aços de alta resistência.

Para cada propriedade de dados_acos.ALVOS é treinado um ensemble de XGBoost em amostras bootstrap;
a previsão é a média do ensemble e a incerteza é o desvio padrão entre os membros. O desvio do
bootstrap subestima o erro real, então a validação cruzada calcula um fator de calibração: o
desvio informado é desvio_ensemble × fator, com o fator escolhido para que ~95% dos aços fora do
treino fiquem dentro de média ± 1,96 desvio.

Domínio de validade: teor máximo de cada elemento no treino (os mínimos do dataset são teores
residuais de ~0,01%, então ausência do elemento conta como dentro). Composições fora dele são
previstas, mas marcadas com fl_no_dominio = False.
"""
######################### BIBLIOTECAS ###################################
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold
from xgboost import XGBRegressor

from configuracao import PASTA_MODELOS
from Rotinas.dados_acos import ALVOS, ELEMENTOS_LIGA, NOME_DATASET, carregar_dataset
#########################################################################

NOME_MODELO = "composicao_acos"
TIPO_MODELO = "ensemble_xgboost_bootstrap"
ARQUIVO_MODELO = PASTA_MODELOS / f"{NOME_MODELO}.joblib"


def arquivo_versao(versao: str) -> Path:
    return PASTA_MODELOS / f"{NOME_MODELO}_{versao}.joblib"


TAMANHO_ENSEMBLE = 10
HIPERPARAMETROS = dict(n_estimators=400, max_depth=4, learning_rate=0.05, subsample=0.8,
                       colsample_bytree=0.8, min_child_weight=2, n_jobs=1)


def _treinar_ensemble(x: np.ndarray, y: np.ndarray, semente: int = 0) -> list[XGBRegressor]:
    gerador = np.random.default_rng(semente)
    membros = []
    for i in range(TAMANHO_ENSEMBLE):
        indices = gerador.integers(0, len(x), len(x))
        membro = XGBRegressor(random_state=semente + i, **HIPERPARAMETROS)
        membro.fit(x[indices], y[indices])
        membros.append(membro)
    return membros


def _prever_ensemble(membros: list[XGBRegressor], x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    previsoes = np.stack([m.predict(x) for m in membros])
    return previsoes.mean(axis=0), previsoes.std(axis=0)


def validar(x: np.ndarray, y: np.ndarray, dobras: int = 5, semente: int = 42) -> dict:
    """Validação cruzada k-fold: MAE, RMSE, R², cobertura de ±2σ e MAE do palpite pela média."""
    media = np.zeros_like(y)
    desvio = np.zeros_like(y)
    mae_base = []
    for treino, teste in KFold(dobras, shuffle=True, random_state=semente).split(x):
        membros = _treinar_ensemble(x[treino], y[treino], semente)
        media[teste], desvio[teste] = _prever_ensemble(membros, x[teste])
        mae_base.append(mean_absolute_error(y[teste], np.full(len(teste), y[treino].mean())))
    erro = np.abs(y - media)
    fator = float(np.quantile(erro / np.maximum(desvio, 1e-9), 0.95) / 1.96)
    return {
        "dobras": dobras,
        "mae": float(mean_absolute_error(y, media)),
        "rmse": float(np.sqrt(mean_squared_error(y, media))),
        "r2": float(r2_score(y, media)),
        "cobertura_ensemble_1_96": float(np.mean(erro <= 1.96 * desvio)),
        "fator_calibracao": fator,
        "mae_palpite_media": float(np.mean(mae_base)),
    }


def treinar(salvar: bool = True) -> dict:
    """Treina e valida um ensemble por propriedade. Devolve o artefato (e o salva em modelos/)."""
    dados = carregar_dataset()
    x = dados[ELEMENTOS_LIGA].to_numpy()
    artefato = {
        "nome": NOME_MODELO,
        "versao": datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
        "tipo": TIPO_MODELO,
        "dataset": NOME_DATASET,
        "nr_amostras": len(dados),
        "elementos": ELEMENTOS_LIGA,
        "hiperparametros": HIPERPARAMETROS | {"tamanho_ensemble": TAMANHO_ENSEMBLE},
        "dominio": {e: {"min": float(dados[e].min()), "max": float(dados[e].max())} for e in ELEMENTOS_LIGA},
        "alvos": {},
    }
    for alvo, (_, unidade) in ALVOS.items():
        y = dados[alvo].to_numpy()
        medido = ~np.isnan(y)
        artefato["alvos"][alvo] = {
            "unidade": unidade,
            "nr_amostras": int(medido.sum()),
            "metricas": validar(x[medido], y[medido]),
            "membros": _treinar_ensemble(x[medido], y[medido]),
        }
    if salvar:
        PASTA_MODELOS.mkdir(parents=True, exist_ok=True)
        joblib.dump(artefato, arquivo_versao(artefato["versao"]))
        joblib.dump(artefato, ARQUIVO_MODELO)
    return artefato


class ModeloComposicao:
    """Carrega o artefato treinado e prevê propriedades a partir da composição (% em massa)."""

    def __init__(self, artefato: dict | None = None, caminho: Path = ARQUIVO_MODELO):
        if artefato is None:
            if not caminho.is_file():
                raise FileNotFoundError(f"Modelo não encontrado em {caminho}; rode treinar_modelo.py.")
            artefato = joblib.load(caminho)
        self.artefato = artefato
        self.elementos = artefato["elementos"]
        self.dominio = artefato["dominio"]

    def vetorizar(self, composicao: dict[str, float]) -> np.ndarray:
        desconhecidos = set(composicao) - set(self.elementos) - {"Fe"}
        if desconhecidos:
            raise ValueError(f"Elementos fora do modelo: {sorted(desconhecidos)} (aceitos: {self.elementos}).")
        invalidos = {e: v for e, v in composicao.items() if not np.isfinite(float(v)) or float(v) < 0}
        if invalidos:
            raise ValueError(f"Teores inválidos (devem ser finitos e >= 0 % em massa): {invalidos}.")
        return np.array([float(composicao.get(e, 0.0)) for e in self.elementos])

    def fora_do_dominio(self, composicao: dict[str, float]) -> list[str]:
        return [e for e in self.elementos if float(composicao.get(e, 0.0)) > self.dominio[e]["max"]]

    def prever_lote(self, x: np.ndarray) -> dict[str, tuple[np.ndarray, np.ndarray]]:
        """x: matriz (n, len(elementos)) em % em massa. Devolve {alvo: (média, desvio calibrado)}."""
        previsoes = {}
        for alvo, dados in self.artefato["alvos"].items():
            media, desvio = _prever_ensemble(dados["membros"], np.atleast_2d(x))
            previsoes[alvo] = (media, desvio * dados["metricas"]["fator_calibracao"])
        return previsoes

    def prever(self, composicao: dict[str, float]) -> dict:
        previsoes = self.prever_lote(self.vetorizar(composicao))
        fora = self.fora_do_dominio(composicao)
        return {
            "propriedades": {
                alvo: {"valor": float(media[0]), "incerteza": float(desvio[0]),
                       "unidade": self.artefato["alvos"][alvo]["unidade"]}
                for alvo, (media, desvio) in previsoes.items()
            },
            "fl_no_dominio": not fora,
            "fora_do_dominio": fora,
        }
