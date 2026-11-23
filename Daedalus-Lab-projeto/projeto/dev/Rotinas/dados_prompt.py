"""Consultas usadas pelos geradores de prompt dos agentes (dados do projeto e retornos anteriores)."""
######################### BIBLIOTECAS ###################################
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from database import ElementoProjeto, PesquisaElementos, Projeto, ProjetoRequisitos, engine
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
                ProjetoRequisitos.nm_propriedade,
                ProjetoRequisitos.ds_descricao,
                ProjetoRequisitos.ds_unidade,
            ).where(ProjetoRequisitos.id_projeto == id_projeto).order_by(ProjetoRequisitos.id_requisitos)
        ).mappings().all()
    return [dict(r) for r in registros]


def restricoes_projeto(id_projeto: int) -> list[dict]:
    """Restrições químicas (elementos) do projeto (pode ser lista vazia)."""
    with Session(engine) as session:
        registros = session.execute(
            select(
                ElementoProjeto.nm_sigla_elemento,
                ElementoProjeto.ds_restricao,
            ).where(ElementoProjeto.id_projeto == id_projeto).order_by(ElementoProjeto.id_elemento_restricao)
        ).mappings().all()
    return [dict(r) for r in registros]


def elementos_pesquisados(id_projeto: int) -> list[dict]:
    """Elementos levantados pela Atena (pesquisa_elementos) com a justificativa gravada."""
    with Session(engine) as session:
        registros = session.execute(
            select(PesquisaElementos.nm_sigla_elemento, PesquisaElementos.ds_observacao)
            .where(PesquisaElementos.id_projeto == id_projeto).order_by(PesquisaElementos.id_elemento)
        ).mappings().all()
    return [dict(r) for r in registros]
