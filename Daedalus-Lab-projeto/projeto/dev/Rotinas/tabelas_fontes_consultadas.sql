-- Tabelas usadas por Rotinas/cache_fontes.py (Firecrawl, OpenAlex e Unpaywall).

-- Cache: cada URL lida uma única vez. Guarda o texto extraído, não o arquivo PDF.
CREATE TABLE IF NOT EXISTS fonte_consultada (
    id_fonte            SERIAL PRIMARY KEY,
    ds_url              TEXT NOT NULL,
    ds_url_normalizada  TEXT NOT NULL UNIQUE,      -- sem utm, #âncora etc.
    nm_dominio          VARCHAR(255) NOT NULL,
    tp_conteudo         VARCHAR(10)  NOT NULL,     -- 'html' | 'pdf'
    tp_nivel_fonte      VARCHAR(30),               -- fabricante | referencia_aberta | complementar | indice_norma | artigo | nao_classificada
    ds_titulo           TEXT,
    ds_conteudo         TEXT,                      -- markdown retornado pelo Firecrawl
    nr_paginas_pdf      INTEGER,
    nr_paginas_lidas    INTEGER,
    fl_pdf_truncado     BOOLEAN DEFAULT FALSE,     -- leu só parte do PDF
    cd_http_status      INTEGER,
    ds_hash_conteudo    CHAR(64),                  -- SHA-256 do conteúdo
    ds_doi              VARCHAR(255),              -- quando vier de artigo
    dt_consulta         TIMESTAMPTZ DEFAULT now(),
    dt_expiracao        TIMESTAMPTZ                -- padrão: +90 dias (DAEDALUS_DIAS_VALIDADE_CACHE)
);

-- Log: cada chamada de ferramenta, por projeto e agente (controle de créditos)
CREATE TABLE IF NOT EXISTS log_consulta_externa (
    id_log          SERIAL PRIMARY KEY,
    id_projeto      INTEGER REFERENCES projeto(id_projeto),
    nm_agente       VARCHAR(100),
    nm_servico      VARCHAR(30)  NOT NULL,         -- firecrawl | openalex | unpaywall
    tp_operacao     VARCHAR(30)  NOT NULL,         -- busca | leitura
    ds_consulta     TEXT,                          -- termo buscado, DOI ou URL
    id_fonte        INTEGER REFERENCES fonte_consultada(id_fonte),
    fl_cache        BOOLEAN DEFAULT FALSE,         -- true = veio do cache, 0 créditos
    vl_creditos     INTEGER DEFAULT 0,
    ds_erro         TEXT,
    dt_consulta     TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_log_projeto ON log_consulta_externa (id_projeto, nm_agente);
