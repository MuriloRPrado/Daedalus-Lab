"""Tabelas do módulo Otimizacao (mesmo Postgres do Daedalus-Lab-projeto, sem dependência das tabelas antigas).

Uso: from database import obter_sessao, criar_tabelas
"""
############################## BIBLIOTECAS ##############################
import os
from functools import lru_cache

from sqlalchemy import (
    TIMESTAMP, VARCHAR, Boolean, Column, Float, ForeignKey, Integer, Text, create_engine, func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base, sessionmaker

import configuracao  # noqa: F401  (carrega Otimizacao/.env)

Base = declarative_base()


############################## CONEXÃO ##############################
@lru_cache(maxsize=1)
def obter_engine():
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("A variável DATABASE_URL não foi configurada (veja Otimizacao/.env.exemplo).")
    return create_engine(url)


def obter_sessao():
    return sessionmaker(bind=obter_engine())()


def criar_tabelas() -> None:
    Base.metadata.create_all(obter_engine())


############################## TABELAS ##############################
'''Modelos de ML treinados (um registro por propriedade-alvo e versão)'''
class ModeloML(Base):
    __tablename__ = 'modelo_ml'

    id_modelo = Column(Integer, primary_key=True)
    nm_modelo = Column(VARCHAR(100), nullable=False)
    nm_versao = Column(VARCHAR(50), nullable=False)
    nm_tipo = Column(VARCHAR(50))                 # ex.: ensemble_xgboost, chgnet
    nm_propriedade = Column(VARCHAR(100))         # ex.: limite_escoamento
    ds_unidade = Column(VARCHAR(30))
    nm_dataset = Column(VARCHAR(255))
    nr_amostras = Column(Integer)
    vl_mae = Column(Float)
    vl_rmse = Column(Float)
    vl_r2 = Column(Float)
    ds_metricas = Column(JSONB)                   # métricas extras da validação cruzada
    ds_dominio = Column(JSONB)                    # faixa min/máx de cada elemento no treino
    ds_caminho_artefato = Column(Text)
    dt_treino = Column(TIMESTAMP(timezone=True), server_default=func.now())


'''Preço, pegada de CO2 e concentração de produção (HHI) por elemento'''
class ElementoReferencia(Base):
    __tablename__ = 'elemento_referencia'

    nm_sigla = Column(VARCHAR(3), primary_key=True)
    nm_elemento = Column(VARCHAR(50))
    vl_massa_atomica = Column(Float)
    vl_preco_usd_kg = Column(Float)
    ds_fonte_preco = Column(Text)
    vl_co2_kg_kg = Column(Float)
    vl_co2_p2_5 = Column(Float)
    vl_co2_p97_5 = Column(Float)
    ds_fonte_co2 = Column(Text)
    vl_hhi_producao = Column(Integer)
    vl_hhi_reserva = Column(Integer)
    ds_fonte_hhi = Column(Text)
    fl_critico = Column(Boolean)
    dt_atualizacao = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())


'''Uma execução de otimização: metas, restrições e parâmetros do algoritmo'''
class Otimizacao(Base):
    __tablename__ = 'otimizacao'

    id_otimizacao = Column(Integer, primary_key=True)
    nm_otimizacao = Column(VARCHAR(255))
    nm_usuario_solicitante = Column(VARCHAR(255))
    ds_objetivo = Column(Text)                    # pedido do usuário em texto livre
    ds_metas = Column(JSONB)                      # ex.: {"limite_escoamento": {"min": 1500}}
    ds_restricoes = Column(JSONB)                 # ex.: {"Ni": {"max": 1.0}, "Co": {"max": 0}}
    ds_objetivos = Column(JSONB)                  # ex.: ["custo", "co2"]
    nm_algoritmo = Column(VARCHAR(100))
    nr_iteracoes = Column(Integer)
    ds_parametros = Column(JSONB)
    nm_status = Column(VARCHAR(50), server_default='Pendente')
    dt_criacao = Column(TIMESTAMP(timezone=True), server_default=func.now())
    dt_inicio = Column(TIMESTAMP(timezone=True))
    dt_fim = Column(TIMESTAMP(timezone=True))
    ds_observacao = Column(Text)


'''Composições candidatas geradas por uma otimização'''
class CandidatoComposicao(Base):
    __tablename__ = 'candidato_composicao'

    id_candidato = Column(Integer, primary_key=True)
    id_otimizacao = Column(Integer, ForeignKey("otimizacao.id_otimizacao"), nullable=False)
    ds_composicao = Column(JSONB, nullable=False)  # ex.: {"C": 0.3, "Cr": 1.0, ..., "Fe": 97.2}
    nm_base_comp = Column(VARCHAR(50), server_default='% em massa')
    vl_custo_usd_kg = Column(Float)
    vl_co2_kg_kg = Column(Float)
    vl_hhi = Column(Float)
    fl_no_dominio = Column(Boolean)
    fl_pareto = Column(Boolean)
    nr_ranking = Column(Integer)
    ds_observacao = Column(Text)
    dt_criacao = Column(TIMESTAMP(timezone=True), server_default=func.now())


'''Propriedades previstas para cada candidato (uma linha por propriedade)'''
class CandidatoPrevisao(Base):
    __tablename__ = 'candidato_previsao'

    id_previsao = Column(Integer, primary_key=True)
    id_candidato = Column(Integer, ForeignKey("candidato_composicao.id_candidato"), nullable=False)
    id_modelo = Column(Integer, ForeignKey("modelo_ml.id_modelo"))
    nm_propriedade = Column(VARCHAR(100), nullable=False)
    vl_previsto = Column(Float)
    vl_incerteza = Column(Float)                  # desvio padrão do ensemble
    ds_unidade = Column(VARCHAR(30))


'''Etapas da rota de tratamento térmico sugerida para um candidato'''
class RotaTratamento(Base):
    __tablename__ = 'rota_tratamento'

    id_rota = Column(Integer, primary_key=True)
    id_candidato = Column(Integer, ForeignKey("candidato_composicao.id_candidato"), nullable=False)
    nr_etapa = Column(Integer, nullable=False)
    nm_etapa = Column(VARCHAR(100))               # austenitização, têmpera, revenimento...
    vl_temperatura_c = Column(Float)
    vl_tempo_h = Column(Float)
    nm_meio_resfriamento = Column(VARCHAR(100))
    ds_observacao = Column(Text)


'''Resultados dos cálculos metalúrgicos do tratamento térmico de um candidato'''
class PrevisaoTratamento(Base):
    __tablename__ = 'previsao_tratamento'

    id_prev_trat = Column(Integer, primary_key=True)
    id_candidato = Column(Integer, ForeignKey("candidato_composicao.id_candidato"), nullable=False)
    vl_ac1_c = Column(Float)
    vl_ac3_c = Column(Float)
    vl_ms_c = Column(Float)
    vl_fracao_martensita = Column(Float)
    vl_param_hj = Column(Float)                   # parâmetro de Hollomon-Jaffe
    vl_dureza_hrc = Column(Float)
    ds_metodo = Column(Text)


'''Estruturas candidatas da etapa de descoberta (triagem por GNN pré-treinada)'''
class CandidatoEstrutura(Base):
    __tablename__ = 'candidato_estrutura'

    id_cand_estr = Column(Integer, primary_key=True)
    id_otimizacao = Column(Integer, ForeignKey("otimizacao.id_otimizacao"))
    id_modelo = Column(Integer, ForeignKey("modelo_ml.id_modelo"))
    nm_formula = Column(VARCHAR(100))
    nm_origem = Column(VARCHAR(255))              # ex.: substituição em mp-xxxx
    ds_cif = Column(Text)
    vl_energia_ev_atomo = Column(Float)
    vl_e_hull_ev_atomo = Column(Float)
    fl_possivel_estavel = Column(Boolean)
    ds_observacao = Column(Text)
    dt_criacao = Column(TIMESTAMP(timezone=True), server_default=func.now())
