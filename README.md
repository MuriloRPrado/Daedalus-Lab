# Daedalus Lab — Pesquisa de Materiais Metálicos

## Sobre o projeto

O Daedalus Lab é um sistema multiagente focado em apoiar a pesquisa e a seleção de materiais metálicos a partir de requisitos informados pelo usuário.

A proposta é integrar agentes de inteligência artificial a ferramentas de consulta em bases de materiais, documentos técnicos e artigos de acesso aberto. Os resultados serão apresentados com fontes, justificativas, condições das propriedades e indicação de informações ausentes ou conflitantes, permitindo que o usuário confira as evidências utilizadas.

## Problema e objetivo

A seleção de materiais envolve propriedades, composição química, condições de operação, tratamentos e processos de fabricação. Essas informações podem estar distribuídas entre diferentes fontes e nem sempre são diretamente comparáveis.

O Daedalus Lab pretende facilitar a localização e a organização dessas informações, apoiando a comparação de candidatos e a identificação de pendências que precisam ser investigadas. Espera-se reduzir o esforço dedicado à pesquisa e contribuir para decisões mais fundamentadas. Esses benefícios serão avaliados durante o desenvolvimento e os testes do sistema.

## Público-alvo

O projeto pretende atender:

- Engenheiros de produto que pesquisam materiais para componentes e equipamentos.
- Profissionais de pesquisa e desenvolvimento que avaliam alternativas de materiais.
- Pesquisadores e estudantes envolvidos em estudos de seleção e aplicação de materiais metálicos.

## Funcionalidades previstas

O sistema contará com uma interface para cadastrar projetos, definir requisitos, iniciar pesquisas e consultar resultados anteriores.

Em cada pesquisa, o usuário poderá visualizar os materiais encontrados, comparar suas características, consultar as fontes e baixar o relatório final.

Os critérios informados serão separados em:

- **Requisitos obrigatórios:** condições que os materiais precisam atender.
- **Prioridades:** preferências utilizadas para comparar e ordenar os candidatos, como menor massa ou menor custo, quando houver dados suficientes.

Também estão previstos um módulo de gestão de usuários e permissões e a opção de envio do relatório por e-mail. Essas funcionalidades serão implementadas conforme a evolução do projeto.

## Fluxo de pesquisa multiagente

A pesquisa será conduzida por quatro agentes com responsabilidades complementares.

### Agente 1 — Pesquisa e seleção inicial

Responsável por interpretar os requisitos do projeto, pesquisar materiais candidatos e reunir evidências preliminares sobre suas características e possíveis aplicações.

Cada candidato deverá ser identificado com o máximo de precisão disponível, incluindo designação, condição de fornecimento e tratamento, quando pertinentes.

### Agente 2 — Avaliação técnica e comparação

Responsável por avaliar os candidatos encontrados pelo Agente 1 em relação aos requisitos técnicos, além daqueles de composição química tratados pelo Agente 3.

A avaliação considerará propriedades e condições relevantes para a aplicação, classificando cada requisito como atendido, não atendido ou com evidência insuficiente.

O agente também comparará os candidatos conforme as prioridades do usuário, explicando vantagens, limitações e diferenças entre as alternativas. O atendimento aos requisitos obrigatórios terá precedência sobre as preferências.

### Agente 3 — Avaliação da composição química

Responsável por pesquisar a composição química dos candidatos encontrados pelo Agente 1 e verificar sua compatibilidade com as restrições de elementos definidas pelo usuário.

A análise deverá preservar as unidades, os limites de composição e as referências utilizadas, sinalizando informações ausentes ou divergentes.

### Agente 4 — Consolidação e relatório final

Responsável por consolidar os resultados dos três agentes anteriores, identificar inconsistências e organizar o relatório final.

Informações ausentes ou conflitantes deverão permanecer explícitas. A consolidação não deverá tratar a ausência de evidência como confirmação de atendimento a um requisito.

## Resultado da pesquisa

O resultado será salvo como um registro do projeto e incluirá:

- Requisitos obrigatórios e prioridades considerados.
- Materiais candidatos e suas condições relevantes.
- Comparação de propriedades e composição química.
- Avaliação do atendimento aos requisitos.
- Justificativas para a classificação dos candidatos.
- Fontes utilizadas e referências associadas às informações.
- Divergências, limitações e necessidades de investigação adicional.

O usuário poderá consultar esse registro na interface e baixar o relatório correspondente.

## Assistente de conversa por projeto

Cada registro de pesquisa terá um chat contextual para esclarecer dúvidas, explicar comparações e aprofundar a investigação.

O assistente poderá consultar o resultado salvo e utilizar ferramentas de pesquisa complementar quando a pergunta exigir informações adicionais. Caso encontre novos materiais ou evidências, apresentará esses achados na conversa, com suas fontes. **A pesquisa original permanecerá preservada e não será alterada por esse chat.**

O usuário também poderá solicitar um PDF com uma resposta ou análise complementar. Esse documento identificará as fontes, a data e a distinção entre informações da pesquisa original e achados obtidos durante a conversa.

A escolha do modelo de linguagem e a eventual realização de ajuste fino serão avaliadas conforme qualidade das respostas, uso de ferramentas, custo e infraestrutura necessária.

## Avaliação

O sistema será uma ferramenta de apoio à pesquisa e à decisão. A adequação final de um material dependerá da avaliação de engenharia e das validações exigidas pela aplicação.

## Visão de longo prazo

A pesquisa e a seleção de materiais metálicos representam a primeira etapa do Daedalus Lab.

A visão de longo prazo é desenvolver um laboratório que integre inteligência artificial, métodos computacionais e validação experimental para apoiar o estudo e o desenvolvimento de novos materiais, buscando contribuir para a capacidade tecnológica e a inovação da indústria brasileira.