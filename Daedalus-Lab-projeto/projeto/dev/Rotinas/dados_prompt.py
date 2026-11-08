"""Consultas usadas pelos geradores de prompt dos agentes (dados do projeto e retornos anteriores)."""
######################### BIBLIOTECAS ###################################
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from database import ElementoProjeto, Projeto, Propriedade, ProjetoRequisitos, RetornoCientista, engine
#########################################################################

COLUNAS_PROJETO = (
    Projeto.id_projeto,
    Projeto.nm_usuario_solicitante,
    Projeto.nm_tp_sigla,
    Projeto.nm_projeto,
    Projeto.ds_aplicacao,
    Projeto.ds_ambiente,
    Projeto.nm_material_ref,
    Projeto.ds_rota_fabricacao,
    Projeto.ds_disponibilidade,
    Projeto.ds_custo,
    Projeto.cd_status,
    Projeto.ds_observacao,
)


def em_json(dados) -> str:
    """Transforma os dados em texto JSON legível para o prompt."""
    return json.dumps(dados, ensure_ascii=False, indent=2, allow_nan=False, default=str)


def dados_projeto(id_projeto: int) -> dict:
    """Dados da tabela projeto. Erro se o projeto não existir."""
    with Session(engine) as session:
        resultado = session.execute(
            select(*COLUNAS_PROJETO).where(Projeto.id_projeto == id_projeto)
        ).mappings().one_or_none()
    if resultado is None:
        raise ValueError(f"Projeto com ID:{id_projeto} não encontrado.")
    return dict(resultado)


def requisitos_projeto(id_projeto: int) -> list[dict]:
    """Requisitos de propriedades do projeto (pode ser lista vazia)."""
    with Session(engine) as session:
        registros = session.execute(
            select(
                ProjetoRequisitos.id_requisitos,
                ProjetoRequisitos.id_projeto,
                ProjetoRequisitos.id_propriedade,
                ProjetoRequisitos.nm_propriedade,
                ProjetoRequisitos.ds_operador,
                ProjetoRequisitos.vl_alvo,
                ProjetoRequisitos.vl_min,
                ProjetoRequisitos.vl_max,
                ProjetoRequisitos.ds_unidade,
                ProjetoRequisitos.fl_obrigatorio,
                ProjetoRequisitos.ds_observacao,
            ).where(ProjetoRequisitos.id_projeto == id_projeto).order_by(ProjetoRequisitos.id_requisitos)
        ).mappings().all()
    return [dict(r) for r in registros]


def restricoes_projeto(id_projeto: int) -> list[dict]:
    """Restrições químicas (elementos) do projeto (pode ser lista vazia)."""
    with Session(engine) as session:
        registros = session.execute(
            select(
                ElementoProjeto.id_elemento_restricao,
                ElementoProjeto.id_projeto,
                ElementoProjeto.nm_sigla_elemento,
                ElementoProjeto.tp_restricao,
                ElementoProjeto.ds_limite,
                ElementoProjeto.ds_observacao,
            ).where(ElementoProjeto.id_projeto == id_projeto).order_by(ElementoProjeto.id_elemento_restricao)
        ).mappings().all()
    return [dict(r) for r in registros]


def propriedades_cadastradas() -> list[dict]:
    """Propriedades cadastradas em propriedades_materiais, que a Calíope deve pesquisar."""
    with Session(engine) as session:
        registros = session.execute(
            select(
                Propriedade.id_propriedade,
                Propriedade.nm_propriedade,
                Propriedade.nm_categoria_prop,
                Propriedade.ds_unidade,
                Propriedade.ds_definicao,
            ).order_by(Propriedade.nm_categoria_prop, Propriedade.id_propriedade)
        ).mappings().all()
    return [dict(r) for r in registros]


def retorno_agente(id_retorno: int, id_projeto: int, nm_agente: str) -> dict:
    """Retorno gravado por um agente para o projeto. Erro se não existir."""
    with Session(engine) as session:
        resultado = session.execute(
            select(
                RetornoCientista.id_ret_cientistas,
                RetornoCientista.id_projeto,
                RetornoCientista.nm_agente,
                RetornoCientista.ds_retorno,
            ).where(
                RetornoCientista.id_ret_cientistas == id_retorno,
                RetornoCientista.id_projeto == id_projeto,
                RetornoCientista.nm_agente == nm_agente,
            )
        ).mappings().one_or_none()
    if resultado is None:
        raise ValueError(f"Não há retorno de {nm_agente} com IDPesquisa {id_retorno} para o projeto {id_projeto}.")
    return dict(resultado)
