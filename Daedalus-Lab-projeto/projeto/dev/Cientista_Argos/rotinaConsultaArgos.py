########################## BIBLIOTECAS ###################################
#from database import engine, Projeto, RetornoCientista
#from Cientista_Argos.agenteArgos import executar_pesquisa
#from Cientista_Argos.promptArgos import gerar_prompt
#from sqlalchemy import select, update, func
#from sqlalchemy.orm import Session
##########################################################################
#
#def rotinaArgosSME():
#    with Session(engine) as session:                                        # Consulta a tabela de projetos para identificar se há pesquisas para ser realizadas
#        consulta = select(
#            Projeto.id_projeto,
#            Projeto.nm_tp_sigla,
#            Projeto.cd_status
#        ).where(Projeto.nm_tp_sigla == 'SME', Projeto.cd_status == 23).order_by(Projeto.id_projeto.asc()).limit(1)
#        resultado = session.execute(consulta).one_or_none()             # Registro com o tipo "Selação de Materiais Existentes", status "Aguardando", ordena os registros do mais antigo para o mas recente e retorna apenas uma linha
#
#    return resultado
#
#def atualizar_status(id_projeto: int, novo_status: int):                # Função para atualizar o status do registro para "Pesquisa Iniciada" e inserir a data de atualização
#    with Session(engine) as session:
#        atualizacao = (
#            update(Projeto)
#            .where(Projeto.id_projeto == id_projeto)
#            .values(
#                cd_status=novo_status,
#                dt_atualizacao=func.now()
#            )
#        )
#        session.execute(atualizacao)
#        session.commit()
#
#def consultaRetorno(id_projeto: int, nm_agente: str):
#    with Session(engine) as sessionR:
#        consultaRetorno = select(
#            RetornoCientista.id_ret_cientistas,
#            RetornoCientista.id_projeto,
#            RetornoCientista.nm_agente
#        ).where(RetornoCientista.id_projeto == id_projeto, RetornoCientista.nm_agente == nm_agente).order_by(RetornoCientista.id_projeto.asc()).limit(1)
#        retorno = sessionR.execute(consultaRetorno).one_or_none()
#
#    return retorno
#
#pesquisa = rotinaArgosSME()
#
#if pesquisa is not None:
#
#    consulta = consultaRetorno(pesquisa.id_projeto, "Prometeu")
#    if consulta is not None:
#        prompt = gerar_prompt(pesquisa.id_projeto, consulta.id_ret_cientistas)
#        atualizar_status(pesquisa.id_projeto, 21)
#        print("Pesquisa Iniciada")
#        print("Pesquisa em andamento pelo agente Argos, aguarde...")
#        executar_pesquisa(pesquisa.id_projeto, prompt)
#        atualizar_status(pesquisa.id_projeto, 24)
#        print("Pesquisa Finalizada")
#    else:
#        print(f"Não existe pesquisa realizada para o IDPesquisa{consulta.id_ret_cientistas} e agente{consulta.nm_agente} informado.")
#
#else:
#     print("Não há projetos na fila")