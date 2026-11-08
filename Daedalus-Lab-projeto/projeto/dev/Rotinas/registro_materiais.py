"""Gravação dos materiais selecionados e da caracterização no banco do projeto.

Têmis usa: registrar_fonte, registrar_material, registrar_estado_material e listar_materiais_projeto.
Calíope usa: registrar_fonte, registrar_composicao, registrar_valor_propriedade,
registrar_fase_estrutura e listar_materiais_projeto.

Cada função confere se o registro já existe antes de inserir (o mesmo material não é
gravado duas vezes no mesmo projeto) e vincula as fontes informadas nas tabelas
ma_fontes, me_fontes, cm_fontes, vlp_fontes e fec_fontes.
"""
######################### BIBLIOTECAS ###################################
import re
from datetime import date

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from database import (
    ComposicaoFonte, ComposicaoMaterial, EstrutCristalinaFontes, EstruturaCristalina, Fontes,
    Materiais, MateriaisEstado, MateriaisEstadosFonte, MateriaisFonte, Propriedade,
    ValorPropriedades, ValorPropriedadesFonte, engine,
)
from Rotinas.fontes_firecrawl import normalizar_url
#########################################################################

RESULTADOS_TEMIS = ("Atende", "Parcial")


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


def _bloquear_projeto(session: Session, id_projeto: int) -> None:
    """Evita que duas gravações simultâneas do mesmo projeto criem registros repetidos."""
    session.execute(text("SELECT pg_advisory_xact_lock(:chave)"), {"chave": id_projeto})


def _material_do_projeto(session: Session, id_projeto: int, id_material: int) -> Materiais:
    material = session.get(Materiais, id_material)
    if material is None or material.id_projeto != id_projeto:
        raise ValueError(f"O material {id_material} não existe no projeto {id_projeto}.")
    return material


def _estado_do_projeto(session: Session, id_projeto: int, id_mat_estado: int) -> MateriaisEstado:
    estado = session.get(MateriaisEstado, id_mat_estado)
    if estado is None:
        raise ValueError(f"O estado de material {id_mat_estado} não existe.")
    _material_do_projeto(session, id_projeto, estado.id_material)
    return estado


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

    A fonte é considerada a mesma quando tem o mesmo DOI; sem DOI, a mesma URL; sem DOI e
    sem URL, o mesmo tipo e título. Use o id_fonte devolvido em ids_fontes das demais funções.

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
        filtro = func.lower(Fontes.cd_doi) == cd_doi
    elif nm_url:
        nm_url = normalizar_url(nm_url)
        filtro = Fontes.nm_url == nm_url
    else:
        filtro = (func.lower(Fontes.tp_fonte) == tp_fonte.lower()) & (func.lower(Fontes.nm_titulo) == nm_titulo.lower())

    with Session(engine) as session:
        with session.begin():
            session.execute(text("SELECT pg_advisory_xact_lock(:chave)"), {"chave": 0})
            existente = session.execute(select(Fontes.id_fonte).where(filtro).limit(1)).scalar()
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
    ds_observacao: str,
    nm_grupo: str | None = None,
    nm_sub_grupo: str | None = None,
    nm_norma_designacao: str | None = None,
    ids_fontes: list[int] | None = None,
) -> dict:
    """Registra um material (ou variante) selecionado na tabela "materiais" e vincula suas fontes em "ma_fontes".

    Cada material/variante é gravado uma única vez por projeto: se já existir um material com o
    mesmo nm_material no projeto, nada é inserido e o id existente é devolvido (as fontes novas
    são apenas vinculadas). Variantes diferentes (ex.: outra têmpera) devem ter nm_material diferente.

    Args:
        id_projeto: ID do projeto.
        nm_material: Designação do material/variante, incluindo a condição quando ela diferencia a variante (ex.: "AA 7075-T7351").
        ds_observacao: Deve começar com "Atende" ou "Parcial", seguido das informações necessárias (ex.: "Parcial — atende às propriedades; restrição de Cu inconclusiva").
        nm_grupo: Grupo do material (ex.: "Alumínio e ligas de alumínio").
        nm_sub_grupo: Subgrupo do material (ex.: "Liga Al-Zn-Mg-Cu série 7xxx").
        nm_norma_designacao: Norma de designação confirmada (ex.: "ASTM B209").
        ids_fontes: IDs devolvidos por registrar_fonte que sustentam a identificação do material.
    """
    nm_material = _texto(nm_material, "nm_material", 100, obrigatorio=True)
    ds_observacao = _texto(ds_observacao, "ds_observacao", obrigatorio=True)
    if not ds_observacao.startswith(RESULTADOS_TEMIS):
        raise ValueError('ds_observacao deve começar com "Atende" ou "Parcial".')
    nm_grupo = _texto(nm_grupo, "nm_grupo", 50)
    nm_sub_grupo = _texto(nm_sub_grupo, "nm_sub_grupo", 50)
    nm_norma_designacao = _texto(nm_norma_designacao, "nm_norma_designacao", 150)

    with Session(engine) as session:
        with session.begin():
            _bloquear_projeto(session, id_projeto)
            existentes = session.execute(
                select(Materiais.id_material, Materiais.nm_material).where(Materiais.id_projeto == id_projeto)
            ).all()
            id_material = next((m.id_material for m in existentes if _chave(m.nm_material) == _chave(nm_material)), None)
            criado = id_material is None
            if criado:
                material = Materiais(
                    id_projeto=id_projeto, nm_grupo=nm_grupo, nm_sub_grupo=nm_sub_grupo,
                    nm_norma_designacao=nm_norma_designacao, nm_material=nm_material, ds_observacao=ds_observacao,
                )
                session.add(material)
                session.flush()
                id_material = material.id_material
            fontes = _vincular_fontes(session, MateriaisFonte, ids_fontes, id_material=id_material, id_projeto=id_projeto)
    retorno = {"id_material": id_material, "criado": criado, "fontes_vinculadas": fontes}
    if not criado:
        retorno["aviso"] = "Material já registrado neste projeto; nada foi inserido."
    return retorno


def registrar_estado_material(
    id_projeto: int,
    id_material: int,
    ds_condicao: str | None = None,
    ds_aplicacao: str | None = None,
    ds_ambiente: str | None = None,
    ds_rota_fabricacao: str | None = None,
    ds_trat_termico: str | None = None,
    ds_trat_mecanico: str | None = None,
    ids_fontes: list[int] | None = None,
) -> dict:
    """Registra o estado do material (condição, tratamentos, rota) na tabela "materiais_estado" e vincula as fontes em "me_fontes".

    Cada material/variante tem um único estado: se o material já tiver estado registrado, nada é
    inserido e o id existente é devolvido (as fontes novas são apenas vinculadas).

    Args:
        id_projeto: ID do projeto.
        id_material: ID devolvido por registrar_material.
        ds_condicao: Condição/têmpera e forma do produto (ex.: "T7351, chapa grossa 25–50 mm").
        ds_aplicacao: Aplicação documentada do material nessa condição.
        ds_ambiente: Ambiente de serviço documentado.
        ds_rota_fabricacao: Rota de fabricação (ex.: "laminação a quente").
        ds_trat_termico: Tratamento térmico.
        ds_trat_mecanico: Tratamento mecânico (ex.: "alívio de tensões por estiramento").
        ids_fontes: IDs devolvidos por registrar_fonte que sustentam o estado.
    """
    campos = {
        "ds_condicao": _texto(ds_condicao, "ds_condicao", 255),
        "ds_aplicacao": _texto(ds_aplicacao, "ds_aplicacao"),
        "ds_ambiente": _texto(ds_ambiente, "ds_ambiente"),
        "ds_rota_fabricacao": _texto(ds_rota_fabricacao, "ds_rota_fabricacao", 255),
        "ds_trat_termico": _texto(ds_trat_termico, "ds_trat_termico"),
        "ds_trat_mecanico": _texto(ds_trat_mecanico, "ds_trat_mecanico"),
    }
    with Session(engine) as session:
        with session.begin():
            _bloquear_projeto(session, id_projeto)
            _material_do_projeto(session, id_projeto, id_material)
            id_mat_estado = session.execute(
                select(MateriaisEstado.id_mat_estado).where(MateriaisEstado.id_material == id_material)
                .order_by(MateriaisEstado.id_mat_estado).limit(1)
            ).scalar()
            criado = id_mat_estado is None
            if criado:
                estado = MateriaisEstado(id_material=id_material, **campos)
                session.add(estado)
                session.flush()
                id_mat_estado = estado.id_mat_estado
            fontes = _vincular_fontes(
                session, MateriaisEstadosFonte, ids_fontes, id_mat_estado=id_mat_estado, id_material=id_material
            )
    retorno = {"id_mat_estado": id_mat_estado, "criado": criado, "fontes_vinculadas": fontes}
    if not criado:
        retorno["aviso"] = "O material já possui estado registrado; nada foi inserido."
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
    """Registra o percentual de um elemento na composição do material ("composicao_material") e vincula as fontes em "cm_fontes".

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
            fontes = _vincular_fontes(
                session, ComposicaoFonte, ids_fontes, id_composicao=id_composicao, id_material=id_material
            )
    retorno = {"id_composicao": id_composicao, "criado": criado, "fontes_vinculadas": fontes}
    if not criado:
        retorno["aviso"] = "Elemento já registrado para este material nesta base; nada foi inserido."
    return retorno


def registrar_valor_propriedade(
    id_projeto: int,
    id_mat_estado: int,
    id_propriedade: int,
    tp_valor: str,
    vl_prop: float | None = None,
    vl_min_prop: float | None = None,
    vl_max_prop: float | None = None,
    ids_fontes: list[int] | None = None,
) -> dict:
    """Registra o valor de uma propriedade do estado do material ("valor_propriedades_materiais") e vincula as fontes em "vlp_fontes".

    O valor deve estar na unidade cadastrada (ds_unidade) da propriedade em propriedades_materiais;
    converta antes de gravar e registre a conversão em tp_valor. Se o mesmo valor já estiver
    registrado para o estado e a propriedade, nada é inserido.

    Args:
        id_projeto: ID do projeto.
        id_mat_estado: ID do estado do material (tabela materiais_estado).
        id_propriedade: ID da propriedade na tabela propriedades_materiais.
        tp_valor: Natureza e condição do valor (ex.: "mínimo especificado, L, 25 °C", "típico", "calculado").
        vl_prop: Valor pontual.
        vl_min_prop: Limite inferior da faixa.
        vl_max_prop: Limite superior da faixa.
        ids_fontes: IDs devolvidos por registrar_fonte que sustentam o valor.
    """
    tp_valor = _texto(tp_valor, "tp_valor", 150, obrigatorio=True)
    if vl_prop is None and vl_min_prop is None and vl_max_prop is None:
        raise ValueError("Informe vl_prop ou a faixa (vl_min_prop/vl_max_prop).")
    if vl_min_prop is not None and vl_max_prop is not None and vl_min_prop > vl_max_prop:
        raise ValueError("vl_min_prop não pode ser maior que vl_max_prop.")

    def _igual(coluna, valor):
        return coluna.is_(None) if valor is None else coluna == valor

    with Session(engine) as session:
        with session.begin():
            _bloquear_projeto(session, id_projeto)
            _estado_do_projeto(session, id_projeto, id_mat_estado)
            propriedade = session.get(Propriedade, id_propriedade)
            if propriedade is None:
                raise ValueError(f"A propriedade {id_propriedade} não existe em propriedades_materiais.")
            unidade = propriedade.ds_unidade
            id_vl_prop = session.execute(
                select(ValorPropriedades.id_vl_prop).where(
                    ValorPropriedades.id_mat_estado == id_mat_estado,
                    ValorPropriedades.id_propriedade == id_propriedade,
                    _igual(ValorPropriedades.vl_prop, vl_prop),
                    _igual(ValorPropriedades.vl_min_prop, vl_min_prop),
                    _igual(ValorPropriedades.vl_max_prop, vl_max_prop),
                    func.lower(ValorPropriedades.tp_valor) == tp_valor.lower(),
                ).limit(1)
            ).scalar()
            criado = id_vl_prop is None
            if criado:
                valor = ValorPropriedades(
                    id_propriedade=id_propriedade, id_mat_estado=id_mat_estado, vl_prop=vl_prop,
                    vl_min_prop=vl_min_prop, vl_max_prop=vl_max_prop, tp_valor=tp_valor,
                )
                session.add(valor)
                session.flush()
                id_vl_prop = valor.id_vl_prop
            fontes = _vincular_fontes(
                session, ValorPropriedadesFonte, ids_fontes, id_vl_prop=id_vl_prop, id_mat_estado=id_mat_estado
            )
    retorno = {"id_vl_prop": id_vl_prop, "criado": criado, "unidade": unidade, "fontes_vinculadas": fontes}
    if not criado:
        retorno["aviso"] = "Valor já registrado para este estado e propriedade; nada foi inserido."
    return retorno


def registrar_fase_estrutura(
    id_projeto: int,
    id_mat_estado: int,
    nm_fase: str,
    nm_estrut_cristalina: str | None = None,
    ds_grupo_espacial: str | None = None,
    vl_fracao_fase: str | None = None,
    nm_base_fracao: str | None = None,
    vl_parametro_a_ang: float | None = None,
    vl_parametro_b_ang: float | None = None,
    vl_parametro_c_ang: float | None = None,
    vl_angulo_alfa_graus: float | None = None,
    vl_angulo_beta_graus: float | None = None,
    vl_angulo_gama_graus: float | None = None,
    vl_massa_especifica_kgm3: float | None = None,
    vl_temperatura_k: float | None = None,
    vl_pressao_pa: float | None = None,
    ids_fontes: list[int] | None = None,
) -> dict:
    """Registra uma fase e sua estrutura cristalina ("fase_estrut_cristalina") e vincula as fontes em "fec_fontes".

    Registre uma linha por fase. Se a mesma fase e estrutura já estiverem registradas para o
    estado, nada é inserido e o id existente é devolvido.

    Args:
        id_projeto: ID do projeto.
        id_mat_estado: ID do estado do material (tabela materiais_estado).
        nm_fase: Nome da fase (ex.: "austenita (γ)", "ferrita (α)", "η-MgZn2").
        nm_estrut_cristalina: Estrutura cristalina (ex.: "CFC", "CCC", "HC", "tetragonal").
        ds_grupo_espacial: Grupo espacial com símbolo e número (ex.: "Fm-3m (225)").
        vl_fracao_fase: Fração da fase como informada na fonte (ex.: "45–55").
        nm_base_fracao: Base da fração (ex.: "% em volume").
        vl_parametro_a_ang: Parâmetro de rede a, em Å.
        vl_parametro_b_ang: Parâmetro de rede b, em Å.
        vl_parametro_c_ang: Parâmetro de rede c, em Å.
        vl_angulo_alfa_graus: Ângulo α, em graus.
        vl_angulo_beta_graus: Ângulo β, em graus.
        vl_angulo_gama_graus: Ângulo γ, em graus.
        vl_massa_especifica_kgm3: Massa específica da fase, em kg/m³ (g/cm³ × 1000).
        vl_temperatura_k: Temperatura dos dados, em K.
        vl_pressao_pa: Pressão dos dados, em Pa.
        ids_fontes: IDs devolvidos por registrar_fonte que sustentam os dados da fase.
    """
    nm_fase = _texto(nm_fase, "nm_fase", 255, obrigatorio=True)
    nm_estrut_cristalina = _texto(nm_estrut_cristalina, "nm_estrut_cristalina", 255)
    campos = {
        "ds_grupo_espacial": _texto(ds_grupo_espacial, "ds_grupo_espacial"),
        "vl_fracao_fase": _texto(vl_fracao_fase, "vl_fracao_fase", 255),
        "nm_base_fracao": _texto(nm_base_fracao, "nm_base_fracao", 100),
        "vl_parametro_a_ang": vl_parametro_a_ang, "vl_parametro_b_ang": vl_parametro_b_ang,
        "vl_parametro_c_ang": vl_parametro_c_ang, "vl_angulo_alfa_graus": vl_angulo_alfa_graus,
        "vl_angulo_beta_graus": vl_angulo_beta_graus, "vl_angulo_gama_graus": vl_angulo_gama_graus,
        "vl_massa_especifica_kgm3": vl_massa_especifica_kgm3, "vl_temperatura_k": vl_temperatura_k,
        "vl_pressao_pa": vl_pressao_pa,
    }
    with Session(engine) as session:
        with session.begin():
            _bloquear_projeto(session, id_projeto)
            _estado_do_projeto(session, id_projeto, id_mat_estado)
            fases = session.execute(
                select(EstruturaCristalina.id_fase, EstruturaCristalina.nm_fase, EstruturaCristalina.nm_estrut_cristalina)
                .where(EstruturaCristalina.id_mat_estado == id_mat_estado)
            ).all()
            id_fase = next(
                (f.id_fase for f in fases
                 if _chave(f.nm_fase) == _chave(nm_fase) and _chave(f.nm_estrut_cristalina) == _chave(nm_estrut_cristalina)),
                None,
            )
            criado = id_fase is None
            if criado:
                fase = EstruturaCristalina(
                    id_mat_estado=id_mat_estado, nm_fase=nm_fase, nm_estrut_cristalina=nm_estrut_cristalina, **campos
                )
                session.add(fase)
                session.flush()
                id_fase = fase.id_fase
            fontes = _vincular_fontes(
                session, EstrutCristalinaFontes, ids_fontes, id_fase=id_fase, id_mat_estado=id_mat_estado
            )
    retorno = {"id_fase": id_fase, "criado": criado, "fontes_vinculadas": fontes}
    if not criado:
        retorno["aviso"] = "Fase já registrada para este estado; nada foi inserido."
    return retorno


def listar_materiais_projeto(id_projeto: int) -> dict:
    """Lista os materiais já registrados no projeto, com seus estados e a quantidade de dados gravados.

    Use antes de registrar, para não repetir materiais, e para obter id_material e id_mat_estado.

    Args:
        id_projeto: ID do projeto.
    """
    with Session(engine) as session:
        materiais = session.execute(
            select(Materiais).where(Materiais.id_projeto == id_projeto).order_by(Materiais.id_material)
        ).scalars().all()
        resultado = []
        for material in materiais:
            estados = session.execute(
                select(MateriaisEstado).where(MateriaisEstado.id_material == material.id_material)
                .order_by(MateriaisEstado.id_mat_estado)
            ).scalars().all()
            qtd_comp = session.execute(
                select(func.count()).select_from(ComposicaoMaterial)
                .where(ComposicaoMaterial.id_material == material.id_material)
            ).scalar()
            resultado.append({
                "id_material": material.id_material,
                "nm_material": material.nm_material,
                "nm_grupo": material.nm_grupo,
                "nm_sub_grupo": material.nm_sub_grupo,
                "nm_norma_designacao": material.nm_norma_designacao,
                "ds_observacao": material.ds_observacao,
                "qtd_elementos_composicao": qtd_comp,
                "estados": [
                    {
                        "id_mat_estado": e.id_mat_estado,
                        "ds_condicao": e.ds_condicao,
                        "ds_aplicacao": e.ds_aplicacao,
                        "ds_ambiente": e.ds_ambiente,
                        "ds_rota_fabricacao": e.ds_rota_fabricacao,
                        "ds_trat_termico": e.ds_trat_termico,
                        "ds_trat_mecanico": e.ds_trat_mecanico,
                        "qtd_valores_propriedades": session.execute(
                            select(func.count()).select_from(ValorPropriedades)
                            .where(ValorPropriedades.id_mat_estado == e.id_mat_estado)
                        ).scalar(),
                        "qtd_fases": session.execute(
                            select(func.count()).select_from(EstruturaCristalina)
                            .where(EstruturaCristalina.id_mat_estado == e.id_mat_estado)
                        ).scalar(),
                    }
                    for e in estados
                ],
            })
    return {"id_projeto": id_projeto, "materiais": resultado}
