const menu = document.querySelector('.menu-toggle');
const nav = document.querySelector('#nav');
menu.addEventListener('click', () => {
  const open = menu.getAttribute('aria-expanded') !== 'true';
  menu.setAttribute('aria-expanded', String(open));
  menu.setAttribute('aria-label', open ? 'Fechar navegação' : 'Abrir navegação');
  nav.classList.toggle('open', open);
});
nav.querySelectorAll('a').forEach(link => link.addEventListener('click', () => {
  nav.classList.remove('open'); menu.setAttribute('aria-expanded', 'false');
  menu.setAttribute('aria-label', 'Abrir navegação');
}));
const panels = {
  pesquisa: {title:'Comece pelo que seu projeto precisa.', description:'Informe a aplicação, as condições de operação e os critérios que orientam a seleção.', content:document.querySelector('#panel-content').innerHTML},
  comparacao: {title:'Compare com os mesmos critérios.', description:'Os resultados deverão explicitar o atendimento aos requisitos e a disponibilidade de evidências.', content:'<table class="mini-table"><caption>Exemplo ilustrativo, sem dados de materiais reais</caption><thead><tr><th>CANDIDATO</th><th>REQUISITO TÉCNICO</th><th>COMPOSIÇÃO</th></tr></thead><tbody><tr><td>Material A</td><td>Atende</td><td>Dados insuficientes</td></tr><tr><td>Material B</td><td>Não atende</td><td>Atende</td></tr></tbody></table><div class="sample-note">Cada conclusão deverá estar vinculada às suas fontes e condições.</div>'},
  chat: {title:'Aprofunde a conversa. Preserve a pesquisa.', description:'Um assistente com o contexto do projeto para explicar resultados e investigar dúvidas complementares.', content:'<div class="chat-bubble">Quais informações faltam para avaliar este candidato?</div><div class="chat-bubble">O assistente poderá identificar lacunas, buscar fontes adicionais e apresentar alternativas, sem alterar o registro original.</div><div class="sample-note">Conteúdos complementares poderão ser exportados em um PDF separado, quando solicitado.</div>'}
};
const tabs = [...document.querySelectorAll('[role="tab"]')];
function selectTab(tab) {
  tabs.forEach(item => {item.setAttribute('aria-selected',String(item===tab));item.tabIndex=item===tab?0:-1;});
  const data=panels[tab.dataset.tab];
  document.querySelector('#panel-title').textContent=data.title;
  document.querySelector('#panel-description').textContent=data.description;
  document.querySelector('#panel-content').innerHTML=data.content;
  document.querySelector('#painel').setAttribute('aria-labelledby',tab.id);
}
tabs.forEach((tab,index)=>{
  tab.addEventListener('click',()=>selectTab(tab));
  tab.addEventListener('keydown',event=>{
    let next;
    if(['ArrowRight','ArrowDown'].includes(event.key)) next=(index+1)%tabs.length;
    if(['ArrowLeft','ArrowUp'].includes(event.key)) next=(index+tabs.length-1)%tabs.length;
    if(event.key==='Home') next=0;
    if(event.key==='End') next=tabs.length-1;
    if(next!==undefined){event.preventDefault();tabs[next].focus();selectTab(tabs[next]);}
  });
});
