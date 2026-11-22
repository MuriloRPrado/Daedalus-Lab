"""Rotina VAE: lê os elementos gravados pela Atena, gera 3 composições e grava em materiais/composicao_material.

Cada composição vira um material "Composição DAE-N" (N cresce a cada composição gravada na tabela, em
todos os projetos) com um registro por elemento em composicao_material (valor único em pe_max).
"""
######################### BIBLIOTECAS ###################################
import re

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from database import ComposicaoMaterial, Materiais, PesquisaElementos, engine
from Rotinas.retorno_cientistas import salvar_retorno
from VAE import gerador

#########################################################################

NM_ROTINA = "Rotina VAE"
PREFIXO = "Composição DAE-"
BASE_COMP = "% em massa"
QUANTIDADE = 3
POUCO_REPRESENTADO = 10
_PADRAO_NOME = re.compile(rf"^{re.escape(PREFIXO)}(\d+)$")
_CHAVE_NUMERACAO = 7_201_626  # trava global (pg_advisory_xact_lock) da numeração DAE


def _sigla(valor: str | None) -> str:
    valor = (valor or "").strip()
    return valor[:1].upper() + valor[1:].lower()


def organizar_elementos(id_projeto: int) -> dict:
    """Elementos da Atena (pesquisa_elementos) sem repetição, separados entre aceitos e desconhecidos pelo VAE."""
    with Session(engine) as session:
        siglas = session.execute(
            select(PesquisaElementos.nm_sigla_elemento)
            .where(PesquisaElementos.id_projeto == id_projeto)
            .order_by(PesquisaElementos.id_elemento)
        ).scalars().all()
    vocab = gerador.elementos_modelo()
    elementos = list(dict.fromkeys(s for s in map(_sigla, siglas) if s))
    return {
        "elementos_atena": elementos,
        "aceitos": [e for e in elementos if e in vocab],
        "ignorados": [e for e in elementos if e not in vocab],
    }


def composicoes_projeto(id_projeto: int) -> list[dict]:
    """Composições DAE gravadas no projeto, com os percentuais de composicao_material."""
    with Session(engine) as session:
        materiais = session.execute(
            select(Materiais).where(Materiais.id_projeto == id_projeto, Materiais.nm_material.like(f"{PREFIXO}%"))
            .order_by(Materiais.id_material)
        ).scalars().all()
        saida = []
        for m in materiais:
            if not _PADRAO_NOME.match(m.nm_material or ""):
                continue
            linhas = session.execute(
                select(ComposicaoMaterial).where(ComposicaoMaterial.id_material == m.id_material)
                .order_by(ComposicaoMaterial.pe_max.desc(), ComposicaoMaterial.id_composicao)
            ).scalars().all()
            saida.append({
                "id_material": m.id_material,
                "nm_material": m.nm_material,
                "composicao": {c.nm_sigla: float(c.pe_max) for c in linhas if c.pe_max is not None},
            })
    return saida


def _proximo_numero(session: Session) -> int:
    session.execute(text("SELECT pg_advisory_xact_lock(:chave)"), {"chave": _CHAVE_NUMERACAO})
    nomes = session.execute(select(Materiais.nm_material).where(Materiais.nm_material.like(f"{PREFIXO}%"))).scalars()
    return max((int(m.group(1)) for m in map(_PADRAO_NOME.match, nomes) if m), default=0) + 1


def _gravar(id_projeto: int, composicoes: list[dict[str, float]], elementos: list[str], modelo: dict) -> list[dict]:
    """Grava as composições numa única transação (ou tudo, ou nada)."""
    gravadas = []
    with Session(engine) as session:
        with session.begin():
            numero = _proximo_numero(session)
            for comp in composicoes:
                nao_usados = [e for e in elementos if e not in comp]
                observacao = (
                    f"Composição candidata gerada pelo modelo VAE ({modelo['arquivo']}, época {modelo['epoca']}) "
                    f"a partir dos elementos pesquisados pela Atena: {', '.join(elementos)}. "
                    "Não é um material real confirmado; estabilidade, fabricabilidade e propriedades não foram validadas."
                )
                if nao_usados:
                    observacao += f" Elementos informados que o modelo deixou em 0 %: {', '.join(nao_usados)}."
                material = Materiais(id_projeto=id_projeto, nm_material=f"{PREFIXO}{numero}", ds_observacao=observacao)
                session.add(material)
                session.flush()
                for sigla, valor in comp.items():
                    session.add(ComposicaoMaterial(
                        id_material=material.id_material, nm_base_comp=BASE_COMP, pe_min=None, pe_max=valor,
                        fl_elem_balanco=False, ds_observacao="Valor único gerado pelo modelo VAE", nm_sigla=sigla,
                    ))
                gravadas.append({"id_material": material.id_material, "nm_material": material.nm_material,
                                 "composicao": comp})
                numero += 1
    return gravadas


def _relatorio(org: dict, composicoes: list[dict], modelo: dict, reaproveitadas: bool) -> str:
    linhas = ["# Rotina VAE — Composições geradas", "",
              f"- Modelo: {modelo['arquivo']} ({modelo['parametros']} parâmetros, época {modelo['epoca']})",
              f"- Elementos da Atena: {', '.join(org['elementos_atena']) or 'nenhum'}",
              f"- Elementos usados no VAE: {', '.join(org['aceitos']) or 'nenhum'}"]
    if org["ignorados"]:
        linhas.append(f"- Ignorados (fora da base de treino do VAE): {', '.join(org['ignorados'])}")
    poucos = [e for e in org["aceitos"] if gerador.ocorrencias(e) < POUCO_REPRESENTADO]
    if poucos:
        linhas.append(f"- Pouco representados na base de treino (< {POUCO_REPRESENTADO} ligas): {', '.join(poucos)}")
    if reaproveitadas:
        linhas.append("- As composições já estavam gravadas para o projeto e foram reaproveitadas.")
    for c in composicoes:
        linhas += ["", f"## {c['nm_material']} (id_material {c['id_material']})", "", "| Elemento | % em massa |", "|---|---|"]
        linhas += [f"| {e} | {v:.2f} |" for e, v in c["composicao"].items()]
        linhas.append(f"| **Soma** | **{sum(c['composicao'].values()):.2f}** |")
    return "\n".join(linhas)


def executar_rotina_vae(id_projeto: int, _prompt: str = "") -> int:
    """Organiza os elementos da Atena, gera e grava as composições e salva o resumo em retorno_cientistas."""
    org = organizar_elementos(id_projeto)
    modelo = gerador.descricao_modelo()
    existentes = composicoes_projeto(id_projeto)
    if existentes:
        return salvar_retorno(id_projeto, NM_ROTINA, _relatorio(org, existentes, modelo, True))
    if not org["aceitos"]:
        raise RuntimeError(
            f"Nenhum elemento da Atena pode ser usado pelo VAE (projeto {id_projeto}). "
            f"Registrados: {org['elementos_atena'] or 'nenhum'}; fora da base de treino: {org['ignorados'] or 'nenhum'}.")
    geradas = gerador.gerar_composicoes(org["aceitos"], QUANTIDADE)
    for comp in geradas:
        if abs(sum(comp.values()) - 100) > 1e-6 or not set(comp) <= set(org["aceitos"]):
            raise RuntimeError(f"Composição gerada inválida: {comp}")
    gravadas = _gravar(id_projeto, geradas, org["aceitos"], modelo)
    return salvar_retorno(id_projeto, NM_ROTINA, _relatorio(org, gravadas, modelo, False))
