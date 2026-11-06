# Daedalus Lab — Site de apresentação

Landing page em português para apresentar a proposta de pesquisa de materiais metálicos do Daedalus Lab. Identidade visual azul (#1246B5), titânio (#858D99), grafite e branco.

## Sobre o projeto

O Daedalus Lab é uma proposta de plataforma multiagente para apoiar engenheiros de produto, profissionais de P&D, pesquisadores e estudantes na pesquisa e seleção de materiais metálicos conforme requisitos informados pelo usuário.

O fluxo previsto reúne quatro responsabilidades: pesquisa inicial de candidatos; avaliação dos requisitos técnicos e prioridades; verificação da composição química; e consolidação em um relatório com fontes, condições, justificativas e lacunas.

A interface planejada permitirá criar e consultar pesquisas, comparar materiais e conversar com um assistente sobre cada projeto. A pesquisa original será preservada: consultas complementares e PDFs solicitados no chat serão separados do registro inicial. Download de relatórios, envio por e-mail e controle de permissões estão previstos para a plataforma. Modelo de IA e eventual ajuste fino permanecem em avaliação.

No longo prazo, o projeto pretende aproximar IA, métodos computacionais e investigação experimental de materiais no Brasil.

## O que este repositório entrega

Este repositório contém **somente o site de apresentação**, não o sistema de agentes. A experiência interativa é conceitual e está identificada como tal na página. Não há backend, pesquisa real, login, envio de e-mails ou coleta de dados pessoais.

## Executar localmente

Abra `index.html` no navegador. Opcionalmente, com Python instalado:

```sh
python -m http.server 8000
```

Acesse `http://localhost:8000`. Não há dependências, instalação ou compilação.

## Publicar na Vercel

1. Crie um repositório no GitHub e envie o **conteúdo desta pasta**, com `index.html` na raiz do repositório.
2. Na Vercel, importe esse repositório para um novo projeto.
3. Use o preset **Other**; sem comando de instalação e sem comando de build. O diretório de saída é a raiz do projeto (`.`).
4. Faça o deploy. A Vercel fornecerá o endereço HTTPS para compartilhar com a organização.

O arquivo `vercel.json` contém configurações opcionais de URLs e cabeçalhos. Não é necessário fornecer chaves de API ou variáveis de ambiente para esta página. Caso a pasta inteira seja enviada dentro de outro repositório, selecione `daedalus-lab` como Root Directory.

## Arquivos e edição

- `index.html`: textos, seções, metadados e perguntas frequentes.
- `styles.css`: paleta, layout e ajustes para celular.
- `script.js`: navegação móvel e abas da demonstração.
- `assets/logo-daedalus.png`: logo escolhida, em azul e titânio.
- `assets/favicon.svg`: ícone simplificado da aba do navegador.
- `vercel.json`: configuração de hospedagem.

Antes de divulgar, confira o texto e atualize o status de desenvolvimento conforme a implementação real. A página não contém links fictícios para produto, repositório ou redes sociais.

## Acessibilidade

HTML semântico, navegação por teclado, link para pular ao conteúdo, foco visível, menu com estado acessível, abas com setas/Home/End e respeito à preferência de movimento reduzido.

## Autor

Murilo Rosa — Daedalus Lab.
