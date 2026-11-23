"""Rotina Fases: prevê as fases das composições geradas pelo VAE e grava em fases_composicao.

Método: envoltória convexa (diagrama de fases) do Materials Project, calculada por DFT a 0 K.
Para cada "Composição DAE-N", os elementos com pelo menos PE_MINIMO % em massa são convertidos para
fração atômica e a composição é decomposta nas fases estáveis do sistema químico (pymatgen).
O resultado é calculado: não considera temperatura, solução sólida nem cinética e precisa de validação empírica.
"""
######################### BIBLIOTECAS ###################################
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from database import FasesComposicao, engine
from Rotinas.composicoes_vae import composicoes_projeto
from Rotinas.registro_materiais import registrar_fonte
from Rotinas.retorno_cientistas import salvar_retorno

#########################################################################

NM_ROTINA = "Rotina Fases"
PE_MINIMO = 0.5     # % em massa mínimo para o elemento entrar no cálculo
MAX_ELEMENTOS = 8   # o Materials Project aceita até 9 elementos por sistema químico
URL_MP = "https://next-gen.materialsproject.org"
AVISO = ("Fases calculadas (DFT, Materials Project, 0 K): não consideram temperatura, solução sólida, "
         "cinética nem processamento e precisam de validação empírica.")


def elementos_calculo(composicao: dict[str, float]) -> tuple[list[str], list[str]]:
    """Elementos usados no cálculo (≥ PE_MINIMO %, no máximo MAX_ELEMENTOS, os de maior teor) e os deixados de fora."""
    ordenados = sorted(composicao, key=lambda e: -composicao[e])
    usados = [e for e in ordenados if composicao[e] >= PE_MINIMO][:MAX_ELEMENTOS]
    return usados, [e for e in ordenados if e not in usados]


def prever_fases(composicao: dict[str, float], cache: dict | None = None) -> dict:
    """Decompõe a composição (% em massa) nas fases estáveis do Materials Project.

    cache: diagramas já consultados (por sistema químico), para não repetir a consulta na mesma execução."""
    from pymatgen.core import Composition, Element

    from Rotinas import materials_project as mp

    usados, fora = elementos_calculo(composicao)
    if not usados:
        raise ValueError(f"Nenhum elemento com pelo menos {PE_MINIMO} % em massa: {composicao}")
    chave = tuple(sorted(usados))
    consulta = cache.get(chave) if cache is not None else None
    if consulta is None:
        consulta = mp.diagrama_fases(usados)
        if cache is not None:
            cache[chave] = consulta
    diagrama = consulta["diagrama"]
    alvo = Composition({e: composicao[e] / Element(e).atomic_mass for e in usados})
    decomposicao = diagrama.get_decomposition(alvo)

    massas = {entrada: fracao * entrada.composition.weight / entrada.composition.num_atoms
              for entrada, fracao in decomposicao.items()}
    massa_total = sum(massas.values())
    fases = []
    for entrada, fracao in sorted(decomposicao.items(), key=lambda item: -item[1]):
        id_mp = str(entrada.data.get("material_id") or "") or None
        simetria = consulta["simetria"].get(id_mp, {})
        fases.append({
            "nm_fase": entrada.composition.reduced_formula,
            "cd_material_mp": id_mp,
            "nm_grupo_espacial": simetria.get("grupo_espacial"),
            "nm_sistema_cristalino": simetria.get("sistema_cristalino"),
            "pe_fracao_atomica": round(100 * fracao, 4),
            "pe_fracao_massa": round(100 * massas[entrada] / massa_total, 4),
            "vl_energia_formacao": round(float(diagrama.get_form_energy_per_atom(entrada)), 6),
        })
    return {"sistema_quimico": consulta["sistema_quimico"], "versao_banco": consulta["versao_banco"],
            "elementos_usados": usados, "elementos_fora": fora, "fases": fases}


def _fonte_mp(versao: str) -> int:
    fonte = registrar_fonte(
        tp_fonte="Base de dados calculados", nm_titulo=f"Materials Project - diagramas de fases (banco {versao})",
        nm_instituicao_publicadora="Materials Project (Lawrence Berkeley National Laboratory)",
        cd_identificador_externo=f"materials_project {versao}", ds_versao=versao, dt_acesso=date.today().isoformat(),
        ds_observacoes="calculado (DFT, envoltória convexa a 0 K); licença CC BY 4.0",
    )
    return fonte["id_fonte"]


def _observacao(previsao: dict) -> str:
    texto = f"{AVISO} Elementos considerados: {', '.join(previsao['elementos_usados'])}."
    if previsao["elementos_fora"]:
        texto += (f" Fora do cálculo (abaixo de {PE_MINIMO} % em massa ou além de {MAX_ELEMENTOS} elementos): "
                  f"{', '.join(previsao['elementos_fora'])}.")
    return texto


def fases_projeto(id_projeto: int) -> dict[int, list[dict]]:
    """Fases gravadas para as composições DAE do projeto, por id_material."""
    ids = [c["id_material"] for c in composicoes_projeto(id_projeto)]
    if not ids:
        return {}
    with Session(engine) as session:
        linhas = session.execute(
            select(FasesComposicao).where(FasesComposicao.id_material.in_(ids))
            .order_by(FasesComposicao.id_material, FasesComposicao.pe_fracao_atomica.desc(), FasesComposicao.id_fase)
        ).scalars().all()
    saida: dict[int, list[dict]] = {}
    for f in linhas:
        saida.setdefault(f.id_material, []).append({
            "nm_fase": f.nm_fase, "cd_material_mp": f.cd_material_mp, "nm_grupo_espacial": f.nm_grupo_espacial,
            "nm_sistema_cristalino": f.nm_sistema_cristalino,
            "pe_fracao_atomica": float(f.pe_fracao_atomica) if f.pe_fracao_atomica is not None else None,
            "pe_fracao_massa": float(f.pe_fracao_massa) if f.pe_fracao_massa is not None else None,
            "vl_energia_formacao": float(f.vl_energia_formacao) if f.vl_energia_formacao is not None else None,
            "ds_sistema_quimico": f.ds_sistema_quimico, "ds_versao_base": f.ds_versao_base,
            "id_fonte": f.id_fonte, "ds_observacao": f.ds_observacao,
        })
    return saida


def _gravar(id_material: int, previsao: dict, id_fonte: int) -> None:
    observacao = _observacao(previsao)
    with Session(engine) as session:
        with session.begin():
            for fase in previsao["fases"]:
                session.add(FasesComposicao(
                    id_material=id_material, ds_sistema_quimico=previsao["sistema_quimico"],
                    ds_versao_base=previsao["versao_banco"], id_fonte=id_fonte, ds_observacao=observacao, **fase))


def _relatorio(composicoes: list[dict], fases: dict[int, list[dict]], reaproveitadas: bool) -> str:
    linhas = ["# Rotina Fases — Fases previstas", "", f"- Método: envoltória convexa do Materials Project ({URL_MP}).",
              f"- {AVISO}"]
    if reaproveitadas:
        linhas.append("- As fases já estavam gravadas para todas as composições e foram reaproveitadas.")
    for c in composicoes:
        lista = fases.get(c["id_material"], [])
        linhas += ["", f"## {c['nm_material']} (id_material {c['id_material']})", ""]
        if lista:
            linhas.append(f"Sistema químico: {lista[0]['ds_sistema_quimico']} · banco {lista[0]['ds_versao_base']}")
            linhas += ["", "| Fase | ID MP | Grupo espacial | % atômica | % em massa |", "|---|---|---|---|---|"]
            linhas += [f"| {f['nm_fase']} | {f['cd_material_mp'] or '—'} | {f['nm_grupo_espacial'] or '—'} | "
                       f"{f['pe_fracao_atomica']:.2f} | {f['pe_fracao_massa']:.2f} |" for f in lista]
    return "\n".join(linhas)


def executar_rotina_fases(id_projeto: int, _prompt: str = "") -> int:
    """Calcula e grava as fases das composições DAE do projeto que ainda não têm fases e salva o resumo."""
    composicoes = composicoes_projeto(id_projeto)
    if not composicoes:
        raise RuntimeError(f"O projeto {id_projeto} não tem composições geradas pelo VAE para calcular fases.")
    existentes = fases_projeto(id_projeto)
    pendentes = [c for c in composicoes if c["id_material"] not in existentes]
    fontes: dict[str, int] = {}
    diagramas: dict = {}
    for c in pendentes:
        previsao = prever_fases(c["composicao"], diagramas)
        versao = previsao["versao_banco"]
        if versao not in fontes:
            fontes[versao] = _fonte_mp(versao)
        _gravar(c["id_material"], previsao, fontes[versao])
    return salvar_retorno(id_projeto, NM_ROTINA, _relatorio(composicoes, fases_projeto(id_projeto), not pendentes))
