-- Fases previstas (calculadas, DFT/Materials Project a 0 K) para as composições geradas pelo VAE.
-- Uma linha por fase de cada composição "Composição DAE-N" (materiais).
CREATE TABLE IF NOT EXISTS fases_composicao (
    id_fase               SERIAL PRIMARY KEY,
    id_material           INTEGER NOT NULL REFERENCES materiais (id_material),
    nm_fase               VARCHAR(100) NOT NULL,   -- fórmula reduzida da fase (ex.: Al2Cu)
    cd_material_mp        VARCHAR(50),             -- ID no Materials Project (ex.: mp-985806)
    nm_grupo_espacial     VARCHAR(30),             -- ex.: Fm-3m
    nm_sistema_cristalino VARCHAR(30),             -- ex.: Cubic
    pe_fracao_atomica     NUMERIC(7,4),            -- % dos átomos da composição nesta fase
    pe_fracao_massa       NUMERIC(7,4),            -- % da massa da composição nesta fase
    vl_energia_formacao   NUMERIC(10,6),           -- energia de formação da fase (eV/átomo)
    ds_sistema_quimico    VARCHAR(100),            -- elementos usados no cálculo (ex.: Al-Cu-Mg)
    ds_versao_base        VARCHAR(30),             -- versão do banco do Materials Project
    id_fonte              INTEGER REFERENCES fontes (id_fonte),
    ds_observacao         TEXT,
    dt_criacao            TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_fases_composicao_material ON fases_composicao (id_material);
