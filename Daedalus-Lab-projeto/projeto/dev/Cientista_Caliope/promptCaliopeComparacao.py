######################### BIBLIOTECAS ###################################
from Rotinas import comparacao_composicoes as cc
from Rotinas.dados_prompt import dados_projeto, em_json

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
