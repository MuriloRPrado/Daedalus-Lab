######################### BIBLIOTECAS ###################################
from database import engine
from Rotinas.exportar_retorno import gerar_arquivo_retorno_cientistas
from sqlalchemy import text
from sqlalchemy.orm import Session
#########################################################################

"""Armazena o retorno do agente e devolve o ID do registro."""
def salvar_retorno(id_projeto: int, nm_agente: str, ds_retorno: str,) -> int:

    if not isinstance(nm_agente, str) or not nm_agente.strip():
        raise ValueError("O nome do agente deve ser um texto não vazio.")

    nm_agente = nm_agente.strip()

    if len(nm_agente) > 100:
        raise ValueError("O nome do agente deve ter até 100 caracteres.")

    if not isinstance(ds_retorno, str) or not ds_retorno.strip():
        raise ValueError("O retorno deve ser um texto não vazio.")

    comando = text("""
        INSERT INTO retorno_cientistas (
            id_projeto,
            nm_agente,
            ds_retorno,
            fl_utilizada
        )
        VALUES (
            :id_projeto,
            :nm_agente,
            :ds_retorno,
            :fl_utilizada
        )
        RETURNING id_ret_cientistas
    """)

    with Session(engine) as session:
        with session.begin():
            id_registro = session.execute(
                comando,
                {
                    "id_projeto": id_projeto,
                    "nm_agente": nm_agente,
                    "ds_retorno": ds_retorno,
                    "fl_utilizada": False
                },
            ).scalar_one()

    gerar_arquivo_retorno_cientistas(id_registro, id_projeto, nm_agente)

    return id_registro

def marcar_retornos_utilizados_caliope(
    id_projeto: int,
    id_ret_prometeu: int,
    id_ret_atena: int,
    id_ret_argos: int,
    id_ret_temis: int,
) -> None:
    """Marca atomicamente os quatro pareceres consumidos, sem alterar o de Calíope."""
    retornos = (
        (id_ret_prometeu, "Prometeu"),
        (id_ret_atena, "Atena"),
        (id_ret_argos, "Argos"),
        (id_ret_temis, "Têmis"),
    )
    if len({identificador for identificador, _ in retornos}) != len(retornos):
        raise ValueError("Os IDs dos pareceres devem ser distintos.")

    comando = text("""
        UPDATE retorno_cientistas
        SET fl_utilizada = :utilizada
        WHERE id_ret_cientistas = :id_retorno
          AND id_projeto = :id_projeto
          AND nm_agente = :nm_agente
        RETURNING id_ret_cientistas
    """)
    with Session(engine) as session:
        with session.begin():
            for id_retorno, nm_agente in retornos:
                atualizado = session.execute(comando, {
                    "utilizada": True,
                    "id_retorno": id_retorno,
                    "id_projeto": id_projeto,
                    "nm_agente": nm_agente,
                }).scalar_one_or_none()
                if atualizado is None:
                    raise ValueError(
                        f"Retorno {id_retorno} de {nm_agente} não pertence "
                        f"ao projeto {id_projeto} ou não existe."
                    )
