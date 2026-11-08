########################## BIBLIOTECAS ###################################
#from database import engine, Projeto
#from Cientista_Prometeu.agentePrometeu import executar_pesquisa
#from Cientista_Prometeu.promptPrometeu import gerar_prompt
#from sqlalchemy import select, update, func
#from sqlalchemy.orm import Session
##########################################################################
#
#def rotinaPrometeuSME():
#    with Session(engine) as session:                                        # Consulta a tabela de projetos para identificar se há pesquisas para ser realizadas
#            consulta = select(
#                Projeto.id_projeto,
#                Projeto.nm_responsavel_tecnico,
#                Projeto.nm_tp_sigla,
#                Projeto.ds_aplicacao,
#                Projeto.ds_ambiente,
#                Projeto.nm_componente,
#                Projeto.nm_material_ref,
#                Projeto.ds_rota_fabricacao,
#                Projeto.ds_disponibilidade,
#                Projeto.ds_custo,
#                Projeto.cd_status,
#                Projeto.dt_atualizacao
#            ).where(Projeto.nm_tp_sigla == 'SME', Projeto.cd_status == 10).order_by(Projeto.id_projeto.asc()).limit(1)
#            resultado = session.execute(consulta).one_or_none()             # Registro com o tipo "Selação de Materiais Existentes", status "Aguardando", ordena os registros do mais antigo para o mas recente e retorna apenas uma linha
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
#pesquisaPrometeu = rotinaPrometeuSME()
#
#if pesquisaPrometeu is not None:
#    prompt = gerar_prompt(pesquisaPrometeu.id_projeto)
#    print("Pesquisa Iniciada")
#    atualizar_status(pesquisaPrometeu.id_projeto, 21)
#    print("Pesquisa em andamento pelo agente Prometeu, aguarde...")
#    executar_pesquisa(pesquisaPrometeu.id_projeto, prompt)
#    atualizar_status(pesquisaPrometeu.id_projeto, 23)
#    print("Pesquisa Finalizada")
#else:
#    print("Não há pesquisa para ser realizada")