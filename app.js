const DATA_URL = "data/vacancies.json";
const state = {items:[],tab:"all",search:"",status:"all",sort:"new",saved:new Set(JSON.parse(localStorage.getItem("savedVacancies")||"[]"))};
const $ = (id)=>document.getElementById(id);
const esc = (s="")=>String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const money = (v)=>v==null?"Зарплата не указана":new Intl.NumberFormat("ru-RU").format(v)+" ₽";
function dateText(s){if(!s)return "Дата не указана";const d=new Date(s);return isNaN(d)?"Дата не указана":d.toLocaleString("ru-RU",{day:"numeric",month:"short",hour:"2-digit",minute:"2-digit"});}
async function load(){
  $("vacancies").innerHTML='<div class="empty loading">Загружаю вакансии…</div>';
  try{
    const r=await fetch(DATA_URL+"?v="+Date.now(),{cache:"no-store"});
    if(!r.ok)throw new Error("Файл с вакансиями пока не опубликован");
    const d=await r.json();state.items=d.vacancies||[];
    $("updated").textContent=d.updated_at?"Обновлено "+dateText(d.updated_at):"Данные загружены";
    $("count-good").textContent=state.items.filter(x=>x.status==="confirmed").length;
    $("count-check").textContent=state.items.filter(x=>x.status==="review").length;
    const day=Date.now()-86400000;
    $("count-new").textContent=state.items.filter(x=>new Date(x.published_at||0).getTime()>day).length;
    render();
  }catch(e){$("updated").textContent="Ожидает первого запуска";$("vacancies").innerHTML='<div class="empty">Пока нет файла с результатами.<br>После настройки GitHub Actions здесь появятся вакансии.</div>';}
}
function render(){
  let list=state.items.filter(v=>{
    if(state.tab==="kungur"&&v.city!=="Кунгур")return false;
    if(state.tab==="perm"&&v.city!=="Пермь")return false;
    if(state.tab==="saved"&&!state.saved.has(String(v.id)))return false;
    if(state.status!=="all"&&v.status!==state.status)return false;
    const hay=[v.title,v.company,v.description,v.city,v.schedule].join(" ").toLowerCase();
    return hay.includes(state.search.toLowerCase());
  });
  if(state.sort==="salary")list.sort((a,b)=>(b.salary_to||b.salary_from||0)-(a.salary_to||a.salary_from||0));
  else list.sort((a,b)=>new Date(b.published_at||0)-new Date(a.published_at||0));
  const titles={all:"Все вакансии",kungur:"Кунгур",perm:"Пермь",saved:"Избранное"};
  $("section-title").textContent=titles[state.tab];
  $("result-count").textContent=list.length+" вакансий";
  $("saved-count").textContent=state.saved.size;
  if(!list.length){$("vacancies").innerHTML='<div class="empty">Подходящих объявлений пока нет.<br>Попробуй изменить фильтр или загляни позже — поиск обновляется автоматически.</div>';return;}
  $("vacancies").innerHTML=list.map(v=>{
    const good=v.status==="confirmed", saved=state.saved.has(String(v.id));
    const salary=v.salary_from||v.salary_to?`${v.salary_from?money(v.salary_from):"от —"}${v.salary_to?" — "+money(v.salary_to):""}`:"Условия оплаты не указаны";
    return `<article class="vacancy">
      <div class="vac-top"><div><a class="vac-title" href="${esc(v.url)}" target="_blank" rel="noopener">${esc(v.title||"Вакансия")}</a><div class="company">${esc(v.company||"Работодатель не указан")} · ${esc(v.city)}</div></div><span class="status ${good?"confirmed":"review"}">${good?"Условия подтверждены":"Нужно уточнить"}</span></div>
      <div class="salary ${v.salary_from||v.salary_to?"":"muted"}">${esc(salary)}</div>
      <div class="meta"><span class="chip">${esc(v.schedule||"График не указан")}</span><span class="chip">${good?"Без оформления — указано в объявлении":"Оформление требует проверки"}</span><span class="chip">${v.net_confirmed?"На руки подтверждено":"Выплата на руки не подтверждена"}</span></div>
      <p class="description">${esc((v.description||"Описание не предоставлено").slice(0,360))}${(v.description||"").length>360?"…":""}</p>
      <div class="vac-bottom"><span class="date">Опубликовано: ${dateText(v.published_at)}</span><div class="vac-actions"><button class="save ${saved?"saved":""}" data-save="${esc(v.id)}">${saved?"★ Сохранено":"☆ В избранное"}</button><a class="open-link" href="${esc(v.url)}" target="_blank" rel="noopener">Открыть ↗</a></div></div>
    </article>`;
  }).join("");
  document.querySelectorAll("[data-save]").forEach(b=>b.addEventListener("click",()=>{const id=String(b.dataset.save);state.saved.has(id)?state.saved.delete(id):state.saved.add(id);localStorage.setItem("savedVacancies",JSON.stringify([...state.saved]));render();}));
}
document.querySelectorAll(".tab").forEach(b=>b.addEventListener("click",()=>{document.querySelectorAll(".tab").forEach(x=>x.classList.remove("active"));b.classList.add("active");state.tab=b.dataset.tab;render();}));
$("search").addEventListener("input",e=>{state.search=e.target.value;render();});
$("status-filter").addEventListener("change",e=>{state.status=e.target.value;render();});
$("sort").addEventListener("change",e=>{state.sort=e.target.value;render();});
$("refresh").addEventListener("click",load);
load();
