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
TOLERANCIA_PP = 0.01  # precisão dos percentuais gerados (2 casas)
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
    observacoes_gerais: str = ""


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
        proximas = gerador.ligas_mais_proximas(c["composicao"], 3)
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


def _nome_base(liga: dict) -> str:
    nome = f"{liga['nome']} " if liga["nome"] else ""
    return f"{nome}[{liga['familia']}, fonte {liga['fonte']}; {liga['referencia']}]".strip()


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


def montar_relatorio(id_projeto: int, analise: list[dict], saida: SaidaComparacao | None) -> str:
    """Relatório final em Markdown: resumo, detalhe por composição, critérios e limitações."""
    web = {_sigla(c.nm_composicao): c for c in (saida.comparacoes if saida else [])}
    modelo = gerador.descricao_modelo()
    resumo, detalhes, fontes = [], [], []
    for a in analise:
        comp, nome = a["composicao"], a["nm_material"]
        texto_comp = ", ".join(f"{e} {v:.2f}" for e, v in comp.items())
        detalhes += ["", f"## {nome}", "", f"**Composição gerada (% em massa):** {texto_comp}", ""]
        if a["resultado_base"] is not None:
            liga = a["ligas_proximas_base"][0]
            resultado, distancia, origem = a["resultado_base"], f"{liga['distancia_pp']:.2f} pp", "Base do VAE"
            material = _nome_base(liga)
            detalhes += [f"**Resultado:** {resultado}", f"**Material comparado:** {material}",
                         f"**Distância:** {distancia} (massa que precisa mudar de elemento)", ""]
            detalhes += _tabela_base(comp, liga)
            outras = a["ligas_proximas_base"][1:]
            if outras:
                detalhes += ["", "Outras ligas próximas na base:"]
                detalhes += [f"- {_nome_base(o)}: {o['distancia_pp']:.2f} pp" for o in outras]
        else:
            c = web.get(_sigla(nome))
            melhor_base = a["ligas_proximas_base"][0]
            nota_base = f"Na base do VAE, a liga mais próxima está a {melhor_base['distancia_pp']:.2f} pp ({_nome_base(melhor_base)})."
            if c is None or not c.nm_material or not c.composicao_material:
                resultado, material, distancia, origem = NAO_EXISTE, "—", "—", "Base do VAE + web" if saida else "Base do VAE"
                detalhes += [f"**Resultado:** {resultado}", nota_base,
                             "Na pesquisa web, nenhum material real com composição documentada foi encontrado."
                             if saida else "A pesquisa web não foi executada."]
                if c is not None and c.ds_observacao:
                    detalhes.append(f"Observação da Calíope: {c.ds_observacao}")
            else:
                desvios = desvio_faixas(comp, c.composicao_material)
                total = round(sum(desvios.values()), 2)
                resultado = EXISTE if total <= TOLERANCIA_PP else _resultado(total, False)
                material, distancia, origem = c.nm_material, f"{total:.2f} pp fora das faixas", "Web"
                fonte = " — ".join(t for t in (c.nm_titulo_fonte, c.nm_url_fonte) if t) or "fonte não informada"
                fontes.append(f"- {c.nm_material}: {fonte}" + (f" (id_fonte {c.id_fonte})" if c.id_fonte else ""))
                detalhes += [f"**Resultado:** {resultado}", f"**Material comparado:** {material}", f"**Fonte:** {fonte}",
                             f"**Distância:** {distancia}", ""]
                detalhes += _tabela_web(comp, c.composicao_material, desvios)
                detalhes += ["", nota_base]
                if c.ds_observacao:
                    detalhes.append(f"Observação da Calíope: {c.ds_observacao}")
        resumo.append(f"| {nome} | {resultado} | {material} | {distancia} | {origem} |")

    partes = [
        "# Calíope — Comparação das composições geradas com materiais reais", "",
        f"Projeto {id_projeto} · gerado em {datetime.now():%d/%m/%Y %H:%M} · modelo {modelo['arquivo']} "
        f"(época {modelo['epoca']})", "",
        "## Resumo", "", "| Composição | Resultado | Material comparado | Distância | Origem |", "|---|---|---|---|---|",
        *resumo, *detalhes, "",
        "## Critérios", "",
        f"- **Existe:** todos os elementos coincidem com uma liga real da base (diferença ≤ {TOLERANCIA_PP} pp) "
        "ou ficam dentro das faixas documentadas do material encontrado na web.",
        f"- **Próximo:** até {LIMITE_PROXIMO_PP:g} pp. Na base, a distância é a massa que precisa mudar de elemento "
        "(metade da soma das diferenças); na web, é a soma do quanto cada elemento fica fora da faixa.",
        f"- **Não existe:** acima de {LIMITE_PROXIMO_PP:g} pp na base e sem material documentado na web dentro do limite.",
        "- A base do VAE é consultada primeiro; a web só é pesquisada para as composições sem correspondência na base.",
    ]
    if fontes:
        partes += ["", "## Fontes (web)", "", *fontes]
    if saida and saida.observacoes_gerais.strip():
        partes += ["", "## Observações da Calíope", "", saida.observacoes_gerais.strip()]
    partes += ["", "## Limitações", "",
               "- As composições são candidatas estatísticas do VAE. Proximidade de composição não comprova "
               "estabilidade, fabricabilidade nem propriedades.",
               "- A base do VAE reúne composições medidas ou normatizadas publicadas (fontes em VAE/FONTES.md); "
               "o nome da liga é o da fonte original e pode ser só um rótulo de amostra."]
    return "\n".join(partes)
