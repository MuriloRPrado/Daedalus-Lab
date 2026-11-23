######################### BIBLIOTECAS ###################################
from Rotinas import comparacao_composicoes as cc
from Rotinas.dados_prompt import (dados_projeto, elementos_pesquisados, em_json, requisitos_projeto,
                                   restricoes_projeto)

#########################################################################


def gerar_prompt_caliope_comparacao(id_projeto: int) -> str:
    """Só as composições do VAE sem liga próxima na base, com a liga mais próxima da base como pista."""
    pendentes = [
        {"nm_composicao": a["nm_material"], "composicao_pct_massa": a["composicao"],
         "liga_mais_proxima_base": {k: a["ligas_proximas_base"][0][k]
                                    for k in ("nome", "familia", "referencia", "distancia_pp", "composicao")}}
        for a in cc.sem_correspondencia(cc.analisar_base(id_projeto))
    ]
    return "\n\n".join([
        "Verifique se as composições abaixo, geradas pelo modelo VAE, existem em materiais metálicos reais. "
        f"Nenhuma delas tem liga a até {cc.LIMITE_PROXIMO_PP:g} pp na base de ligas do VAE. "
        "Use suas instruções permanentes.",
        f"ID do projeto: {id_projeto}",
        "## Dados do Projeto", em_json(dados_projeto(id_projeto)),
        "## Composições a pesquisar", em_json(pendentes),
    ])


def gerar_prompt_caliope_relatorio(id_projeto: int, consolidado: list[dict], fases: dict[int, list[dict]]) -> str:
    """Dados das tabelas do projeto usados pela Calíope - Relatório para escrever a Introdução e a Conclusão."""
    composicoes = [
        {"nm_composicao": c["nm_material"], "composicao_pct_massa": c["composicao"],
         "fases_previstas_calculadas": [
             {k: f[k] for k in ("nm_fase", "cd_material_mp", "nm_grupo_espacial", "pe_fracao_atomica",
                                "pe_fracao_massa")} for f in fases.get(c["id_material"], [])],
         "sistema_quimico_fases": (fases.get(c["id_material"]) or [{}])[0].get("ds_sistema_quimico"),
         "resultado_comparacao": c["resultado"],
         "materiais_reais_iguais": [{"material": m["material"], "origem": m["origem"]} for m in c["iguais"]],
         "distancia_liga_mais_proxima_base_pp": c["distancia_base_pp"]}
        for c in consolidado
    ]
    return "\n\n".join([
        "Escreva a Introdução e a Conclusão do relatório final do projeto abaixo. Use suas instruções permanentes "
        "e somente os dados deste prompt.",
        f"ID do projeto: {id_projeto}",
        "## Projeto (tabela projeto)", em_json(dados_projeto(id_projeto)),
        "## Requisitos de propriedades (tabela projeto_requisitos)", em_json(requisitos_projeto(id_projeto)),
        "## Restrições químicas (tabela elemento_proj_restricao)", em_json(restricoes_projeto(id_projeto)),
        "## Elementos levantados pela Atena (tabela pesquisa_elementos)", em_json(elementos_pesquisados(id_projeto)),
        "## Composições geradas pelo VAE, fases previstas e comparação "
        "(tabelas materiais, composicao_material e fases_composicao)", em_json(composicoes),
        f"Critério de material igual: todos os elementos a até {cc._pp(cc.TOLERANCIA_PP)} pp da liga real ou dentro "
        "das faixas da fonte. \"Próximo\" e \"Não existe\" não entram na seção Comparação.",
    ])
