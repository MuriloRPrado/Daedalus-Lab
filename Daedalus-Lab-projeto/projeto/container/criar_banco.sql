-- Daedalus Lab: cria as tabelas usadas pelo fluxo Atena -> Rotina VAE -> Rotina Fases -> Calíope
-- e os cadastros fixos (status, tipos de projeto e propriedades).
-- O container daedalus_db executa este arquivo sozinho quando sobe com o volume vazio
-- (/docker-entrypoint-initdb.d). Também pode ser rodado à mão: o script não recria nem
-- sobrescreve o que já existe.

-- ============================== CADASTROS ==============================

CREATE TABLE IF NOT EXISTS status (
    id_status   INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cd_status   INTEGER CONSTRAINT uq_status_cd_status UNIQUE,
    nm_status   VARCHAR(50),
    ds_status   VARCHAR(80),
    ds_dominio  VARCHAR(80)
);

CREATE TABLE IF NOT EXISTS tp_projeto (
    id_tp_projeto  INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cd_tp_projeto  INTEGER,
    nm_tp_sigla    VARCHAR(10),
    ds_tp_projeto  VARCHAR(80),
    fl_ativo       BOOLEAN
);

CREATE TABLE IF NOT EXISTS propriedades_materiais (
    id_propriedade     INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nm_propriedade     VARCHAR(100),
    nm_categoria_prop  VARCHAR(100),
    ds_unidade         VARCHAR(255),
    ds_definicao       TEXT
);

-- ============================== PROJETO ==============================

CREATE TABLE IF NOT EXISTS projeto (
    id_projeto              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nm_usuario_solicitante  VARCHAR(255),
    nm_tp_sigla             VARCHAR(10),               -- o orquestrador processa projetos 'NC'
    nm_projeto              VARCHAR(255),
    ds_aplicacao            TEXT,
    ds_ambiente             TEXT,
    nm_material_ref         VARCHAR(255),
    ds_rota_fabricacao      VARCHAR(255),
    ds_custo                VARCHAR(100),
    cd_status               INTEGER CONSTRAINT fk_projeto_status REFERENCES status (cd_status),
    dt_criacao              TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    dt_atualizacao          TIMESTAMPTZ,
    dt_conclusao            TIMESTAMPTZ,
    ds_observacao           TEXT
);

CREATE TABLE IF NOT EXISTS projeto_requisitos (
    id_requisitos   INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_projeto      INTEGER REFERENCES projeto (id_projeto),
    id_propriedade  INTEGER CONSTRAINT fk_projeto_requisitos_propriedades REFERENCES propriedades_materiais (id_propriedade),
    nm_propriedade  VARCHAR(150),
    ds_unidade      VARCHAR(30),
    ds_descricao    TEXT
);

CREATE TABLE IF NOT EXISTS elemento_proj_restricao (
    id_elemento_restricao  INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_projeto             INTEGER REFERENCES projeto (id_projeto),
    nm_sigla_elemento      VARCHAR(50),
    ds_restricao           TEXT
);

CREATE TABLE IF NOT EXISTS retorno_cientistas (
    id_ret_cientistas  INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_projeto         INTEGER CONSTRAINT fk_id_projeto REFERENCES projeto (id_projeto),
    nm_agente          VARCHAR(100) NOT NULL,
    ds_retorno         TEXT NOT NULL,
    fl_utilizada       BOOLEAN,
    dt_criacao         TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================== FONTES ==============================

CREATE TABLE IF NOT EXISTS fontes (
    id_fonte                    INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tp_fonte                    VARCHAR(50) NOT NULL CONSTRAINT ck_fonte_tipo_preenchido CHECK (btrim(tp_fonte) <> ''),
    nm_titulo                   TEXT NOT NULL CONSTRAINT ck_fonte_titulo_preenchido CHECK (btrim(nm_titulo) <> ''),
    nm_autores                  TEXT,
    nm_instituicao_publicadora  TEXT,
    nr_ano_publicacao           SMALLINT CONSTRAINT ck_fonte_ano_positivo CHECK (nr_ano_publicacao > 0),
    cd_doi                      TEXT,
    nm_url                      TEXT,
    cd_identificador_externo    TEXT,
    ds_versao                   VARCHAR(100),
    dt_acesso                   DATE,
    nm_caminho_arquivo          TEXT,
    ds_observacoes              TEXT,
    dt_criacao                  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Cache de páginas e PDFs lidos (Firecrawl, OpenAlex, Unpaywall): cada URL é lida uma única vez.
CREATE TABLE IF NOT EXISTS fonte_consultada (
    id_fonte            SERIAL PRIMARY KEY,
    ds_url              TEXT NOT NULL,
    ds_url_normalizada  TEXT NOT NULL UNIQUE,
    nm_dominio          VARCHAR(255) NOT NULL,
    tp_conteudo         VARCHAR(10) NOT NULL,      -- 'html' | 'pdf'
    tp_nivel_fonte      VARCHAR(30),
    ds_titulo           TEXT,
    ds_conteudo         TEXT,
    nr_paginas_pdf      INTEGER,
    nr_paginas_lidas    INTEGER,
    fl_pdf_truncado     BOOLEAN DEFAULT FALSE,
    cd_http_status      INTEGER,
    ds_hash_conteudo    CHAR(64),
    ds_doi              VARCHAR(255),
    dt_consulta         TIMESTAMPTZ DEFAULT now(),
    dt_expiracao        TIMESTAMPTZ
);

-- Log de cada chamada externa, por projeto e agente (controle de créditos).
CREATE TABLE IF NOT EXISTS log_consulta_externa (
    id_log       SERIAL PRIMARY KEY,
    id_projeto   INTEGER REFERENCES projeto (id_projeto),
    nm_agente    VARCHAR(100),
    nm_servico   VARCHAR(30) NOT NULL,
    tp_operacao  VARCHAR(30) NOT NULL,
    ds_consulta  TEXT,
    id_fonte     INTEGER REFERENCES fonte_consultada (id_fonte),
    fl_cache     BOOLEAN DEFAULT FALSE,
    vl_creditos  INTEGER DEFAULT 0,
    ds_erro      TEXT,
    dt_consulta  TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_log_projeto ON log_consulta_externa (id_projeto, nm_agente);

-- ============================== ATENA ==============================

CREATE TABLE IF NOT EXISTS pesquisa_elementos (
    id_elemento        INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_projeto         INTEGER REFERENCES projeto (id_projeto),
    nm_sigla_elemento  VARCHAR(50) NOT NULL,
    ds_observacao      TEXT
);

CREATE TABLE IF NOT EXISTS elementos_fontes (
    id_ele_fonte  INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_fonte      INTEGER REFERENCES fontes (id_fonte),
    id_elemento   INTEGER REFERENCES pesquisa_elementos (id_elemento)
);

-- ============================== VAE ==============================

-- Cada composição gerada vira um material "Composição DAE-N" (N único no banco).
CREATE TABLE IF NOT EXISTS materiais (
    id_material          INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_projeto           INTEGER CONSTRAINT id_projeto REFERENCES projeto (id_projeto),
    nm_grupo             VARCHAR(50),
    nm_sub_grupo         VARCHAR(50),
    nm_norma_designacao  VARCHAR(150),
    nm_material          VARCHAR(100) UNIQUE,
    ds_observacao        TEXT,
    ds_aplicacao         TEXT,
    ds_ambiente          TEXT,
    ds_condicao          TEXT,
    ds_rota_fabricacao   TEXT,
    ds_trat_termico      TEXT,
    ds_trat_mecanico     TEXT
);

CREATE TABLE IF NOT EXISTS composicao_material (
    id_composicao    INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_material      INTEGER CONSTRAINT fk_id_material REFERENCES materiais (id_material),
    nm_sigla         VARCHAR(80),
    nm_base_comp     VARCHAR(50),
    pe_min           NUMERIC(7,4),
    pe_max           NUMERIC(7,4),
    fl_elem_balanco  BOOLEAN,
    ds_observacao    TEXT
);

-- ============================== ROTINA FASES ==============================

-- Fases previstas por composição: calculadas (DFT, Materials Project, 0 K), precisam de validação empírica.
CREATE TABLE IF NOT EXISTS fases_composicao (
    id_fase               SERIAL PRIMARY KEY,
    id_material           INTEGER NOT NULL REFERENCES materiais (id_material),
    nm_fase               VARCHAR(100) NOT NULL,
    cd_material_mp        VARCHAR(50),
    nm_grupo_espacial     VARCHAR(30),
    nm_sistema_cristalino VARCHAR(30),
    pe_fracao_atomica     NUMERIC(7,4),
    pe_fracao_massa       NUMERIC(7,4),
    vl_energia_formacao   NUMERIC(10,6),
    ds_sistema_quimico    VARCHAR(100),
    ds_versao_base        VARCHAR(30),
    id_fonte              INTEGER REFERENCES fontes (id_fonte),
    ds_observacao         TEXT,
    dt_criacao            TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_fases_composicao_material ON fases_composicao (id_material);

-- ============================== DADOS FIXOS ==============================

-- Códigos usados pelo orquestrador (orquestrador.py): 10, 11, 12, 21, 25 e 26.
INSERT INTO status (id_status, cd_status, nm_status, ds_status, ds_dominio) OVERRIDING SYSTEM VALUE VALUES
    (1, 10, 'Aguardando', 'Aguardando início da pesquisa', 'Projeto'),
    (2, 11, 'Erro', 'Ocorreu erro na pesquisa', 'Projeto'),
    (3, 12, 'Concluído', 'Pesquisa finalizada', 'Projeto'),
    (12, 21, 'Pesquisa em execução', 'Pesquisa iniciada por algum agente', 'Projeto'),
    (13, 22, 'Cancelado', 'Projeto cancelado', 'Projeto'),
    (16, 25, 'Pesquisa da Atena concluída', 'Pesquisa realizada pela agente Atena', 'Projeto'),
    (17, 26, 'Composições do VAE geradas', 'Rotina VAE gravou as composições DAE do projeto', 'Projeto'),
    (18, 27, 'Aguardando informação', 'Necessário informação para dar sequência', 'Projeto')
ON CONFLICT DO NOTHING;

INSERT INTO tp_projeto (id_tp_projeto, cd_tp_projeto, nm_tp_sigla, ds_tp_projeto, fl_ativo) OVERRIDING SYSTEM VALUE VALUES
    (1, 30, 'SME', 'Seleção de Material Existente', true),
    (2, 33, 'OC', 'Otimização de Composição', NULL),
    (3, 35, 'OP', 'Otimização de Processamento', NULL),
    (4, 37, 'ENL', 'Exploração de Nova Liga', NULL),
    (5, 43, 'NC', 'Nova Composição', true)
ON CONFLICT DO NOTHING;

INSERT INTO propriedades_materiais (id_propriedade, nm_propriedade, nm_categoria_prop, ds_unidade, ds_definicao) OVERRIDING SYSTEM VALUE VALUES
    (1, 'Energia incorporada', 'Propriedade Ecológica', 'MJ/kg', 'Ela é a soma de toda a energia necessária para extrair, processar, fabricar, transportar e descartar um material. Quanto mais processado ou industrializado é um material, maior é a sua energia incorporada e o seu impacto ambiental.'),
    (2, 'Pegada de carbono', 'Propriedade Ecológica', 'kg CO₂e/kg', 'Ela é uma propriedade ecológica crucial de qualquer material, representando a quantidade total de gases de efeito estufa (GEE) emitidos ao longo de seu ciclo de vida. Mede o impacto que a produção, o uso e o descarte de um material têm no aquecimento global.'),
    (3, 'Resistividade elétrica', 'Propriedade Elétrica', 'Ω·m', 'A resistividade elétrica é uma propriedade intrínseca de cada material que mede o tamanho da oposição oferecida à passagem da corrente elétrica. Depende exclusivamente da natureza química e física da substância, não alterando com o tamanho do componente.'),
    (4, 'Densidade', 'Propriedade Específica', 'kg/m³', 'Indica o grau de compactação ou empacotamento dos átomos de uma substância, servindo para identificar substâncias e prever se um objeto vai boiar ou afundar em um líquido.'),
    (5, 'Módulo de Young', 'Propriedade Mecânica', 'GPa', 'Mede a rigidez do material sob tração ou compressão no regime elástico. Quanto maior, menor a deformação para uma mesma tensão aplicada.'),
    (6, 'Módulo transversal', 'Propriedade Mecânica', 'GPa', 'Mede a rigidez elástica do material ao cisalhamento, esforço que altera sua forma pelo deslocamento relativo entre camadas internas.'),
    (7, 'Módulo volumétrico', 'Propriedade Mecânica', 'GPa', 'Mede a resistência do material à mudança de volume sob pressão uniforme em todas as direções. Quanto maior, menos compressível é o material.'),
    (8, 'Limite de escoamento', 'Propriedade Mecânica', 'MPa', 'Tensão associada ao início do escoamento plástico, com deformação que permanece após retirar a carga. Quando não há escoamento bem definido, costuma-se adotar uma deformação plástica de referência de 0,2%.'),
    (9, 'Limite de resistência à tração', 'Propriedade Mecânica', 'MPa', 'Maior tensão de engenharia alcançada durante um ensaio de tração, calculada pela força máxima dividida pela área inicial da seção do corpo de prova.'),
    (10, 'Dureza', 'Propriedade Mecânica', 'HB', 'Resistência à deformação plástica localizada, normalmente avaliada pela penetração de um indentador na superfície.'),
    (11, 'Alongamento', 'Propriedade Mecânica', '%', 'Aumento percentual do comprimento útil do corpo de prova após a ruptura, em relação ao comprimento inicial. Indica a ductilidade do material e depende do comprimento de referência e das condições do ensaio.'),
    (12, 'Tenacidade', 'Propriedade Mecânica', 'MJ/m³', 'Capacidade de absorver energia por deformação até a fratura. Em tração, pode ser quantificada pela área sob a curva tensão-deformação até a ruptura, como energia por unidade de volume.'),
    (13, 'Tenacidade à fratura', 'Propriedade Mecânica', 'MPa·√m', 'Resistência à propagação de uma trinca já existente. Pode ser expressa por diferentes parâmetros, como K_IC, em MPa·√m, válido sob condições específicas de ensaio e estado plano de deformação.'),
    (14, 'Condutividade térmica', 'Propriedade Térmica', 'W/(m·K)', 'Mede a capacidade do material de conduzir calor. Quanto maior, maior o fluxo de calor para um mesmo gradiente de temperatura. Depende da temperatura e pode variar com a direção no material.'),
    (15, 'Calor específico', 'Propriedade Térmica', 'J/(kg·K)', 'Quantidade de energia necessária para elevar em um kelvin a temperatura de uma unidade de massa do material, sem mudança de fase. Depende da temperatura e das condições do processo, como pressão ou volume constante.'),
    (16, 'Coeficiente de expansão térmica', 'Propriedade Térmica', 'K⁻¹', 'Quantifica a variação relativa das dimensões do material com a temperatura. O coeficiente linear descreve a mudança de comprimento; o volumétrico, a mudança de volume. Deve ser acompanhado do tipo de coeficiente, direção quando relevante e intervalo de temperatura.'),
    (17, 'Ponto de fusão', 'Propriedade Térmica', '°C', 'Temperatura em que ocorre a transformação entre sólido e líquido em equilíbrio, para uma pressão especificada. Muitas ligas apresentam um intervalo de fusão, entre a temperatura de início, solidus, e a de término, liquidus.'),
    (18, 'Temperatura de serviço máxima', 'Propriedade Térmica', '°C', 'Maior temperatura de uso na qual o material atende aos critérios de desempenho definidos para a aplicação. Depende de fatores como tempo de exposição, carregamento, ambiente e condição do material. Deve indicar se o uso é contínuo ou intermitente.'),
    (19, 'Temperatura de serviço mínima', 'Propriedade Térmica', '°C', 'Menor temperatura de uso na qual o material atende aos critérios de desempenho definidos para a aplicação, incluindo resistência à fratura quando relevante. Depende de fatores como carregamento, ambiente e condição do material.'),
    (20, 'Coeficiente de temperatura', 'Propriedade Elétrica', 'K⁻¹', 'Variação relativa da resistividade elétrica por unidade de temperatura, em relação a uma temperatura de referência.')
ON CONFLICT DO NOTHING;

SELECT setval(pg_get_serial_sequence('status', 'id_status'), (SELECT max(id_status) FROM status));
SELECT setval(pg_get_serial_sequence('tp_projeto', 'id_tp_projeto'), (SELECT max(id_tp_projeto) FROM tp_projeto));
SELECT setval(pg_get_serial_sequence('propriedades_materiais', 'id_propriedade'), (SELECT max(id_propriedade) FROM propriedades_materiais));
