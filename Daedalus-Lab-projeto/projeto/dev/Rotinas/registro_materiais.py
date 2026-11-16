"""Gravação dos materiais encontrados e das suas composições químicas no banco do projeto.

Funções: registrar_fonte, registrar_material, registrar_composicao, listar_materiais_projeto,
registrar_elemento e listar_elementos_projeto.

Cada função confere se o registro já existe antes de inserir (o mesmo material ou elemento não é
gravado duas vezes no mesmo projeto) e vincula as fontes informadas nas tabelas
ma_fontes, composicao_fonte e elementos_fontes.
"""
######################### BIBLIOTECAS ###################################
import re
from datetime import date

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from database import (
    ComposicaoFonte, ComposicaoMaterial, ElementosFontes, Fontes, Materiais, MateriaisFonte, PesquisaElementos, engine,
)
from Rotinas.cache_fontes import contexto_atual
from Rotinas.fontes_firecrawl import normalizar_url
#########################################################################

def _texto(valor: str | None, nome: str, tamanho: int | None = None, obrigatorio: bool = False) -> str | None:
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        if obrigatorio:
            raise ValueError(f"{nome} deve ser um texto não vazio.")
        return None
    if not isinstance(valor, str):
        raise ValueError(f"{nome} deve ser texto.")
    valor = valor.strip()
    if tamanho is not None and len(valor) > tamanho:
        raise ValueError(f"{nome} deve ter até {tamanho} caracteres (recebido: {len(valor)}).")
    return valor


def _chave(valor: str | None) -> str:
    """Normaliza um nome para comparação: minúsculas e espaços simples."""
    return re.sub(r"\s+", " ", (valor or "").strip().lower())


def _normalizar_doi(doi: str) -> str:
    doi = doi.strip().lower()
    return re.sub(r"^(https?://(dx\.)?doi\.org/|doi:)", "", doi)


def _validar_projeto_do_agente(id_projeto: int) -> None:
    """Impede que o agente em execução leia ou grave dados de outro projeto."""
    id_projeto_agente, _ = contexto_atual()
    if id_projeto_agente is not None and id_projeto != id_projeto_agente:
        raise ValueError(f"Esta execução pertence ao projeto {id_projeto_agente}; use id_projeto={id_projeto_agente}.")


def _bloquear_projeto(session: Session, id_projeto: int) -> None:
    """Evita que duas gravações simultâneas do mesmo projeto criem registros repetidos."""
    _validar_projeto_do_agente(id_projeto)
    session.execute(text("SELECT pg_advisory_xact_lock(:chave)"), {"chave": id_projeto})


def _material_do_projeto(session: Session, id_projeto: int, id_material: int) -> Materiais:
    material = session.get(Materiais, id_material)
    if material is None or material.id_projeto != id_projeto:
        raise ValueError(f"O material {id_material} não existe no projeto {id_projeto}.")
    return material


def _vincular_fontes(session: Session, modelo, ids_fontes: list[int] | None, **campos) -> list[int]:
    """Grava o vínculo de cada fonte com o registro, sem repetir vínculos já existentes."""
    vinculadas = []
    for id_fonte in dict.fromkeys(ids_fontes or []):
        if session.get(Fontes, id_fonte) is None:
            raise ValueError(f"A fonte {id_fonte} não existe. Registre-a antes com registrar_fonte.")
        filtros = [getattr(modelo, nome) == valor for nome, valor in campos.items()]
        existe = session.execute(
            select(modelo).where(*filtros, modelo.id_fonte == id_fonte).limit(1)
        ).first()
        if existe is None:
            session.add(modelo(**campos, id_fonte=id_fonte))
        vinculadas.append(id_fonte)
    return vinculadas


def registrar_fonte(
    tp_fonte: str,
    nm_titulo: str,
    nm_url: str | None = None,
    cd_doi: str | None = None,
    nm_autores: str | None = None,
    nm_instituicao_publicadora: str | None = None,
    nr_ano_publicacao: int | None = None,
    cd_identificador_externo: str | None = None,
    ds_versao: str | None = None,
    dt_acesso: str | None = None,
    ds_observacoes: str | None = None,
) -> dict:
    """Registra uma fonte na tabela "fontes" e devolve o id_fonte. Se a fonte já existir, devolve o id existente.

    A fonte é considerada a mesma quando tem o mesmo DOI ou a mesma URL; sem DOI e sem URL,
    o mesmo tipo e título. Use o id_fonte devolvido em ids_fontes das demais funções.

    Args:
        tp_fonte: Tipo da fonte (ex.: "Ficha técnica", "Artigo científico", "Norma", "Base de dados calculados").
        nm_titulo: Título da fonte.
        nm_url: URL da fonte, quando houver.
        cd_doi: DOI, quando houver (ex.: "10.3390/met9020224").
        nm_autores: Autores; não informe quando a fonte não tiver autores.
        nm_instituicao_publicadora: Instituição, fabricante ou editora responsável.
        nr_ano_publicacao: Ano de publicação, quando informado na fonte.
        cd_identificador_externo: Identificador na base de origem (ex.: "mp-134", "Q25045309", UNS).
        ds_versao: Versão ou revisão da fonte ou da base de dados.
        dt_acesso: Data em que a fonte foi acessada, no formato AAAA-MM-DD.
        ds_observacoes: Observações (ex.: "calculado" para dados DFT, página/tabela consultada).
    """
    tp_fonte = _texto(tp_fonte, "tp_fonte", 50, obrigatorio=True)
    nm_titulo = _texto(nm_titulo, "nm_titulo", obrigatorio=True)
    nm_url = _texto(nm_url, "nm_url")
    cd_doi = _texto(cd_doi, "cd_doi")
    ds_versao = _texto(ds_versao, "ds_versao", 100)
    if nr_ano_publicacao is not None and not (1000 <= nr_ano_publicacao <= date.today().year + 1):
        raise ValueError("nr_ano_publicacao deve ser um ano válido.")
    data_acesso = None
    if dt_acesso:
        try:
            data_acesso = date.fromisoformat(dt_acesso.strip())
        except ValueError as erro:
            raise ValueError("dt_acesso deve estar no formato AAAA-MM-DD.") from erro

    if cd_doi:
        cd_doi = _normalizar_doi(cd_doi)
    if nm_url:
        nm_url = normalizar_url(nm_url)
    # Ordem de prioridade: DOI, depois URL; sem ambos, tipo + título.
    filtros = []
    if cd_doi:
        filtros.append(func.lower(Fontes.cd_doi) == cd_doi)
    if nm_url:
        filtros.append(Fontes.nm_url == nm_url)
    if not filtros:
        filtros.append((func.lower(Fontes.tp_fonte) == tp_fonte.lower()) & (func.lower(Fontes.nm_titulo) == nm_titulo.lower()))

    with Session(engine) as session:
        with session.begin():
            session.execute(text("SELECT pg_advisory_xact_lock(:chave)"), {"chave": 0})
            existente = None
            for filtro in filtros:
                existente = session.execute(
                    select(Fontes.id_fonte).where(filtro).order_by(Fontes.id_fonte).limit(1)
                ).scalar()
                if existente is not None:
                    break
            if existente is not None:
                return {"id_fonte": existente, "criado": False, "aviso": "Fonte já registrada; use este id_fonte."}
            fonte = Fontes(
                tp_fonte=tp_fonte, nm_titulo=nm_titulo, nm_autores=_texto(nm_autores, "nm_autores"),
                nm_instituicao_publicadora=_texto(nm_instituicao_publicadora, "nm_instituicao_publicadora"),
                nr_ano_publicacao=nr_ano_publicacao, cd_doi=cd_doi, nm_url=nm_url,
                cd_identificador_externo=_texto(cd_identificador_externo, "cd_identificador_externo"),
                ds_versao=ds_versao, dt_acesso=data_acesso, ds_observacoes=_texto(ds_observacoes, "ds_observacoes"),
            )
            session.add(fonte)
            session.flush()
            return {"id_fonte": fonte.id_fonte, "criado": True}


def registrar_material(
    id_projeto: int,
    nm_material: str,
    nm_grupo: str | None = None,
    nm_sub_grupo: str | None = None,
    nm_norma_designacao: str | None = None,
    ds_aplicacao: str | None = None,
    ds_ambiente: str | None = None,
    ds_condicao: str | None = None,
    ds_rota_fabricacao: str | None = None,
    ds_trat_termico: str | None = None,
    ds_trat_mecanico: str | None = None,
    ds_observacao: str | None = None,
    ids_fontes: list[int] | None = None,
) -> dict:
    """Registra um material (ou variante) encontrado na tabela "materiais" e vincula suas fontes em "ma_fontes".

    Cada material/variante é gravado uma única vez por projeto: se já existir um material com o
    mesmo nm_material no projeto, nada é inserido e o id existente é devolvido (as fontes novas
    são apenas vinculadas). Variantes diferentes (ex.: outra têmpera) devem ter nm_material diferente.

    Args:
        id_projeto: ID do projeto.
        nm_material: Designação do material/variante, incluindo a condição quando ela diferencia a variante (ex.: "AA 7075-T7351").
        nm_grupo: Grupo do material (ex.: "Alumínio e ligas de alumínio").
        nm_sub_grupo: Subgrupo do material (ex.: "Liga Al-Zn-Mg-Cu série 7xxx").
        nm_norma_designacao: Norma de designação confirmada (ex.: "ASTM B209").
        ds_aplicacao: Aplicação usual do material.
        ds_ambiente: Ambiente usual do material.
        ds_condicao: Condição do material: têmpera/estado e forma do produto (ex.: "T7351, chapa grossa 25–50 mm").
        ds_rota_fabricacao: Rota de fabricação (ex.: "laminação a quente").
        ds_trat_termico: Tratamento térmico.
        ds_trat_mecanico: Tratamento mecânico (ex.: "alívio de tensões por estiramento").
        ds_observacao: Observação: fabricante e especificação/revisão, quando encontrados.
        ids_fontes: IDs devolvidos por registrar_fonte que sustentam a existência do material e a condição comercial documentada.
    """
    nm_material = _texto(nm_material, "nm_material", 100, obrigatorio=True)
    campos = {
        "nm_grupo": _texto(nm_grupo, "nm_grupo", 50),
        "nm_sub_grupo": _texto(nm_sub_grupo, "nm_sub_grupo", 50),
        "nm_norma_designacao": _texto(nm_norma_designacao, "nm_norma_designacao", 150),
        "ds_aplicacao": _texto(ds_aplicacao, "ds_aplicacao"),
        "ds_ambiente": _texto(ds_ambiente, "ds_ambiente"),
        "ds_condicao": _texto(ds_condicao, "ds_condicao"),
        "ds_rota_fabricacao": _texto(ds_rota_fabricacao, "ds_rota_fabricacao"),
        "ds_trat_termico": _texto(ds_trat_termico, "ds_trat_termico"),
        "ds_trat_mecanico": _texto(ds_trat_mecanico, "ds_trat_mecanico"),
        "ds_observacao": _texto(ds_observacao, "ds_observacao"),
    }

    with Session(engine) as session:
        with session.begin():
            _bloquear_projeto(session, id_projeto)
            existentes = session.execute(select(Materiais).where(Materiais.id_projeto == id_projeto)).scalars().all()
            existente = next((m for m in existentes if _chave(m.nm_material) == _chave(nm_material)), None)
            criado = existente is None
            if criado:
                material = Materiais(id_projeto=id_projeto, nm_material=nm_material, **campos)
                session.add(material)
                session.flush()
                id_material = material.id_material
            else:
                id_material = existente.id_material
            fontes = _vincular_fontes(session, MateriaisFonte, ids_fontes, id_material=id_material, id_projeto=id_projeto)
    retorno = {"id_material": id_material, "criado": criado, "fontes_vinculadas": fontes}
    if not criado:
        retorno["aviso"] = "Material já registrado neste projeto; nada foi inserido."
    return retorno


def registrar_composicao(
    id_projeto: int,
    id_material: int,
    nm_sigla: str,
    nm_base_comp: str,
    pe_min: float | None = None,
    pe_max: float | None = None,
    fl_elem_balanco: bool = False,
    ds_observacao: str | None = None,
    ids_fontes: list[int] | None = None,
) -> dict:
    """Registra o percentual de um elemento na composição do material ("composicao_material") e vincula as fontes em "composicao_fonte".

    Faixa: preencha pe_min e pe_max. Valor único (nominal, máximo ou medido): preencha somente
    pe_max e explique em ds_observacao. Elemento de balanço: fl_elem_balanco=true, sem percentuais
    se a fonte não os informar. Se o elemento já estiver registrado para o material na mesma
    base, nada é inserido e o id existente é devolvido.

    Args:
        id_projeto: ID do projeto.
        id_material: ID do material (tabela materiais).
        nm_sigla: Símbolo do elemento (ex.: "Cr", "Ni") ou o termo da fonte para grupos (ex.: "Outros, cada").
        nm_base_comp: Base do percentual (ex.: "% em massa", "% atômica").
        pe_min: Percentual mínimo do elemento na composição.
        pe_max: Percentual máximo; em valor único, apenas este campo recebe o valor.
        fl_elem_balanco: true quando a fonte indica o elemento como balanço/restante.
        ds_observacao: Observações (ex.: "Valor único: máximo especificado", "Valor nominal", natureza da composição).
        ids_fontes: IDs devolvidos por registrar_fonte que sustentam o valor.
    """
    nm_sigla = _texto(nm_sigla, "nm_sigla", 80, obrigatorio=True)
    nm_base_comp = _texto(nm_base_comp, "nm_base_comp", 50, obrigatorio=True)
    ds_observacao = _texto(ds_observacao, "ds_observacao")
    if pe_min is not None and pe_max is None:
        raise ValueError("Valor único deve ser informado em pe_max (com a explicação em ds_observacao), não em pe_min.")
    for nome, valor in (("pe_min", pe_min), ("pe_max", pe_max)):
        if valor is not None and not (0 <= valor <= 100):
            raise ValueError(f"{nome} deve estar entre 0 e 100.")
    if pe_min is not None and pe_min > pe_max:
        raise ValueError("pe_min não pode ser maior que pe_max.")
    if pe_min is None and pe_max is None and not fl_elem_balanco and not ds_observacao:
        raise ValueError("Sem percentual, informe fl_elem_balanco=true ou explique em ds_observacao (ex.: \"Percentual não informado\").")

    with Session(engine) as session:
        with session.begin():
            _bloquear_projeto(session, id_projeto)
            _material_do_projeto(session, id_projeto, id_material)
            id_composicao = session.execute(
                select(ComposicaoMaterial.id_composicao).where(
                    ComposicaoMaterial.id_material == id_material,
                    func.lower(ComposicaoMaterial.nm_sigla) == nm_sigla.lower(),
                    func.lower(ComposicaoMaterial.nm_base_comp) == nm_base_comp.lower(),
                ).limit(1)
            ).scalar()
            criado = id_composicao is None
            if criado:
                composicao = ComposicaoMaterial(
                    id_material=id_material, nm_base_comp=nm_base_comp, pe_min=pe_min, pe_max=pe_max,
                    fl_elem_balanco=fl_elem_balanco, ds_observacao=ds_observacao, nm_sigla=nm_sigla,
                )
                session.add(composicao)
                session.flush()
                id_composicao = composicao.id_composicao
            fontes = _vincular_fontes(session, ComposicaoFonte, ids_fontes, id_composicao=id_composicao)
    retorno = {"id_composicao": id_composicao, "criado": criado, "fontes_vinculadas": fontes}
    if not criado:
        retorno["aviso"] = "Elemento já registrado para este material nesta base; nada foi inserido."
    return retorno


def listar_materiais_projeto(id_projeto: int) -> dict:
    """Lista os materiais já registrados no projeto, com seus dados e a quantidade de elementos de composição gravados.

    Use antes de registrar, para não repetir materiais, e para obter o id_material.

    Args:
        id_projeto: ID do projeto.
    """
    _validar_projeto_do_agente(id_projeto)
    with Session(engine) as session:
        materiais = session.execute(
            select(Materiais).where(Materiais.id_projeto == id_projeto).order_by(Materiais.id_material)
        ).scalars().all()
        resultado = [
            {
                "id_material": material.id_material,
                "nm_material": material.nm_material,
                "nm_grupo": material.nm_grupo,
                "nm_sub_grupo": material.nm_sub_grupo,
                "nm_norma_designacao": material.nm_norma_designacao,
                "ds_aplicacao": material.ds_aplicacao,
                "ds_ambiente": material.ds_ambiente,
                "ds_condicao": material.ds_condicao,
                "ds_rota_fabricacao": material.ds_rota_fabricacao,
                "ds_trat_termico": material.ds_trat_termico,
                "ds_trat_mecanico": material.ds_trat_mecanico,
                "ds_observacao": material.ds_observacao,
                "qtd_elementos_composicao": session.execute(
                    select(func.count()).select_from(ComposicaoMaterial)
                    .where(ComposicaoMaterial.id_material == material.id_material)
                ).scalar(),
            }
            for material in materiais
        ]
    return {"id_projeto": id_projeto, "materiais": resultado}


SIMBOLOS_ELEMENTOS = frozenset("""
H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se Br Kr
Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb
Lu Hf Ta W Re Os Ir Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf Es Fm Md No Lr Rf
Db Sg Bh Hs Mt Ds Rg Cn Nh Fl Mc Lv Ts Og
""".split())


def _simbolo_elemento(valor: str) -> str:
    """Valida o símbolo químico e o devolve com a grafia padrão (ex.: "al" -> "Al")."""
    simbolo = _texto(valor, "nm_sigla_elemento", 50, obrigatorio=True).capitalize()
    if simbolo not in SIMBOLOS_ELEMENTOS:
        raise ValueError(f"\"{valor}\" não é o símbolo de um elemento químico (ex.: \"Al\", \"Fe\", \"Mg\").")
    return simbolo


def registrar_elemento(
    id_projeto: int,
    nm_sigla_elemento: str,
    ds_observacao: str,
    ids_fontes: list[int],
) -> dict:
    """Registra um elemento químico pesquisado na tabela "pesquisa_elementos" e vincula suas fontes em "elementos_fontes".

    Cada elemento é gravado uma única vez por projeto: se o mesmo símbolo já estiver registrado no
    projeto, nada é inserido e o id existente é devolvido (as fontes novas são apenas vinculadas).

    Args:
        id_projeto: ID do projeto.
        nm_sigla_elemento: Símbolo do elemento químico (ex.: "Al", "Fe", "Mg").
        ds_observacao: Explicação de por que o elemento pode auxiliar a atingir as propriedades pedidas (mecanismo, processamento necessário e efeitos colaterais).
        ids_fontes: IDs devolvidos por registrar_fonte que sustentam a informação (ao menos um).
    """
    nm_sigla_elemento = _simbolo_elemento(nm_sigla_elemento)
    ds_observacao = _texto(ds_observacao, "ds_observacao", obrigatorio=True)
    if not ids_fontes:
        raise ValueError("Informe ao menos um id_fonte em ids_fontes. Registre a fonte antes com registrar_fonte.")

    with Session(engine) as session:
        with session.begin():
            _bloquear_projeto(session, id_projeto)
            id_elemento = session.execute(
                select(PesquisaElementos.id_elemento).where(
                    PesquisaElementos.id_projeto == id_projeto,
                    func.lower(PesquisaElementos.nm_sigla_elemento) == nm_sigla_elemento.lower(),
                ).order_by(PesquisaElementos.id_elemento).limit(1)
            ).scalar()
            criado = id_elemento is None
            if criado:
                elemento = PesquisaElementos(
                    id_projeto=id_projeto, nm_sigla_elemento=nm_sigla_elemento, ds_observacao=ds_observacao,
                )
                session.add(elemento)
                session.flush()
                id_elemento = elemento.id_elemento
            fontes = _vincular_fontes(session, ElementosFontes, ids_fontes, id_elemento=id_elemento)
    retorno = {"id_elemento": id_elemento, "nm_sigla_elemento": nm_sigla_elemento, "criado": criado, "fontes_vinculadas": fontes}
    if not criado:
        retorno["aviso"] = "Elemento já registrado neste projeto; nada foi inserido (somente as fontes novas foram vinculadas)."
    return retorno


def listar_elementos_projeto(id_projeto: int) -> dict:
    """Lista os elementos químicos já registrados no projeto, com a observação e os IDs das fontes vinculadas.

    Use antes de registrar, para não repetir elementos.

    Args:
        id_projeto: ID do projeto.
    """
    _validar_projeto_do_agente(id_projeto)
    with Session(engine) as session:
        elementos = session.execute(
            select(PesquisaElementos).where(PesquisaElementos.id_projeto == id_projeto).order_by(PesquisaElementos.id_elemento)
        ).scalars().all()
        resultado = [
            {
                "id_elemento": elemento.id_elemento,
                "nm_sigla_elemento": elemento.nm_sigla_elemento,
                "ds_observacao": elemento.ds_observacao,
                "ids_fontes": session.execute(
                    select(ElementosFontes.id_fonte)
                    .where(ElementosFontes.id_elemento == elemento.id_elemento)
                    .order_by(ElementosFontes.id_fonte)
                ).scalars().all(),
            }
            for elemento in elementos
        ]
    return {"id_projeto": id_projeto, "elementos": resultado}
