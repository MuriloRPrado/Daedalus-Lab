import Rotinas.configuracao  # noqa: F401  (carrega .env antes dos demais módulos)
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select, update, func
from sqlalchemy.orm import Session

from database import engine, Projeto, RetornoCientista
from Rotinas.retorno_cientistas import marcar_retornos_utilizados

from Cientista_Prometeu.agentePrometeu import executar_pesquisa_prometeu
from Cientista_Prometeu.promptPrometeu import gerar_prompt_prometeu

from Cientista_Atena.promptAtena import gerar_prompt_atena
from Cientista_Atena.agenteAtena import executar_pesquisa_atena

from Cientista_Argos.promptArgos import gerar_prompt_argos
from Cientista_Argos.agenteArgos import executar_pesquisa_argos

from Cientista_Temis.promptTemis import gerar_prompt_temis
from Cientista_Temis.agenteTemis import executar_pesquisa_temis

from Cientista_Caliope.promptCaliope import (
    gerar_prompt_caliope_composicao, gerar_prompt_caliope_estrutura, gerar_prompt_caliope_propriedades,
    gerar_prompt_caliope_relatorio,
)
from Cientista_Caliope.agenteCaliope import (
    executar_caliope_composicao, executar_caliope_estrutura, executar_caliope_propriedades,
    executar_caliope_relatorio,
)
#########################################################################

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Códigos da tabela status
STATUS_AGUARDANDO = 10
STATUS_ERRO = 11
STATUS_EM_ANDAMENTO = 21
STATUS_PROMETEU_OK = 23
STATUS_TEMIS_OK = 28
STATUS_ORGANIZANDO_PESQUISA = 29
STATUS_FINAL_OK = 12

SEGUNDOS_ENTRE_AGENTES = 5

colunas = (
    Projeto.id_projeto,
    Projeto.nm_usuario_solicitante,
    Projeto.nm_tp_sigla,
    Projeto.ds_aplicacao,
    Projeto.ds_ambiente,
    Projeto.nm_material_ref,
    Projeto.ds_rota_fabricacao,
    Projeto.ds_disponibilidade,
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
    Sem ID: o projeto SME aguardando mais antigo. Com ID: o projeto SME aguardando ou com erro (retomada).
    Devolve os dados do projeto antes da reserva (cd_status original) ou None.
    """
    consulta = select(*colunas).where(Projeto.nm_tp_sigla == "SME")
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
    return "O projeto do ID informado não é SME, já finalizou a pesquisa ou está em execução."


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
    st_erro=None não grava o erro (etapas paralelas: quem grava é rodar_em_paralelo, ao fim de todas).
    st_final=None não grava o status final (etapas paralelas: o projeto segue em andamento até a próxima etapa).

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


def rodar_em_paralelo(projeto, *etapas) -> list[int]:
    """
    Executa etapas independentes ao mesmo tempo. Se alguma falhar, as demais terminam e o projeto fica com erro.
    As etapas não gravam o status de erro: o projeto só fica disponível para retomada depois que todas terminam.
    """
    with ThreadPoolExecutor(max_workers=len(etapas)) as executor:
        futuros = [executor.submit(etapa) for etapa in etapas]
    erros = [futuro.exception() for futuro in futuros if futuro.exception() is not None]
    if erros:
        atualizar_status(projeto.id_projeto, STATUS_ERRO)
        raise erros[0]
    return [futuro.result() for futuro in futuros]


def rodar_prometeu(projeto, id_reaproveitado: int | None = None) -> int:
    return rodar_agente(
        projeto, "Prometeu", gerar_prompt_prometeu, executar_pesquisa_prometeu,
        st_final=STATUS_PROMETEU_OK, id_reaproveitado=id_reaproveitado)


def rodar_atena(projeto, id_ret_prometeu: int, id_reaproveitado: int | None = None,
                st_erro: int | None = STATUS_ERRO) -> int:
    return rodar_agente(
        projeto, "Atena", gerar_prompt_atena, executar_pesquisa_atena,
        st_final=None, args_prompt=(id_ret_prometeu,), id_reaproveitado=id_reaproveitado,
        st_erro=st_erro)


def rodar_argos(projeto, id_ret_prometeu: int, id_reaproveitado: int | None = None,
                st_erro: int | None = STATUS_ERRO) -> int:
    return rodar_agente(
        projeto, "Argos", gerar_prompt_argos, executar_pesquisa_argos,
        st_final=None, args_prompt=(id_ret_prometeu,), id_reaproveitado=id_reaproveitado,
        st_erro=st_erro)


def rodar_temis(projeto, id_ret_prometeu: int, id_ret_atena: int, id_ret_argos: int,
                id_reaproveitado: int | None = None) -> int:
    return rodar_agente(
        projeto, "Têmis", gerar_prompt_temis, executar_pesquisa_temis,
        st_final=STATUS_TEMIS_OK,
        args_prompt=(id_ret_prometeu, id_ret_atena, id_ret_argos), id_reaproveitado=id_reaproveitado)


CALIOPE_COMPOSICAO = "Calíope - Composição"
CALIOPE_PROPRIEDADES = "Calíope - Propriedades"
CALIOPE_ESTRUTURA = "Calíope - Estrutura Cristalina"
CALIOPE_RELATORIO = "Calíope - Relatório"


def rodar_caliope_pesquisa(projeto, nm_agente: str, gerar_prompt, executar, id_ret_temis: int,
                           id_reaproveitado: int | None = None) -> int:
    """Etapa de pesquisa da Calíope: o projeto fica em "Organizando Pesquisa" até o relatório."""
    return rodar_agente(
        projeto, nm_agente, gerar_prompt, executar,
        st_final=None, args_prompt=(id_ret_temis,), id_reaproveitado=id_reaproveitado,
        st_andamento=STATUS_ORGANIZANDO_PESQUISA)


def rodar_caliope_relatorio(projeto, retornos: dict[str, int], id_reaproveitado: int | None = None) -> int:
    """retornos: id_ret_cientistas de cada agente anterior; todos são marcados como utilizados ao fim."""
    return rodar_agente(
        projeto, CALIOPE_RELATORIO, gerar_prompt_caliope_relatorio, executar_caliope_relatorio,
        st_final=STATUS_FINAL_OK, st_andamento=STATUS_ORGANIZANDO_PESQUISA,
        args_prompt=(retornos[CALIOPE_COMPOSICAO], retornos[CALIOPE_PROPRIEDADES], retornos[CALIOPE_ESTRUTURA]),
        id_reaproveitado=id_reaproveitado,
        apos_retorno=lambda: marcar_retornos_utilizados(
            projeto.id_projeto, [(id_ret, nm_agente) for nm_agente, id_ret in retornos.items()]))


def pausa_entre_agentes():
    print(f"Aguardando {SEGUNDOS_ENTRE_AGENTES} segundos")
    time.sleep(SEGUNDOS_ENTRE_AGENTES)


def iniciar(id_projeto: int | None = None):
    """
    Processa um projeto. Com o ID de um projeto com erro, retoma a pesquisa:
    reaproveita os retornos ainda não utilizados das etapas concluídas e roda só as seguintes.
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

    def reaproveitar(nm_agente: str, *ids_anteriores: int) -> int | None:
        """Na retomada, o retorno só vale se foi gravado depois dos retornos em que se baseou."""
        if not retomada:
            return None
        return retorno_pendente(projeto.id_projeto, nm_agente, max(ids_anteriores, default=0))

    # Cada etapa só roda se a anterior terminou sem exceção
    id_ret_prometeu = rodar_prometeu(projeto, reaproveitar("Prometeu"))
    pausa_entre_agentes()

    # Atena e Argos dependem só do Prometeu, então rodam ao mesmo tempo.
    id_ret_atena, id_ret_argos = rodar_em_paralelo(
        projeto,
        lambda: rodar_atena(projeto, id_ret_prometeu, reaproveitar("Atena", id_ret_prometeu), st_erro=None),
        lambda: rodar_argos(projeto, id_ret_prometeu, reaproveitar("Argos", id_ret_prometeu), st_erro=None),
    )
    pausa_entre_agentes()

    id_ret_temis = rodar_temis(
        projeto, id_ret_prometeu, id_ret_atena, id_ret_argos,
        reaproveitar("Têmis", id_ret_atena, id_ret_argos))
    pausa_entre_agentes()

    # Calíope em etapas sequenciais: cada uma grava no banco a sua parte da caracterização.
    retornos = {"Prometeu": id_ret_prometeu, "Atena": id_ret_atena, "Argos": id_ret_argos, "Têmis": id_ret_temis}
    for nm_agente, gerar_prompt, executar in (
        (CALIOPE_COMPOSICAO, gerar_prompt_caliope_composicao, executar_caliope_composicao),
        (CALIOPE_PROPRIEDADES, gerar_prompt_caliope_propriedades, executar_caliope_propriedades),
        (CALIOPE_ESTRUTURA, gerar_prompt_caliope_estrutura, executar_caliope_estrutura),
    ):
        retornos[nm_agente] = rodar_caliope_pesquisa(
            projeto, nm_agente, gerar_prompt, executar, id_ret_temis, reaproveitar(nm_agente, id_ret_temis))
        pausa_entre_agentes()

    id_ret_final = rodar_caliope_relatorio(
        projeto, retornos,
        reaproveitar(CALIOPE_RELATORIO, *(retornos[n] for n in (CALIOPE_COMPOSICAO, CALIOPE_PROPRIEDADES, CALIOPE_ESTRUTURA))))

    return projeto.id_projeto, id_ret_final


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

        print(f"Concluído: projeto {resultado[0]}, retorno final {resultado[1]}")


if __name__ == "__main__":
    # Sem argumento: processa a fila. Com o ID: processa (ou retoma, se estiver com erro) só esse projeto.
    #   python orquestrador.py        |  python orquestrador.py 15
    if len(sys.argv) > 1:
        resultado = iniciar(int(sys.argv[1]))
        print(f"Concluído: projeto {resultado[0]}, retorno final {resultado[1]}")
    else:
        processar_fila()
