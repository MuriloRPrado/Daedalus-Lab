############################## BIBLIOTECAS ##############################
from sqlalchemy import create_engine, Column, Integer, Numeric, VARCHAR, DATE, Boolean, ForeignKey, Text, TIMESTAMP, func, Float, UniqueConstraint, CHAR
from sqlalchemy.orm import sessionmaker, declarative_base
import os

############################## CONEXÃO COM O BANCO DE DADOS ##############################
engine = create_engine(os.getenv("DATABASE_URL", "postgresql+pg8000://euProjetoDaedalus:senhaTeste@localhost:5432/dedalos"))

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
    ds_disponibilidade = Column(Text)
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
    ds_operador = Column(VARCHAR(10))
    vl_alvo = Column(Float)
    vl_min = Column(Float)
    vl_max = Column(Float)
    ds_unidade = Column(VARCHAR(30))
    fl_obrigatorio = Column(Boolean)
    ds_observacao = Column(VARCHAR(255))

'''Tabela que armazena os elementos prioritários, restritos ou proibidos para a pesquisa'''
class ElementoProjeto(Base):
    __tablename__ = 'elemento_proj_restricao'

    id_elemento_restricao = Column(Integer, primary_key=True)
    id_projeto = Column(Integer, ForeignKey("projeto.id_projeto"))
    nm_sigla_elemento = Column(VARCHAR(50))
    tp_restricao = Column(VARCHAR(50))
    ds_limite = Column(VARCHAR(100))
    ds_observacao = Column(VARCHAR(255))

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
    ds_observacao = Column(Text)

'''Tabela que armazena os estados dos materiais'''
class MateriaisEstado(Base):
    __tablename__ = 'materiais_estado'

    id_mat_estado = Column(Integer, primary_key=True)
    id_material = Column(Integer, ForeignKey("materiais.id_material"))
    ds_aplicacao = Column(Text)
    ds_ambiente = Column(Text)
    ds_condicao = Column(VARCHAR(255))
    ds_rota_fabricacao = Column(VARCHAR(255))
    ds_trat_termico = Column(Text)
    ds_trat_mecanico = Column(Text)

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

'''Tabela que armazena as estruturas cristalinas dos materiais'''
class EstruturaCristalina(Base):
    __tablename__ = 'fase_estrut_cristalina'

    id_fase = Column(Integer, primary_key=True)
    id_mat_estado = Column(Integer, ForeignKey("materiais_estado.id_mat_estado"))
    nm_fase = Column(VARCHAR(255))
    nm_estrut_cristalina = Column(VARCHAR(255))
    ds_grupo_espacial = Column(Text)
    vl_fracao_fase = Column(VARCHAR(255))
    nm_base_fracao = Column(VARCHAR(100))
    vl_parametro_a_ang = Column(Float)
    vl_parametro_b_ang = Column(Float)
    vl_parametro_c_ang = Column(Float)
    vl_angulo_alfa_graus = Column(Float)
    vl_angulo_beta_graus = Column(Float)
    vl_angulo_gama_graus = Column(Float)
    vl_massa_especifica_kgm3 = Column(Float)
    vl_temperatura_k = Column(Float)
    vl_pressao_pa = Column(Float)

'''Tabela que armazena as fontes vinculadas as composições dos materiais'''
class ComposicaoFonte(Base):
    __tablename__ = 'cm_fontes'

    id_cm_fonte = Column(Integer, primary_key=True)
    id_composicao = Column(Integer, ForeignKey("composicao_material.id_composicao"))
    id_material = Column(Integer, ForeignKey("materiais.id_material"))
    id_fonte = Column(Integer, ForeignKey("fontes.id_fonte"))

'''Tabela que armazena as fontes vinculadas as estruturas cristalinas dos materiais'''
class EstrutCristalinaFontes(Base):
    __tablename__ = 'fec_fontes'

    id_fec_fonte = Column(Integer, primary_key=True)
    id_fase = Column(Integer, ForeignKey("fase_estrut_cristalina.id_fase"))
    id_mat_estado = Column(Integer, ForeignKey("materiais_estado.id_mat_estado"))
    id_fonte = Column(Integer, ForeignKey("fontes.id_fonte"))

'''Tabela que armazena as fontes dos materiais'''
class MateriaisFonte(Base):
    __tablename__ = 'ma_fontes'

    id_ma_fonte = Column(Integer, primary_key=True)
    id_material = Column(Integer, ForeignKey("materiais.id_material"))
    id_projeto = Column(Integer, ForeignKey("projeto.id_projeto"))
    id_fonte = Column(Integer, ForeignKey("fontes.id_fonte"))

'''Tabela que armazena as fontes dos estados dos materiais'''
class MateriaisEstadosFonte(Base):
    __tablename__ = 'me_fontes'

    id_me_fonte = Column(Integer, primary_key=True)
    id_mat_estado = Column(Integer, ForeignKey("materiais_estado.id_mat_estado"))
    id_material = Column(Integer, ForeignKey("materiais.id_material"))
    id_fonte = Column(Integer, ForeignKey("fontes.id_fonte"))

'''Tabela que armazena os valores das propriedades'''
class ValorPropriedades(Base):
    __tablename__ = 'valor_propriedades_materiais'

    id_vl_prop = Column(Integer, primary_key=True)
    id_propriedade = Column(Integer, ForeignKey("propriedades_materiais.id_propriedade"))
    id_mat_estado = Column(Integer, ForeignKey("materiais_estado.id_mat_estado"))
    vl_prop = Column(Float)
    vl_min_prop = Column(Float)
    vl_max_prop = Column(Float)
    tp_valor = Column(VARCHAR(150))

'''Tabela que armazena as fontes dos valores de propriedades'''
class ValorPropriedadesFonte(Base):
    __tablename__ = 'vlp_fontes'

    id_vlp_fonte = Column(Integer, primary_key=True)
    id_vl_prop = Column(Integer, ForeignKey("valor_propriedades_materiais.id_vl_prop"))
    id_mat_estado = Column(Integer, ForeignKey("materiais_estado.id_mat_estado"))
    id_fonte = Column(Integer, ForeignKey("fontes.id_fonte"))

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
