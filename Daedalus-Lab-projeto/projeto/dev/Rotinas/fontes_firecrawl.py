######################### BIBLIOTECAS ###################################
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
#########################################################################

"""Política de fontes usada pelas rotinas de busca e leitura (Firecrawl).

Cada domínio pertence a um nível de fonte. A correspondência inclui os
subdomínios: "alleima.com" também vale para "www.alleima.com".
Domínios que não estão em nenhuma lista recebem o nível "nao_classificada".
"""

NIVEL_FABRICANTE = "fabricante"
NIVEL_REFERENCIA_ABERTA = "referencia_aberta"
NIVEL_COMPLEMENTAR = "complementar"
NIVEL_INDICE_NORMA = "indice_norma"
NIVEL_ARTIGO = "artigo"
NIVEL_NAO_CLASSIFICADA = "nao_classificada"

# Fichas técnicas de fabricantes: fonte principal para composição, propriedades,
# tratamentos térmicos e aplicações de ligas comerciais.
FABRICANTES = {
    "Outokumpu": ["outokumpu.com"],
    "Alleima (antiga Sandvik Materials Technology)": ["alleima.com", "materials.sandvik"],
    "Aperam": ["aperam.com"],
    "Villares Metals": ["villaresmetals.com.br"],
    "Gerdau": ["gerdau.com", "gerdau.com.br"],
    "Carpenter Technology": ["carpentertechnology.com"],
    "ATI": ["atimaterials.com"],
    "Haynes International": ["haynesintl.com"],
    "Special Metals": ["specialmetals.com"],
    "Böhler/voestalpine": ["bohler.com", "bohler-edelstahl.com", "voestalpine.com"],
    "Aalco": ["aalco.co.uk"],
}

# Referências técnicas abertas. Do NIST, somente o conteúdo de acesso aberto.
REFERENCIAS_ABERTAS = ["nist.gov", "wikipedia.org", "wikidata.org"]

# Qualidade e atualização variam: usar como complemento, nunca como fonte primária.
COMPLEMENTARES = ["engineeringtoolbox.com", "efunda.com"]

# Páginas públicas de normas trazem só índice e resumo; o texto completo é pago.
INDICES_NORMA = ["astm.org", "asminternational.org", "abnt.org.br", "abntcatalogo.com.br", "iso.org", "sae.org"]

# Bloqueados: termos que proíbem uso automatizado, robots.txt restritivo ou
# conteúdo pago/licenciado. Formato: (domínio, prefixo de caminho ou None).
BLOQUEADOS = [
    ("makeitfrom.com", None),                   # termos proíbem uso automatizado
    ("matweb.com", None),                       # termos proíbem scraping
    ("azom.com", None),                         # robots.txt bloqueia agentes de IA
    ("matmatch.com", None),
    ("matmake.com", None),
    ("dl.asminternational.org", None),          # ASM Handbooks (pago)
    ("matdata.asminternational.org", None),     # ASM Alloy Phase Diagrams (pago)
    ("totalmateria.com", None),                 # pago
    ("keytometals.com", None),                  # Total Materia
    ("materials.springer.com", None),           # Springer Materials (pago)
    ("springermaterials.com", None),
    ("icsd.fiz-karlsruhe.de", None),            # ICSD (pago)
    ("icsd.products.fiz-karlsruhe.de", None),
    ("crystalimpact.com", "/pcd"),              # Pearson's Crystal Data (pago)
    ("mpds.io", None),                          # MPDS (pago)
    ("grantadesign.com", None),                 # Ansys Granta (pago)
    ("ansys.com", "/products/materials"),
    ("mmpds.org", None),                        # MMPDS (pago)
]

# Parâmetros de rastreamento removidos na normalização da URL.
_PARAMETROS_IGNORADOS = {"fbclid", "gclid", "mc_cid", "mc_eid", "ref", "ref_src"}


def _host(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _pertence(host: str, dominio: str) -> bool:
    return host == dominio or host.endswith("." + dominio)


def obter_dominio(url: str) -> str:
    """Devolve o domínio da URL, sem "www."."""
    return _host(url)


def normalizar_url(url: str) -> str:
    """Normaliza a URL para servir de chave do cache: minúsculas no domínio, sem âncora e sem parâmetros de rastreamento."""
    partes = urlsplit(url.strip())
    esquema = (partes.scheme or "https").lower()
    host = (partes.hostname or "").lower()
    if partes.port and not ((esquema == "https" and partes.port == 443) or (esquema == "http" and partes.port == 80)):
        host = f"{host}:{partes.port}"
    parametros = [
        (chave, valor)
        for chave, valor in parse_qsl(partes.query, keep_blank_values=True)
        if not chave.lower().startswith("utm_") and chave.lower() not in _PARAMETROS_IGNORADOS
    ]
    caminho = partes.path or "/"
    return urlunsplit((esquema, host, caminho, urlencode(parametros), ""))


def dominio_bloqueado(url: str) -> bool:
    """Indica se a URL pertence a uma fonte bloqueada."""
    host = _host(url)
    caminho = (urlsplit(url).path or "/").lower()
    for dominio, prefixo in BLOQUEADOS:
        if _pertence(host, dominio) and (prefixo is None or caminho.startswith(prefixo)):
            return True
    return False


def dominios_bloqueados_busca() -> list[str]:
    """Domínios inteiros bloqueados, no formato aceito pelo excludeDomains da busca."""
    return sorted({dominio for dominio, prefixo in BLOQUEADOS if prefixo is None})


def dominios_fabricantes(fabricantes: list[str] | None = None) -> list[str]:
    """Domínios dos fabricantes informados (por nome, sem diferenciar maiúsculas) ou de todos."""
    if not fabricantes:
        return [d for dominios in FABRICANTES.values() for d in dominios]
    procurados = [f.strip().lower() for f in fabricantes if f and f.strip()]
    selecionados = []
    for nome, dominios in FABRICANTES.items():
        if any(p in nome.lower() or any(p in dominio for dominio in dominios) for p in procurados):
            selecionados.extend(dominios)
    if not selecionados:
        raise ValueError(f"Fabricante não reconhecido. Opções: {', '.join(FABRICANTES)}.")
    return selecionados


def classificar_fonte(url: str) -> str:
    """Devolve o nível da fonte: fabricante, referencia_aberta, complementar, indice_norma ou nao_classificada."""
    host = _host(url)
    if any(_pertence(host, d) for d in dominios_fabricantes()):
        return NIVEL_FABRICANTE
    if any(_pertence(host, d) for d in REFERENCIAS_ABERTAS):
        return NIVEL_REFERENCIA_ABERTA
    if any(_pertence(host, d) for d in COMPLEMENTARES):
        return NIVEL_COMPLEMENTAR
    if any(_pertence(host, d) for d in INDICES_NORMA):
        return NIVEL_INDICE_NORMA
    return NIVEL_NAO_CLASSIFICADA


def nome_fabricante(url: str) -> str | None:
    """Devolve o nome do fabricante dono da URL, se houver."""
    host = _host(url)
    for nome, dominios in FABRICANTES.items():
        if any(_pertence(host, d) for d in dominios):
            return nome
    return None
