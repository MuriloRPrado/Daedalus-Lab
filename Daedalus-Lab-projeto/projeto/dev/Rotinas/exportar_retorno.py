######################### BIBLIOTECAS ###################################
from database import engine, RetornoCientista
from Rotinas.configuracao import PASTA_RETORNOS
from sqlalchemy import select
from sqlalchemy.orm import Session
#########################################################################

# Caminho da pasta onde o arquivo será armazenado
pasta = PASTA_RETORNOS

'''Função para consultar se há retorno dentro da tabela de retornos dos cientistas'''
def gerar_arquivo_retorno_cientistas(id_pesquisa: int, id_projeto: int, nm_agente: str):
    with Session(engine) as session:
        retorno = select(
            RetornoCientista.id_ret_cientistas,
            RetornoCientista.id_projeto,
            RetornoCientista.nm_agente,
            RetornoCientista.ds_retorno,
            RetornoCientista.dt_criacao
        ).where(RetornoCientista.id_ret_cientistas == id_pesquisa, RetornoCientista.id_projeto == id_projeto, RetornoCientista.nm_agente == nm_agente)     # Consulta se existe registro com ID projeto e nome de agente pesquisado
        resultado = session.execute(retorno).one_or_none()                                              # Retorna a consulta

    if resultado is not None:
        pasta.mkdir(parents=True, exist_ok=True)
        arquivo = pasta / f"pesquisa_{resultado.nm_agente}_IDProjeto{resultado.id_projeto}_IDPesquisa{resultado.id_ret_cientistas}.md"          # Cria o arquivo com o seguinte formato: pesquisa_NmAgente_idProjetoNr_id.md

        with arquivo.open("w", encoding="utf-8") as f:
            f.write(resultado.ds_retorno)                                                               # Após criar o arquivo, armazena o retorno da consulta dentro dele

        return arquivo                                                                                  # Retorna o arquivo
    else:
        return "Não existe retorno registrado"                                                          # Caso não tenha registro, retorno essa mensagem

def consultar_retorno_agente(id_pesquisa: int, id_projeto: int, nm_agente: str) -> dict | None:
    """Recupera o texto de um retorno de agente gravado na tabela retorno_cientistas.

    Args:
        id_pesquisa: ID do retorno (id_ret_cientistas) informado no prompt.
        id_projeto: ID do projeto.
        nm_agente: Nome do agente que gravou o retorno (ex.: "Prometeu").
    """
    with Session(engine) as session:
        conteudo = session.execute(
            select(RetornoCientista.ds_retorno).where(
                RetornoCientista.id_ret_cientistas == id_pesquisa,
                RetornoCientista.id_projeto == id_projeto,
                RetornoCientista.nm_agente == nm_agente,
            )
        ).scalar_one_or_none()
    if conteudo is None:
        return None
    return {"encontrado": True, "conteudo": conteudo}
