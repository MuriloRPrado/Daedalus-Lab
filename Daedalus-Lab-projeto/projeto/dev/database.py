############################## BIBLIOTECAS ##############################
from sqlalchemy import create_engine, Column, Integer, Numeric, VARCHAR, DATE, Boolean, ForeignKey, Text, TIMESTAMP, func, UniqueConstraint, CHAR
from sqlalchemy.orm import sessionmaker, declarative_base
import os

import Rotinas.configuracao  # noqa: F401  (carrega .env)

############################## CONEXÃO COM O BANCO DE DADOS ##############################
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("A variável DATABASE_URL não foi configurada (veja projeto/dev/.env.exemplo).")

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

############################## DECLARANDO TABELAS ##############################
'''Tabela que armazena os dados do projeto'''
class Projeto(Base):
    __tablename__ = 'projeto'

    id_projeto = Column(Integer, primary_key=True)
    nm_usuario_solicitante = Column(VARCHAR(255))
    nm_tp_sigla = Column(VARCHAR(10))
    nm_projeto = Column(VARCHAR(255))
    ds_aplicacao = Column(Text)
    ds_ambiente = Column(Text)
    nm_material_ref = Column(VARCHAR(255))
    ds_rota_fabricacao = Column(VARCHAR(255))
    ds_custo = Column(VARCHAR(100))
    cd_status = Column(Integer, ForeignKey("status.cd_status", name="fk_projeto_status"))
    dt_criacao = Column(TIMESTAMP(timezone=True), server_default=func.now())   # Indicar que a data traz o fuso horário e o próprio SQL preenche o registro
    dt_atualizacao = Column(TIMESTAMP(timezone=True))
    dt_conclusao = Column(TIMESTAMP(timezone=True))
    ds_observacao = Column(Text)

'''Tabela que armazena propriedades prioritárias ou não para a pesquisa'''
class ProjetoRequisitos(Base):
    __tablename__ = 'projeto_requisitos'

    id_requisitos = Column(Integer, primary_key=True)
    id_projeto = Column(Integer, ForeignKey("projeto.id_projeto"))
    id_propriedade = Column(Integer, ForeignKey("propriedades_materiais.id_propriedade"))
    nm_propriedade = Column(VARCHAR(150))
    ds_descricao = Column(Text)
    ds_unidade = Column(VARCHAR(30))

'''Tabela que armazena os elementos prioritários, restritos ou proibidos para a pesquisa'''
class ElementoProjeto(Base):
    __tablename__ = 'elemento_proj_restricao'

    id_elemento_restricao = Column(Integer, primary_key=True)
    id_projeto = Column(Integer, ForeignKey("projeto.id_projeto"))
    nm_sigla_elemento = Column(VARCHAR(50))
    ds_restricao = Column(Text)

'''Tabela que armazena os nomes das propriedades'''
class Propriedade(Base):
    __tablename__ = 'propriedades_materiais'

    id_propriedade = Column(Integer, primary_key=True)
    nm_propriedade = Column(VARCHAR(100))
    nm_categoria_prop = Column(VARCHAR(100))
    ds_unidade = Column(VARCHAR(255))
    ds_definicao = Column(Text)

'''Tabela que armazena os status para serem utilizados pelo sistema'''
class Status(Base):
    __tablename__ = 'status'
    __table_args__ = (UniqueConstraint("cd_status", name="uq_status_cd_status"),)

    id_status = Column(Integer, primary_key=True)
    cd_status = Column(Integer)
    nm_status = Column(VARCHAR(50))
    ds_status = Column(VARCHAR(80))
    ds_dominio = Column(VARCHAR(80))

'''Tabela que armazena os tipos de projetos possível no sistema'''
class TpProjeto(Base):
    __tablename__ = 'tp_projeto'

    id_tp_projeto = Column(Integer, primary_key=True)
    cd_tp_projeto = Column(Integer)
    nm_tp_sigla = Column(VARCHAR(10))
    ds_tp_projeto = Column(VARCHAR(80))
    fl_ativo = Column(Boolean)

'''Tabela que armazena os retornos dos agentes do time de Cientistas'''
class RetornoCientista(Base):
    __tablename__ = 'retorno_cientistas'

    id_ret_cientistas = Column(Integer, primary_key=True)
    id_projeto = Column(Integer, ForeignKey("projeto.id_projeto"))
    nm_agente = Column(VARCHAR(100))
    ds_retorno = Column(Text)
    fl_utilizada = Column(Boolean)
    dt_criacao = Column(TIMESTAMP(timezone=True), server_default=func.now())

'''Tabela que armazena os materiais'''
class Materiais(Base):
    __tablename__ = 'materiais'

    id_material = Column(Integer, primary_key=True)
    id_projeto = Column(Integer, ForeignKey("projeto.id_projeto"))
    nm_grupo = Column(VARCHAR(50))
    nm_sub_grupo = Column(VARCHAR(50))
    nm_norma_designacao = Column(VARCHAR(150))
    nm_material = Column(VARCHAR(100))
    ds_aplicacao = Column(Text)
    ds_ambiente = Column(Text)
    ds_condicao = Column(Text)
    ds_rota_fabricacao = Column(Text)
    ds_trat_termico = Column(Text)
    ds_trat_mecanico = Column(Text)
    ds_observacao = Column(Text)

'''Tabela que armazena as composições químicas dos materiais'''
class ComposicaoMaterial(Base):
    __tablename__ = 'composicao_material'

    id_composicao = Column(Integer, primary_key=True)
    id_material = Column(Integer, ForeignKey("materiais.id_material"))
    nm_base_comp = Column(VARCHAR(50))
    pe_min = Column(Numeric(7,4))
    pe_max = Column(Numeric(7,4))
    fl_elem_balanco = Column(Boolean)
    ds_observacao = Column(Text)
    nm_sigla = Column(VARCHAR(80))

class Fontes(Base):
    __tablename__ = 'fontes'

    id_fonte = Column(Integer, primary_key=True)
    tp_fonte = Column(VARCHAR(50))
    nm_titulo = Column(Text)
    nm_autores = Column(Text)
    nm_instituicao_publicadora = Column(Text)
    nr_ano_publicacao = Column(Integer)
    cd_doi = Column(Text)
    nm_url = Column(Text)
    cd_identificador_externo = Column(Text)
    ds_versao = Column(VARCHAR(100))
    dt_acesso = Column(DATE)
    nm_caminho_arquivo = Column(Text)
    ds_observacoes = Column(Text)
    dt_criacao = Column(TIMESTAMP(timezone=True), server_default=func.now())

class FonteConsultada(Base):
    __tablename__ = 'fonte_consultada'

    id_fonte = Column(Integer, primary_key=True)
    ds_url = Column(Text, nullable=False)
    ds_url_normalizada = Column(Text, nullable=False, unique=True)
    nm_dominio = Column(VARCHAR(255), nullable=False)
    tp_conteudo = Column(VARCHAR(10), nullable=False)
    tp_nivel_fonte = Column(VARCHAR(30))
    ds_titulo = Column(Text)
    ds_conteudo = Column(Text)
    nr_paginas_pdf = Column(Integer)
    nr_paginas_lidas = Column(Integer)
    fl_pdf_truncado = Column(Boolean, server_default='false')
    cd_http_status = Column(Integer)
    ds_hash_conteudo = Column(CHAR(64))
    ds_doi = Column(VARCHAR(255))
    dt_consulta = Column(TIMESTAMP(timezone=True), server_default=func.now())
    dt_expiracao = Column(TIMESTAMP(timezone=True))

class LogConsultaExterna(Base):
    __tablename__ = 'log_consulta_externa'

    id_log = Column(Integer, primary_key=True)
    id_projeto = Column(Integer, ForeignKey("projeto.id_projeto"))
    nm_agente = Column(VARCHAR(100))
    nm_servico = Column(VARCHAR(30), nullable=False)
    tp_operacao = Column(VARCHAR(30), nullable=False)
    ds_consulta = Column(Text)
    id_fonte = Column(Integer, ForeignKey("fonte_consultada.id_fonte"))
    fl_cache = Column(Boolean, server_default='false')
    vl_creditos = Column(Integer, server_default='0')
    ds_erro = Column(Text)
    dt_consulta = Column(TIMESTAMP(timezone=True), server_default=func.now())

class PesquisaElementos(Base):
    __tablename__ = 'pesquisa_elementos'

    id_elemento = Column(Integer, primary_key=True)
    id_projeto = Column(Integer, ForeignKey("projeto.id_projeto"))
    nm_sigla_elemento = Column(VARCHAR(50))
    ds_observacao = Column(Text)

class ElementosFontes(Base):
    __tablename__ = 'elementos_fontes'

    id_ele_fonte = Column(Integer, primary_key=True)
    id_fonte = Column(Integer, ForeignKey("fontes.id_fonte"))
    id_elemento = Column(Integer, ForeignKey("pesquisa_elementos.id_elemento"))
'''Tabela que armazena as fases previstas (calculadas) para as composições geradas pelo VAE'''
class FasesComposicao(Base):
    __tablename__ = 'fases_composicao'

    id_fase = Column(Integer, primary_key=True)
    id_material = Column(Integer, ForeignKey("materiais.id_material"), nullable=False)
    nm_fase = Column(VARCHAR(100), nullable=False)
    cd_material_mp = Column(VARCHAR(50))
    nm_grupo_espacial = Column(VARCHAR(30))
    nm_sistema_cristalino = Column(VARCHAR(30))
    pe_fracao_atomica = Column(Numeric(7,4))
    pe_fracao_massa = Column(Numeric(7,4))
    vl_energia_formacao = Column(Numeric(10,6))
    ds_sistema_quimico = Column(VARCHAR(100))
    ds_versao_base = Column(VARCHAR(30))
    id_fonte = Column(Integer, ForeignKey("fontes.id_fonte"))
    ds_observacao = Column(Text)
    dt_criacao = Column(TIMESTAMP(timezone=True), server_default=func.now())
