/*INSERT INTO elemento_proj_restricao
(
    id_projeto,
    nm_sigla_elemento,
    ds_restricao
)
VALUES
(
    1,
    'Al',
    'Quero que o material tenha obrigatóriamente Aluminio em sua composição'
),
(
    1,
    'Fe',
    'O material deve ter Ferro em sua composição'
),
(
    1,
    'Ti',
    'O material deve ter Titânio em sua composição'
);*/

select * from projeto_requisitos;

INSERT INTO projeto_requisitos
(
    id_projeto,
    id_propriedade,
    nm_propriedade,
    ds_unidade,
    fl_obrigatorio,
    ds_descricao
)
VALUES
(
    1,
    8,
    'Limite de escoamento',
    'MPa',
    FALSE,
    'O material deve possuir um Limite de escoamente igual ou maior que 300 MPa'
),
(
    1,
    5,
    'Módulo de Young',
    'GPa',
    FALSE,
    'O material deve possuir um módulo de young maior que 60 GPa'
),
(
    1,
    10,
    'Dureza',
    'HB',
    FALSE,
    'O material deve possuir uma dureza igual ou maior que 95 HB'
),
(
    1,
    17,
    'Ponto de fusão',
    '°C',
    FALSE,
    'A faixa do ponto de fusão do material deve estar entre 470 a 630 °C'
);

select * from projeto;

select * from composicao_material;

select * from retorno_cientistas;

select * from pesquisa_elementos;

select * from composicao_fonte;

select * from elementos_fontes;
