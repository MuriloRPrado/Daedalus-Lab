"""Calíope - Comparação: verifica se as composições geradas pelo VAE existem em materiais metálicos reais.

1. Base de ligas reais do VAE (VAE/dados/base_composicoes.csv), sem custo.
2. Só para as composições sem liga a até LIMITE_PROXIMO_PP na base: pesquisa web (Firecrawl etc.) pela agente.
A classificação (existe / próximo / não existe) é calculada aqui, a partir das composições; a agente só
fornece o material encontrado na web, a composição documentada e a fonte.
"""
######################### BIBLIOTECAS ###################################
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from Rotinas.composicoes_vae import _sigla, composicoes_projeto
from VAE import gerador

#########################################################################

LIMITE_PROXIMO_PP = 10.0
TOLERANCIA_PP = 0.5  # "igual": todos os elementos a até 0,5 pp do material real
EXISTE, PROXIMO, NAO_EXISTE = "Existe", "Próximo", "Não existe"


class ElementoReferencia(BaseModel):
    nm_sigla: str = Field(description='Símbolo do elemento (ex.: "Cr").')
    tp_valor: Literal["faixa", "maximo", "minimo", "nominal", "balanco"] = Field(
        description="Como a fonte informa o elemento: faixa (pe_min a pe_max), maximo, minimo, nominal ou balanco.")
    pe_min: float | None = Field(None, description="% em massa mínimo (faixa ou minimo).")
    pe_max: float | None = Field(None, description="% em massa máximo (faixa ou maximo) ou o valor nominal.")


class ComparacaoWeb(BaseModel):
    nm_composicao: str = Field(description='Nome da composição gerada (ex.: "Composição DAE-4").')
    nm_material: str | None = Field(None, description="Material real mais parecido encontrado; null se não encontrou.")
    composicao_material: list[ElementoReferencia] = Field(
        default_factory=list, description="Composição do material como está na fonte lida (todos os elementos informados).")
    nm_titulo_fonte: str | None = None
    nm_url_fonte: str | None = None
    id_fonte: int | None = Field(None, description="id_fonte devolvido por registrar_fonte.")
    ds_observacao: str = Field("", description="Buscas feitas e, se não encontrou, o motivo.")


class SaidaComparacao(BaseModel):
    comparacoes: list[ComparacaoWeb]


class TextosRelatorio(BaseModel):
    introducao: str = Field(description="Texto da seção Introdução, sem título, em Markdown simples.")
    conclusao: str = Field(description="Texto da seção Conclusão, sem título, em Markdown simples.")


def _resultado(distancia: float, existe: bool) -> str:
    if existe:
        return EXISTE
    return PROXIMO if distancia <= LIMITE_PROXIMO_PP else NAO_EXISTE


def analisar_base(id_projeto: int) -> list[dict]:
    """Para cada composição DAE do projeto, as 3 ligas mais próximas da base e o resultado pela base."""
    composicoes = composicoes_projeto(id_projeto)
    if not composicoes:
        raise RuntimeError(f"O projeto {id_projeto} não tem composições geradas pelo VAE para comparar.")
    analise = []
    for c in composicoes:
        proximas = gerador.ligas_mais_proximas(c["composicao"], 3, TOLERANCIA_PP)
        melhor = proximas[0]
        resultado = _resultado(melhor["distancia_pp"], melhor["maior_diferenca_pp"] <= TOLERANCIA_PP)
        analise.append({**c, "ligas_proximas_base": proximas,
                        "resultado_base": resultado if resultado != NAO_EXISTE else None})
    return analise


def sem_correspondencia(analise: list[dict]) -> list[dict]:
    return [a for a in analise if a["resultado_base"] is None]


def _faixa(e: ElementoReferencia) -> tuple[float, float]:
    if e.tp_valor == "balanco":
        return 0.0, 100.0
    if e.tp_valor == "maximo":
        return 0.0, e.pe_max if e.pe_max is not None else 100.0
    if e.tp_valor == "minimo":
        return e.pe_min if e.pe_min is not None else 0.0, 100.0
    if e.tp_valor == "nominal":
        v = e.pe_max if e.pe_max is not None else e.pe_min
        return (v, v) if v is not None else (0.0, 100.0)
    return e.pe_min if e.pe_min is not None else 0.0, e.pe_max if e.pe_max is not None else 100.0


def desvio_faixas(composicao: dict[str, float], referencia: list[ElementoReferencia]) -> dict[str, float]:
    """Quanto (pp) cada elemento fica fora da faixa do material real; elemento ausente no material = faixa 0."""
    faixas = {_sigla(e.nm_sigla): _faixa(e) for e in referencia}
    desvios = {}
    for sigla in dict.fromkeys([*composicao, *faixas]):
        valor = composicao.get(sigla, 0.0)
        lo, hi = faixas.get(sigla, (0.0, 0.0))
        desvios[sigla] = round(max(lo - valor, valor - hi, 0.0), 4)
    return desvios


def _texto_faixa(e: ElementoReferencia | None) -> str:
    if e is None:
        return "ausente"
    return {
        "balanco": "balanço",
        "maximo": f"≤ {e.pe_max:g}" if e.pe_max is not None else "máx. não informado",
        "minimo": f"≥ {e.pe_min:g}" if e.pe_min is not None else "mín. não informado",
        "nominal": f"{(e.pe_max if e.pe_max is not None else e.pe_min):g} (nominal)" if (e.pe_max, e.pe_min) != (None, None) else "—",
    }.get(e.tp_valor, f"{e.pe_min if e.pe_min is not None else 0:g} – {e.pe_max if e.pe_max is not None else 100:g}")


def _referencia_base(liga: dict) -> str:
    ref = liga["referencia"].strip().removeprefix("doi:").strip()
    if ref.startswith("10.") and " " not in ref:
        ref = f"https://doi.org/{ref}"
    return f"base de ligas do VAE, conjunto {liga['fonte']} (VAE/FONTES.md); referência original: {ref or 'não informada'}"


def _tabela_base(comp: dict[str, float], liga: dict) -> list[str]:
    linhas = ["| Elemento | Gerada (%) | Material real (%) | Diferença (pp) |", "|---|---|---|---|"]
    for e in dict.fromkeys([*comp, *liga["composicao"]]):
        g, r = comp.get(e, 0.0), liga["composicao"].get(e, 0.0)
        linhas.append(f"| {e} | {g:.2f} | {r:.4g} | {g - r:+.2f} |")
    return linhas


def _tabela_web(comp: dict[str, float], ref: list[ElementoReferencia], desvios: dict[str, float]) -> list[str]:
    por_sigla = {_sigla(e.nm_sigla): e for e in ref}
    linhas = ["| Elemento | Gerada (%) | Material real (%) | Fora da faixa (pp) |", "|---|---|---|---|"]
    for e in desvios:
        linhas.append(f"| {e} | {comp.get(e, 0.0):.2f} | {_texto_faixa(por_sigla.get(e))} | {desvios[e]:.2f} |")
    return linhas


def consolidar(analise: list[dict], saida: SaidaComparacao | None) -> list[dict]:
    """Por composição: resultado (Existe/Próximo/Não existe) e os materiais reais iguais (até TOLERANCIA_PP)."""
    web = {_sigla(c.nm_composicao): c for c in (saida.comparacoes if saida else [])}
    consolidado = []
    for a in analise:
        comp, iguais, observacao_web = a["composicao"], [], None
        if a["resultado_base"] is not None:
            resultado = a["resultado_base"]
            for liga in a["ligas_proximas_base"]:
                if liga["maior_diferenca_pp"] <= TOLERANCIA_PP:
                    iguais.append({"material": liga["nome"] or liga["familia"],
                                   "familia": liga["familia"], "origem": "Base de ligas do VAE",
                                   "fonte": _referencia_base(liga), "tabela": _tabela_base(comp, liga)})
        else:
            c = web.get(_sigla(a["nm_material"]))
            resultado = NAO_EXISTE
            observacao_web = (c.ds_observacao.strip() or None) if c is not None else (
                "Pesquisa web não executada ou sem retorno para esta composição.")
            if c is not None and c.nm_material and c.composicao_material:
                desvios = desvio_faixas(comp, c.composicao_material)
                total = round(sum(desvios.values()), 2)
                resultado = EXISTE if max(desvios.values(), default=0.0) <= TOLERANCIA_PP else _resultado(total, False)
                if resultado == EXISTE:
                    fonte = " — ".join(t for t in (c.nm_titulo_fonte, c.nm_url_fonte) if t) or "fonte não informada"
                    iguais.append({"material": c.nm_material, "familia": None, "origem": "Pesquisa web",
                                   "fonte": fonte, "tabela": _tabela_web(comp, c.composicao_material, desvios)})
        consolidado.append({**a, "resultado": resultado, "iguais": iguais, "observacao_pesquisa_web": observacao_web,
                            "distancia_base_pp": a["ligas_proximas_base"][0]["distancia_pp"]})
    return consolidado


def _pp(valor: float) -> str:
    return f"{valor:g}".replace(".", ",")


def _tabela_composicao(comp: dict[str, float]) -> list[str]:
    return ["| Elemento | % em massa |", "|---|---|", *[f"| {e} | {v:.2f} |" for e, v in comp.items()]]


def _secao_fases(fases: list[dict]) -> list[str]:
    if not fases:
        return ["**Fases previstas (calculadas):** não calculadas para esta composição."]
    f0 = fases[0]
    linhas = [f"**Fases previstas (calculadas)** — sistema {f0['ds_sistema_quimico']}, Materials Project "
              f"(banco {f0['ds_versao_base']}), envoltória convexa a 0 K:", "",
              "| Fase | ID Materials Project | Grupo espacial | Sistema cristalino | % atômica | % em massa |",
              "|---|---|---|---|---|---|"]
    for f in fases:
        id_mp = f["cd_material_mp"]
        link = f"[{id_mp}](https://next-gen.materialsproject.org/materials/{id_mp})" if id_mp else "—"
        linhas.append(f"| {f['nm_fase']} | {link} | {f['nm_grupo_espacial'] or '—'} | "
                      f"{f['nm_sistema_cristalino'] or '—'} | {f['pe_fracao_atomica']:.2f} | {f['pe_fracao_massa']:.2f} |")
    if f0.get("ds_observacao"):
        linhas += ["", f"_{f0['ds_observacao']}_"]
    return linhas


def montar_relatorio(id_projeto: int, consolidado: list[dict], fases: dict[int, list[dict]],
                     textos: TextosRelatorio) -> str:
    """Relatório final: Título, Introdução, Resultados, Comparação (só se houver material igual) e Conclusão."""
    modelo = gerador.descricao_modelo()
    partes = ["# Geração de Composições Químicas para Materiais Metálicos", "",
              f"_Projeto {id_projeto} · gerado em {datetime.now():%d/%m/%Y %H:%M}_", "",
              "## Introdução", "", textos.introducao.strip(), "",
              "## Resultados", "",
              "> As composições abaixo foram geradas por um modelo estatístico (VAE) e as fases foram **calculadas** "
              "(DFT, Materials Project, 0 K). São candidatas teóricas: composição e fases **precisam de validação "
              "empírica** (fabricação, caracterização microestrutural e ensaios)."]
    for c in consolidado:
        partes += ["", f"### {c['nm_material']}", "", "**Composição química gerada:**", "",
                   *_tabela_composicao(c["composicao"]), "", *_secao_fases(fases.get(c["id_material"], []))]
    partes += ["", "Fontes:",
               f"- Composições: modelo VAE do Daedalus Lab ({modelo['arquivo']}, época {modelo['epoca']}), treinado "
               "com composições publicadas de ligas reais (conjuntos e DOIs em VAE/FONTES.md).",
               "- Fases: Materials Project (https://next-gen.materialsproject.org), dados sob licença CC BY 4.0; "
               "cálculo da envoltória convexa com pymatgen."]

    com_iguais = [c for c in consolidado if c["iguais"]]
    if com_iguais:
        partes += ["", "## Comparação", "",
                   f"Materiais reais documentados com a mesma composição (todos os elementos a até {_pp(TOLERANCIA_PP)} pp "
                   "ou dentro das faixas da fonte):"]
        for c in com_iguais:
            for m in c["iguais"]:
                titulo = m["material"] + (f" ({m['familia']})" if m["familia"] and m["familia"] != m["material"] else "")
                partes += ["", f"### {c['nm_material']} — {titulo}", "", f"- Origem: {m['origem']}",
                           f"- Fonte: {m['fonte']}", "", *m["tabela"]]

    partes += ["", "## Conclusão", "", textos.conclusao.strip()]
    return "\n".join(partes)
