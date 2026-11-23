import Rotinas.configuracao  # noqa: F401  (carrega .env antes dos demais módulos)
import logging
import sys
import time

from sqlalchemy import select, update, func
from sqlalchemy.orm import Session

from database import engine, Projeto, RetornoCientista

from Cientista_Atena.agenteAtena import executar_pesquisa_atena
from Cientista_Atena.promptAtena import gerar_prompt_atena
from Cientista_Caliope.agenteCaliopeComparacao import caliope_comparacao, executar_caliope_comparacao
from Cientista_Caliope.promptCaliopeComparacao import gerar_prompt_caliope_comparacao
from Rotinas.composicoes_vae import NM_ROTINA as NM_ROTINA_VAE, executar_rotina_vae
from Rotinas.fases_composicoes import NM_ROTINA as NM_ROTINA_FASES, executar_rotina_fases
from Rotinas.exportar_retorno import gerar_arquivo_retorno_cientistas
from Rotinas.retorno_cientistas import marcar_retornos_utilizados
#########################################################################

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Códigos da tabela status
STATUS_AGUARDANDO = 10
STATUS_ERRO = 11
STATUS_CALIOPE_OK = 12
STATUS_EM_ANDAMENTO = 21
STATUS_ATENA_OK = 25
STATUS_VAE_OK = 26

colunas = (
    Projeto.id_projeto,
    Projeto.nm_usuario_solicitante,
    Projeto.nm_tp_sigla,
    Projeto.ds_aplicacao,
    Projeto.ds_ambiente,
    Projeto.nm_material_ref,
    Projeto.ds_rota_fabricacao,
    Projeto.ds_custo,
    Projeto.cd_status,
    Projeto.dt_atualizacao,
)


def atualizar_status(id_projeto: int, novo_status: int):
    """Atualiza o status do projeto e a data de atualização."""
    with Session(engine) as session:
        atualizacao = (
            update(Projeto)
            .where(Projeto.id_projeto == id_projeto)
            .values(cd_status=novo_status, dt_atualizacao=func.now())
        )
        session.execute(atualizacao)
        session.commit()


def retorno_pendente(id_projeto: int, nm_agente: str, apos_id: int = 0) -> int | None:
    """Retorno mais recente do agente ainda não utilizado e gravado depois de apos_id, ou None."""
    with Session(engine) as session:
        consulta = (
            select(RetornoCientista.id_ret_cientistas)
            .where(
                RetornoCientista.id_projeto == id_projeto,
                RetornoCientista.nm_agente == nm_agente,
                RetornoCientista.fl_utilizada == False,
                RetornoCientista.id_ret_cientistas > apos_id)).order_by(RetornoCientista.id_ret_cientistas.desc()).limit(1)
        return session.execute(consulta).scalar_one_or_none()


def reservar_projeto(id_projeto: int | None = None):
    """
    Seleciona o projeto a processar e já o marca como em andamento, na mesma transação.
    FOR UPDATE SKIP LOCKED impede que dois processos peguem o mesmo projeto.
    Sem ID: o projeto NC aguardando mais antigo. Com ID: o projeto NC aguardando ou com erro (retomada).
    Devolve os dados do projeto antes da reserva (cd_status original) ou None.
    """
    consulta = select(*colunas).where(Projeto.nm_tp_sigla == "NC")
    if id_projeto is None:
        consulta = consulta.where(Projeto.cd_status == STATUS_AGUARDANDO).order_by(Projeto.id_projeto.asc()).limit(1)
    else:
        consulta = consulta.where(
            Projeto.id_projeto == id_projeto,
            Projeto.cd_status.in_((STATUS_AGUARDANDO, STATUS_ERRO)))

    with Session(engine) as session:
        with session.begin():
            projeto = session.execute(consulta.with_for_update(skip_locked=True)).one_or_none()
            if projeto is not None:
                session.execute(
                    update(Projeto)
                    .where(Projeto.id_projeto == projeto.id_projeto)
                    .values(cd_status=STATUS_EM_ANDAMENTO, dt_atualizacao=func.now()))
    return projeto


def motivo_indisponivel(id_projeto: int) -> str:
    """Explica por que o projeto do ID informado não pôde ser reservado."""
    with Session(engine) as session:
        existe = session.execute(select(Projeto.id_projeto).where(Projeto.id_projeto == id_projeto)).scalar_one_or_none()
    if existe is None:
        return "Não existe projeto com o ID informado, favor verificar."
    return "O projeto do ID informado não é NC, já finalizou a pesquisa ou está em execução."


def rodar_agente(
    projeto,
    nm_agente: str,
    gerar_prompt,
    executar,
    st_final: int | None,
    args_prompt: tuple = (),
    id_reaproveitado: int | None = None,
    st_andamento: int = STATUS_EM_ANDAMENTO,
    st_erro: int | None = STATUS_ERRO,
    apos_retorno=None,
) -> int:
    """
    Executa um agente de ponta a ponta:
    status de andamento -> prompt -> pesquisa -> confere retorno -> status final.
    Qualquer falha grava o status de erro e relança a exceção (a cadeia para).
    st_erro=None não grava o status de erro; st_final=None não grava o status final.

    id_reaproveitado: retorno já gravado em uma execução anterior (retomada); o agente não roda de novo.
    apos_retorno: rotina executada após conferir o retorno e antes do status final.
    args_prompt: IDs extras (ex.: retornos de agentes anteriores) repassados
    ao gerador de prompt, depois do id do projeto.
    """
    id_proj = projeto.id_projeto
    if id_reaproveitado is None:
        print(f"Pesquisa iniciada pelo agente {nm_agente}")
    else:
        print(f"Retomada: reaproveitando o retorno {id_reaproveitado} do agente {nm_agente}")
    atualizar_status(id_proj, st_andamento)
    try:
        id_retorno = id_reaproveitado
        if id_retorno is None:
            prompt = gerar_prompt(id_proj, *args_prompt)

            print(f"Pesquisa em andamento pelo agente {nm_agente}, aguarde...")
            id_retorno = executar(id_proj, prompt)

        if id_retorno is None:
            raise RuntimeError(f"{nm_agente} terminou, mas não gravou retorno para o projeto")

        # Só consome os pareceres depois de confirmar o retorno da etapa.
        if apos_retorno is not None:
            apos_retorno()

    except Exception:
        logging.exception("Falha no agente %s do projeto %s", nm_agente, id_proj)
        if st_erro is None:
            raise
        try:
            atualizar_status(id_proj, st_erro)
        except Exception:
            logging.exception("Não foi possível gravar o status de erro do projeto %s", id_proj)
        raise

    if st_final is not None:
        atualizar_status(id_proj, st_final)
    print(f"Pesquisa finalizada pelo agente {nm_agente}")
    return id_retorno


def rodar_atena(projeto, id_reaproveitado: int | None = None) -> int:
    return rodar_agente(
        projeto, "Atena", gerar_prompt_atena, executar_pesquisa_atena,
        st_final=STATUS_ATENA_OK, id_reaproveitado=id_reaproveitado)


def rodar_vae(projeto, id_reaproveitado: int | None = None) -> int:
    """Organiza os elementos da Atena, gera as composições com o VAE e grava em composicao_material."""
    return rodar_agente(
        projeto, NM_ROTINA_VAE, lambda _id: "", executar_rotina_vae,
        st_final=STATUS_VAE_OK, id_reaproveitado=id_reaproveitado)


def rodar_fases(projeto, id_reaproveitado: int | None = None) -> int:
    """Calcula as fases previstas (Materials Project, 0 K) das composições do VAE e grava em fases_composicao."""
    return rodar_agente(
        projeto, NM_ROTINA_FASES, lambda _id: "", executar_rotina_fases,
        st_final=None, id_reaproveitado=id_reaproveitado)


def rodar_caliope_comparacao(projeto, id_ret_atena: int, id_ret_vae: int, id_ret_fases: int,
                             id_reaproveitado: int | None = None) -> int:
    """Compara as composições do VAE com materiais reais e gera o relatório em Arquivos/Retornos."""
    def finalizar():
        # Na retomada, o retorno já estava gravado, mas o arquivo pode não ter sido gerado.
        if id_reaproveitado is not None:
            gerar_arquivo_retorno_cientistas(id_reaproveitado, projeto.id_projeto, caliope_comparacao.name)
        marcar_retornos_utilizados(projeto.id_projeto, [(id_ret_atena, "Atena"), (id_ret_vae, NM_ROTINA_VAE),
                                                         (id_ret_fases, NM_ROTINA_FASES)])

    return rodar_agente(
        projeto, caliope_comparacao.name, gerar_prompt_caliope_comparacao, executar_caliope_comparacao,
        st_final=STATUS_CALIOPE_OK, id_reaproveitado=id_reaproveitado, apos_retorno=finalizar)


def iniciar(id_projeto: int | None = None):
    """
    Processa um projeto: Atena -> Rotina VAE -> Rotina Fases -> Calíope (Comparação e relatório final).
    Com o ID de um projeto com erro, retoma a pesquisa: as etapas que já gravaram um retorno ainda não
    utilizado não rodam de novo.
    """
    if id_projeto is not None and not isinstance(id_projeto, int):
        raise TypeError("O ID do projeto deve ser um número, favor verificar.")

    projeto = reservar_projeto(id_projeto)

    if projeto is None:
        if id_projeto is not None:
            raise ValueError(motivo_indisponivel(id_projeto))
        print("Não há pesquisa para ser realizada")
        return None

    retomada = projeto.cd_status == STATUS_ERRO

    def reaproveitar(nm_agente: str) -> int | None:
        """Na retomada, reaproveita o retorno do agente ainda não utilizado."""
        if not retomada:
            return None
        return retorno_pendente(projeto.id_projeto, nm_agente)

    id_ret_atena = rodar_atena(projeto, reaproveitar("Atena"))
    id_ret_vae = rodar_vae(projeto, reaproveitar(NM_ROTINA_VAE))
    id_ret_fases = rodar_fases(projeto, reaproveitar(NM_ROTINA_FASES))
    id_ret_caliope = rodar_caliope_comparacao(
        projeto, id_ret_atena, id_ret_vae, id_ret_fases, reaproveitar(caliope_comparacao.name))

    return projeto.id_projeto, id_ret_caliope


def processar_fila():
    erros_seguidos = 0

    while True:
        try:
            resultado = iniciar()
            erros_seguidos = 0
        except Exception as e:
            erros_seguidos += 1
            print(f"Falha: {e}")
            if erros_seguidos >= 3:
                print("Muitas falhas seguidas, encerrando.")
                break
            time.sleep(10)
            continue

        if resultado is None:
            print("Fila vazia, encerrando.")
            break

        print(f"Concluído: projeto {resultado[0]}, relatório da Calíope {resultado[1]}")


if __name__ == "__main__":
    # Sem argumento: processa a fila. Com o ID: processa (ou retoma, se estiver com erro) só esse projeto.
    #   python orquestrador.py        |  python orquestrador.py 15
    if len(sys.argv) > 1:
        resultado = iniciar(int(sys.argv[1]))
        print(f"Concluído: projeto {resultado[0]}, relatório da Calíope {resultado[1]}")
    else:
        processar_fila()
