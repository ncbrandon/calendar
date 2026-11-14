'use strict';
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const params=new URLSearchParams(location.search), view=params.get('screen')||'both';
if(view!=='both')document.body.classList.add('single');
let S=null, events=[], csrf='', online=false, activeField=null, shift=false, mediaDismissed='';
let touchKeyboard=params.get('touch')==='1'||matchMedia('(pointer:coarse)').matches;
const D=s=>new Date(s+'T12:00:00Z'), iso=d=>d.toISOString().slice(0,10);
function addDays(s,n){let d=D(s);d.setUTCDate(d.getUTCDate()+n);return iso(d)}
function weekday(s){return (D(s).getUTCDay()+6)%7}
function monthAdd(s,n){let d=D(s+'-01');d.setUTCMonth(d.getUTCMonth()+n);return iso(d).slice(0,7)}
function weekStart(s){return addDays(s,-((weekday(s)-3+7)%7))}
function assigned(s){const start=weekStart(s), n=Math.round((D(start)-D('2026-11-12'))/86400000/7);return S.days[s]||S.weeks[start]||['Jody','Marcus'][((n%2)+2)%2]}
function toast(message){$('#toast').textContent=message;$('#toast').hidden=false;clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('#toast').hidden=true,6000)}
async function api(path,body,method='POST'){
 const options={method:body===undefined?'GET':method,headers:{}};
 if(body!==undefined){options.headers={'Content-Type':'application/json','X-CSRF-Token':csrf};options.body=JSON.stringify(body)}
 const r=await fetch(path,options);let data;try{data=await r.json()}catch{throw Error('Server returned an unreadable response.')}
 if(!r.ok){if(r.status===401&&path!=='/api/login')showLogin();throw Error(data.error||'Request failed')}
 return data;
}
function showLogin(){if(!$('#login').open)$('#login').showModal();online=false}
function setStatus(ok){online=ok;$('#connection').textContent=ok?'● Connected':'● OFFLINE — showing last loaded calendar';$('#connection').style.color=ok?'#46795b':'#b34e36'}
async function refresh(force=false){
 if(!csrf)return;
 try{
  const next=await api('/api/state'); S=next;setStatus(true);
  const start=addDays(S.wall_month+'-01',-7), end=addDays(monthAdd(S.wall_month,2)+'-01',7);
  events=await api(`/api/events?start=${start}&end=${end}`);
  if(force||(!$('#editor').open&&!document.activeElement?.classList.contains('responsibility')))render();
  updateAmbient();$('#sync').textContent=' · Synced '+new Date().toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'});
 }catch(e){setStatus(false);if(force)toast(e.message)}
}
function render(){
 $('#site-title').textContent=S.settings.title;document.title=S.settings.title;
 const pending=S.requirements.filter(r=>r.stage!=='Complete'), draft=pending.filter(r=>!r.reviewed), overdue=pending.filter(r=>r.window_end<S.today);
 $('#sample-count').textContent=pending.length;
 $('#notice').className=draft.length||overdue.length?'show':'';
 $('#notice').textContent=`${draft.length} sampling requirements need record review. ${overdue.length?overdue.length+' windows have ended; verify completion records. ':''}D01 excluded · Bottle requests: Wednesday before collection week.`;
 $('#current-worker').textContent=assigned(S.today);
 $('#calendars').innerHTML=(view==='left'?[0]:view==='right'?[1]:[0,1]).map(offset=>monthHTML(monthAdd(S.wall_month,offset),offset)).join('');
 $$('.date-button').forEach(b=>b.onclick=()=>dayDetail(b.dataset.date));
 $$('.event[data-req]').forEach(b=>b.onclick=()=>requirementEditor(Number(b.dataset.req)));
 $$('.event[data-event]').forEach(b=>b.onclick=()=>eventEditor(events.find(e=>e.id===Number(b.dataset.event))));
 $$('.more').forEach(b=>b.onclick=()=>dayDetail(b.dataset.date));
 $$('.responsibility').forEach(sel=>sel.onchange=()=>assignmentEditor(sel.dataset.date,sel.value));
}
function monthHTML(month,offset){
 const visibleCount=view==='both'?3:2;
 const first=month+'-01', start=addDays(first,-((weekday(first)+1)%7));
 const name=D(first).toLocaleDateString('en-US',{month:'long',timeZone:'UTC'}), year=month.slice(0,4);
 let html=`<section class="month"><div class="month-heading"><h2>${name} <span>${year}</span></h2><span class="eyebrow">${month===S.today.slice(0,7)?'THIS MONTH':offset?'UP NEXT':'BROWSING'}</span></div><div class="weekdays">${['SUN','MON','TUE','WED','THU','FRI','SAT'].map(x=>`<div>${x}</div>`).join('')}</div><div class="days">`;
 for(let i=0;i<42;i++){
  const d=addDays(start,i), outside=d.slice(0,7)!==month, dayEvents=events.filter(e=>e.date===d), person=assigned(d), override=S.days[d]||S.weeks[weekStart(d)];
  html+=`<div class="day ${outside?'outside':''} ${[5,6].includes(weekday(d))?'weekend':''} ${d===S.today?'today':''}"><button class="date-button" data-date="${d}" aria-label="Open ${d}">${Number(d.slice(-2))}</button><div class="day-events">${dayEvents.slice(0,visibleCount).map(e=>`<button class="event ${esc(e.kind)}" ${e.requirement_id?`data-req="${e.requirement_id}"`:e.id?`data-event="${e.id}"`:''} title="${esc(e.title)}">${esc(e.time?e.time+' ':'')}${esc(e.title)}</button>`).join('')}${dayEvents.length>visibleCount?`<button class="more" data-date="${d}">+${dayEvents.length-visibleCount} more</button>`:''}</div><select class="responsibility ${override?'overridden':''}" data-date="${d}" aria-label="Responsible employee ${d}">${['Jody','Marcus','Brandon'].map(p=>`<option ${p===person?'selected':''}>${p}</option>`).join('')}</select></div>`;
 }
 return html+'</div></section>';
}
function modal(title,html){$('#editor-title').textContent=title;$('#editor-body').innerHTML=html;if(!$('#editor').open)$('#editor').showModal();closeKeyboard()}
function closeEditor(){$('#editor').close();closeKeyboard();refresh(true)}
$('#close-editor').onclick=closeEditor;
function field(label,name,value='',type='text',extra=''){return `<label>${label}<input type="${type}" name="${name}" value="${esc(value)}" ${extra}></label>`}
function selectField(label,name,options,value){return `<label>${label}<select name="${name}">${options.map(o=>{let [v,t]=Array.isArray(o)?o:[o,o];return `<option value="${esc(v)}" ${v===value?'selected':''}>${esc(t)}</option>`}).join('')}</select></label>`}
function formObject(form){return Object.fromEntries(new FormData(form))}
function submit(form,fn){form.onsubmit=async e=>{e.preventDefault();const button=form.querySelector('[type=submit]');button.disabled=true;try{await fn(formObject(form));closeEditor();toast('Saved')}catch(error){toast(error.message)}finally{button.disabled=false}}}
function dayDetail(date){
 const list=events.filter(e=>e.date===date);
 modal(D(date).toLocaleDateString('en-US',{weekday:'long',month:'long',day:'numeric',year:'numeric',timeZone:'UTC'}),`<p>Responsible: <strong>${esc(assigned(date))}</strong> · Duty week ${weekStart(date)} through ${addDays(weekStart(date),6)}</p><div id="day-list">${list.map((e,i)=>`<button class="event ${esc(e.kind)}" data-index="${i}">${esc(e.title)}${e.notes?` — ${esc(e.notes)}`:''}</button>`).join('')||'<p class="hint">No events yet.</p>'}</div><div class="actions"><button class="primary" id="day-add">＋ Add event</button><button id="day-assign">Change coverage</button></div>`);
 $('#day-add').onclick=()=>eventEditor({date});$('#day-assign').onclick=()=>assignmentEditor(date,assigned(date));
 $$('#day-list button').forEach(b=>b.onclick=()=>{const e=list[Number(b.dataset.index)];if(e.requirement_id)requirementEditor(e.requirement_id);else if(e.id)eventEditor(e)});
}
function eventEditor(e={}){
 const editing=!!e.id, record={...e,date:e.series_date||e.date||S.today};
 modal(editing?'Edit event series':'New event',`<form id="event-form" class="grid-form">${field('Title','title',record.title||'')}${selectField('Category','kind',['general','maintenance','holiday','weekend','payroll'],record.kind||'general')}${field('Starts','date',record.date,'date','required')}${field('Ends (optional)','end_date',record.end_date||'','date')}${field('Time (optional)','time',record.time||'','time')}${selectField('Assigned employee','employee',[['','Duty employee'],'Jody','Marcus','Brandon'],record.employee||'')}${selectField('Repeat','repeat',[['none','Does not repeat'],['weekly','Weekly'],['monthly','Monthly'],['yearly','Yearly']],record.repeat||'none')}${field('Repeat until (optional)','repeat_until',record.repeat_until||'','date')}<label class="wide">Notes<textarea name="notes">${esc(record.notes||'')}</textarea></label><div class="actions wide"><button type="submit" class="primary">Save event</button>${editing?'<button type="button" id="delete-event" class="danger">Delete entire series</button>':''}</div></form>`);
 submit($('#event-form'),async b=>{if(editing){b.id=e.id;b.revision=e.revision||0}await api('/api/events',b)});
 if(editing)$('#delete-event').onclick=async()=>{if(confirm('Delete this entire event series?')){await api('/api/events/'+e.id,{},'DELETE');closeEditor()}};
}
function assignmentEditor(date,person){
 modal('Duty coverage',`<p><b>${date}</b> · ${esc(person)}</p><p class="hint">Weekly assignments cover Thursday through Wednesday. Brandon coverage never shifts the underlying Jody/Marcus rotation.</p><form id="assign-form">${selectField('Employee','person',['Jody','Marcus','Brandon'],person)}${selectField('Apply to','scope',[['day','This day only'],['week',`Whole duty week: ${weekStart(date)} → ${addDays(weekStart(date),6)}`]],weekday(date)===3?'week':'day')}<div class="actions"><button class="primary" type="submit">Save coverage</button><button type="button" id="reset-assignment">Restore automatic assignment</button></div></form>`);
 submit($('#assign-form'),b=>api('/api/assignments',{date,...b}));
 $('#reset-assignment').onclick=async()=>{const scope=$('#assign-form [name=scope]').value;await api('/api/assignments',{date,scope,person:null});closeEditor()};
}
function samplesPanel(){
 const reqs=S.requirements, pending=reqs.filter(r=>r.stage!=='Complete'), amounts={};
 reqs.forEach(r=>{if(r.planned&&r.cost!==null){const y=r.planned.slice(0,4);amounts[y]=(amounts[y]||0)+r.cost}});
 modal('Sampling planner',`<div class="summary"><div class="stat"><b>${pending.length}</b><span>OPEN REQUIREMENTS</span></div><div class="stat"><b>${pending.filter(r=>!r.reviewed).length}</b><span>NEED REVIEW</span></div>${Object.entries(amounts).map(([y,v])=>`<div class="stat"><b>$${v.toLocaleString()}</b><span>${y} PLANNED ESTIMATE</span></div>`).join('')}</div><div class="alert">Source: Drinking Water Watch, November 14, 2026. Zero / unsatisfied in the source is a record to verify, not a finding of a missed sample. D01 excluded. Review windows, panel coverage, and costs before planning.</div><div class="toolbar"><input id="sample-search" placeholder="Filter by P-code, group, or status" aria-label="Filter samples"><button id="propose" class="primary">Balance unplanned samples</button><button id="new-requirement">＋ Requirement</button></div><div class="table-wrap"><table><thead><tr><th>Location / group</th><th>Window ends</th><th>Collection</th><th>Estimate</th><th>Status</th><th></th></tr></thead><tbody id="sample-rows">${reqs.map(r=>`<tr data-search="${esc((r.facility+' '+r.group+' '+r.stage).toLowerCase())}"><td><b>${r.facility}</b> · ${esc(r.group)}<br><small>${r.years}-year cycle</small></td><td>${r.window_end}</td><td>${r.planned||'—'}</td><td>${r.cost===null?'Not entered':'$'+r.cost.toLocaleString()}</td><td><span class="badge ${!r.reviewed?'warn':''}">${!r.reviewed?'Verify records':esc(r.stage)}</span></td><td><button class="small req-open" data-id="${r.id}">Open</button></td></tr>`).join('')}</tbody></table></div>`);
 $('#sample-search').oninput=e=>$$('#sample-rows tr').forEach(tr=>tr.hidden=!tr.dataset.search.includes(e.target.value.toLowerCase()));
 $$('.req-open').forEach(b=>b.onclick=()=>requirementEditor(Number(b.dataset.id)));
 $('#new-requirement').onclick=()=>requirementEditor(null);$('#propose').onclick=showProposals;
}
function requirementEditor(id){
 const r=id?S.requirements.find(r=>r.id===id):{facility:'P03',group:'',window_start:S.today,window_end:S.today,years:1,cost:null,reviewed:false,planned:null,actual:null,stage:'Verify records',source:'Manual entry — attach source document',notes:'',source_status:'Manual entry',count:1};
 modal(`${r.facility} · ${r.group||'New requirement'}`,`<div class="alert">${esc(r.source)}<br>${esc(r.source_status)}. Keep collection constraints in the window dates and notes. A panel task may require multiple bottles.</div><form id="requirement-form" class="grid-form">${selectField('Location','facility',['P03','P04','P05','P07','P08','P10','P11','P12'],r.facility)}${field('Sample group','group',r.group,'text','required')}${field('Earliest allowed collection','window_start',r.window_start,'date','required')}${field('Latest allowed collection','window_end',r.window_end,'date','required')}${field('Recurrence (years)','years',r.years,'number','min="1" max="20" required')}${field('Estimated total cost ($)','cost',r.cost??'','number','min="0" step="0.01"')}${field('Planned collection','planned',r.planned||'','date')}${field('Actual collection','actual',r.actual||'','date')}${selectField('Progress','stage',S.stages,r.stage)}${field('Source / document reference','source',r.source)}<label class="check"><input name="reviewed" type="checkbox" ${r.reviewed?'checked':''}>I verified the records, collection window, and panel coverage.</label><label class="wide">Notes / laboratory constraints<textarea name="notes">${esc(r.notes)}</textarea></label><p class="hint wide">Order bottles: Wednesday before the planned collection week. Confirm receipt before pulling samples. Mark Complete only after accepted results and any required reporting are resolved. Future periods require a new review.</p><div class="actions wide"><button class="primary" type="submit">Save requirement</button>${id?'<button type="button" id="next-period">Open next monitoring period</button>':''}<button type="button" id="back-samples">Back to planner</button></div></form>`);
 submit($('#requirement-form'),async b=>{await api('/api/requirements',{...r,...b,reviewed:$('#requirement-form [name=reviewed]').checked,years:Number(b.years),cost:b.cost===''?null:Number(b.cost),planned:b.planned||null,actual:b.actual||null})});
 $('#back-samples').onclick=samplesPanel;
 if(id)$('#next-period').onclick=async()=>{try{await api('/api/requirements/next',{id});await refresh();samplesPanel();toast('New draft period opened; verify against current schedule.')}catch(e){toast(e.message)}};
}
async function showProposals(){
 try{
 const proposals=await api('/api/plan',{}), reqs=Object.fromEntries(S.requirements.map(r=>[r.id,r]));
 modal('Review proposed collection dates',`<p class="hint">Only reviewed, unplanned requirements are considered. Estimated costs balance by calendar month within approved windows. Aim: weekdays, two weeks’ notice, and a 90-day repeat-sampling buffer when possible. Actual bottle arrival must be confirmed. These are proposals until you apply them.</p><div class="table-wrap"><table><thead><tr><th>Requirement</th><th>Request bottles</th><th>Collect</th><th>Estimate / conflict</th></tr></thead><tbody>${proposals.map(p=>`<tr><td>${reqs[p.id].facility} · ${esc(reqs[p.id].group)}</td><td>${p.order||'—'}</td><td>${p.planned||'—'}</td><td>${p.conflict?esc(p.conflict):'$'+p.cost.toLocaleString()}</td></tr>`).join('')}</tbody></table></div>${!proposals.length?'<p>No reviewed, unplanned requirements. Review records and enter costs first.</p>':''}<div class="actions"><button id="apply-plan" class="primary" ${proposals.some(p=>p.planned)?'':'disabled'}>Apply feasible proposals</button><button id="back-planner">Back</button></div>`);
 $('#back-planner').onclick=samplesPanel;
 $('#apply-plan').onclick=async()=>{try{await api('/api/plan/apply',{proposals:proposals.filter(p=>p.planned)});closeEditor();toast('Collection dates and bottle tasks saved')}catch(e){toast(e.message)}};
 }catch(e){toast(e.message)}
}
function libraryPanel(){
 modal('Documents & scheduled media',`<p class="hint">Upload permits and schedules for reference. Enter verified requirements in Samples; this version does not automatically interpret new permits. Upload GIFs, images, MP4, or WebM for scheduled playback. Maximum 80 MB per file.</p><label>Upload document or media<input id="upload" type="file" accept=".pdf,.txt,.md,.csv,.gif,.png,.jpg,.jpeg,.webp,.mp4,.webm"></label><p id="upload-status" class="hint"></p><div>${S.files.map(f=>`<div class="file"><a href="${esc(f.url)}" target="_blank" rel="noopener">${esc(f.name)}</a><small>${(f.bytes/1024/1024).toFixed(2)} MB</small>${f.kind==='media'?`<button class="small schedule-file" data-id="${f.id}">Schedule</button>`:''}</div>`).join('')||'<p class="hint">No uploaded files.</p>'}</div><h3>Media schedule</h3>${S.media.map(m=>`<div class="file"><span>${esc(m.name)} · ${m.start} → ${m.end} · ${m.screen}</span><button class="small remove-media" data-id="${m.id}">Remove schedule</button></div>`).join('')||'<p class="hint">No scheduled media.</p>'}`);
 $('#upload').onchange=async e=>{
 const f=e.target.files[0];if(!f)return;if(f.size>80*1024*1024){toast('Maximum file size is 80 MB');return}
 $('#upload-status').textContent='Uploading…';
 try{const res=await fetch('/api/upload',{method:'POST',headers:{'X-CSRF-Token':csrf,'X-Filename':encodeURIComponent(f.name),'Content-Type':'application/octet-stream'},body:f});const data=await res.json();if(!res.ok)throw Error(data.error);await refresh();libraryPanel();toast('Uploaded')}catch(err){$('#upload-status').textContent=err.message}
 };
 $$('.schedule-file').forEach(b=>b.onclick=()=>mediaEditor(Number(b.dataset.id)));
 $$('.remove-media').forEach(b=>b.onclick=async()=>{await api('/api/media/'+b.dataset.id,{},'DELETE');await refresh();libraryPanel()});
}
function mediaEditor(file_id){
 const f=S.files.find(f=>f.id===file_id);
 modal('Schedule '+f.name,`<form id="media-form" class="grid-form">${field('First date (inclusive)','start',S.today,'date','required')}${field('Last date (inclusive)','end',S.today,'date','required')}${selectField('Display on','screen',[['both','Both screens'],'left','right'],'both')}${selectField('Play when','condition',[['always','Always within dates'],['snow','Snow / winter fallback'],['rain','Rain'],['leaves','Autumn fallback'],['clear','Clear conditions']],'always')}<p class="hint">Media plays muted in a floating panel during work hours. If schedules overlap, the most recently added matching schedule wins. Close the panel temporarily to expose the calendar underneath.</p><button class="primary" type="submit">Schedule playback</button></form>`);
 submit($('#media-form'),b=>api('/api/media',{file_id,...b}));
}
function settingsPanel(){
 const s=S.settings, days=['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'];
 modal('Calendar & display settings',`<form id="settings-form" class="grid-form">${field('Calendar title','title',s.title)}${field('Facility timezone','timezone',s.timezone)}${field('Screens on','on',s.on,'time')}${field('Screens off','off',s.off,'time')}<div class="wide"><label>Active weekdays</label><div class="toolbar">${days.map((d,i)=>`<label class="check"><input type="checkbox" name="day-${i}" ${s.workdays.includes(i)?'checked':''}>${d.slice(0,3)}</label>`).join('')}</div></div>${selectField('Seasonal effects','effects',[['off','Off'],['seasonal','Seasonal leaves / snow'],['weather','Current weather (coordinates required)'],'leaves','snow','rain'],s.effects)}${field('Monthly sampling budget ($, optional)','monthly_budget',s.monthly_budget??'','number','min="0" step="0.01"')}${field('Weather latitude (optional)','latitude',s.latitude??'','number','step="any"')}${field('Weather longitude (optional)','longitude',s.longitude??'','number','step="any"')}<label class="check"><input name="holidays" type="checkbox" ${s.holidays?'checked':''}>Show federal reference holidays</label><label class="check"><input name="payroll_enabled" type="checkbox" ${s.payroll_enabled?'checked':''}>Show weekly payroll markers</label>${selectField('Payroll week starts','payroll_start',days.map((d,i)=>[String(i),d]),String(s.payroll_start))}${selectField('Payday','payday',days.map((d,i)=>[String(i),d]),String(s.payday))}<label class="wide">Closure dates (one YYYY-MM-DD per line)<textarea name="dark_dates">${esc(s.dark_dates.join('\n'))}</textarea></label><label class="check wide"><input id="touch-toggle" type="checkbox" ${touchKeyboard?'checked':''}>On-screen keyboard on this browser</label><p class="hint wide">Payroll is disabled until you confirm its boundaries. Duty rotation always starts Thursday. Display sleep needs the supplied kiosk power script; browser-only mode uses a black overlay. Weather uses Open-Meteo and falls back to seasonal effects when stale.</p><div class="actions wide"><button class="primary" type="submit">Save settings</button><button type="button" id="backup">Download full backup</button></div></form>`);
 submit($('#settings-form'),async b=>{
 const form=$('#settings-form');const workdays=days.map((_,i)=>i).filter(i=>form.querySelector(`[name=day-${i}]`).checked);
 const data={...b,workdays,holidays:form.querySelector('[name=holidays]').checked,payroll_enabled:form.querySelector('[name=payroll_enabled]').checked,payroll_start:Number(b.payroll_start),payday:Number(b.payday),dark_dates:b.dark_dates.split(/\s+/).filter(Boolean)};
 for(const k of ['latitude','longitude','monthly_budget'])data[k]=b[k]===''?null:Number(b[k]);
 await api('/api/settings',data);touchKeyboard=$('#touch-toggle').checked;
 });
 $('#backup').onclick=()=>location.href='/api/backup';
}
function exportPanel(){
 modal('Export Markdown records',`<form id="export-form" class="grid-form">${field('From','start',S.wall_month+'-01','date','required')}${field('Through','end',addDays(monthAdd(S.wall_month,2)+'-01',-1),'date','required')}<p class="hint wide">Includes daily crew assignments, events, sample milestones, and the requirement register. Choose past, current, or future dates, up to ten years. Documents and media are included in full backups, not embedded in Markdown.</p><button class="primary" type="submit">Download .md</button></form>`);
 $('#export-form').onsubmit=e=>{e.preventDefault();const b=formObject(e.target);if(b.end<b.start){toast('End must follow start');return}location.href=`/api/export?start=${b.start}&end=${b.end}`};
}
async function navigate(amount){if(!S)return;try{await api('/api/navigation',{month:amount===null?null:monthAdd(S.wall_month,amount)});await refresh(true)}catch(e){toast(e.message)}}
$('#previous').onclick=()=>navigate(-1);$('#next').onclick=()=>navigate(1);$('#today').onclick=()=>navigate(null);
$('#add').onclick=()=>S&&eventEditor();$('#samples').onclick=()=>S&&samplesPanel();$('#library').onclick=()=>S&&libraryPanel();$('#settings').onclick=()=>S&&settingsPanel();$('#export').onclick=()=>S&&exportPanel();
$('#logout').onclick=async()=>{try{await api('/api/logout',{});csrf='';S=null;$('#calendars').innerHTML='';showLogin()}catch(e){toast(e.message)}};
$('#login-form').onsubmit=async e=>{e.preventDefault();try{const r=await api('/api/login',{password:$('#password').value});csrf=r.csrf;$('#password').value='';$('#login').close();closeKeyboard();await refresh(true)}catch(err){$('#login-error').textContent=err.message}};
$('#login').addEventListener('cancel',e=>e.preventDefault());
$('#wake').onclick=async()=>{try{await api('/api/wake',{});await refresh(true)}catch(e){toast(e.message)}};
function currentCondition(){
 const w=S?.weather, month=Number(S?.today.slice(5,7));
 if(w?.current&&!w.stale){const c=w.current.weather_code;if([71,73,75,77,85,86].includes(c))return 'snow';if([51,53,55,56,57,61,63,65,66,67,80,81,82,95,96,99].includes(c))return 'rain';return 'clear'}
 return month>=9&&month<=11?'leaves':month===12||month<=2?'snow':'clear';
}
function updateAmbient(){
 if(!S)return;
 const s=S.settings; const dt=new Intl.DateTimeFormat('en-US',{timeZone:s.timezone,weekday:'short',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(new Date());
 const parts=Object.fromEntries(dt.map(p=>[p.type,p.value]));const time=parts.hour+':'+parts.minute;
 const workday=['Mon','Tue','Wed','Thu','Fri','Sat','Sun'].indexOf(parts.weekday);
 const today=new Intl.DateTimeFormat('en-CA',{timeZone:s.timezone,year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
 const active=(s.workdays.includes(workday)&&time>=s.on&&time<s.off&&!s.dark_dates.includes(today))||s.wake_until>Date.now()/1000;
 $('#dark').hidden=view==='both'||active;
 $('#clock').textContent=new Intl.DateTimeFormat('en-US',{timeZone:s.timezone,weekday:'short',month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}).format(new Date());
 $('#weather').textContent=S.weather?.current?`${Math.round(S.weather.current.temperature_2m)}°F · ${S.weather.stale?'weather stale':'local weather · Open-Meteo'}`:'';
 if($('#editor').open||!active){$('#media-panel').hidden=true;return}
 const m=[...S.media].reverse().find(m=>m.start<=today&&m.end>=today&&(!m.condition||m.condition==='always'||m.condition===currentCondition())&&(m.screen==='both'||view==='both'||m.screen===view));
 if(m&&String(m.id)!==mediaDismissed){
  const panel=$('#media-panel');if(panel.dataset.media!==String(m.id)){
   panel.dataset.media=m.id;const video=/\.(mp4|webm)$/i.test(m.url);
   panel.innerHTML=`${video?`<video src="${esc(m.url)}" autoplay muted loop playsinline></video>`:`<img src="${esc(m.url)}" alt="${esc(m.name)}">`}<button id="dismiss-media" aria-label="Dismiss media">×</button>`;
   $('#dismiss-media').onclick=()=>{mediaDismissed=String(m.id);panel.hidden=true};
  }panel.hidden=false;
 }else $('#media-panel').hidden=true;
}
// App-controlled touch keyboard works in Chromium even when the OS has no keyboard.
function closeKeyboard(){if($('#keyboard').matches(':popover-open'))$('#keyboard').hidePopover();$('#keyboard').hidden=true;document.body.classList.remove('keyboard-open');activeField=null}
$('#keyboard-close').onclick=closeKeyboard;
function drawKeys(){
 const rows=['1234567890','qwertyuiop','asdfghjkl','zxcvbnm'];
 $('#keys').innerHTML=rows.map((row,i)=>`<div class="key-row">${i===3?'<button type="button" data-key="SHIFT">⇧</button>':''}${[...row].map(k=>`<button type="button" data-key="${k}">${shift?k.toUpperCase():k}</button>`).join('')}${i===0?'<button type="button" data-key="BACK">⌫</button>':''}</div>`).join('')+'<div class="key-row">'+['-','_','/',':','.',',','@','!','?'].map(k=>`<button type="button" data-key="${k}">${k}</button>`).join('')+'<button type="button" class="space" data-key="SPACE">Space</button></div>';
 $$('#keys button').forEach(b=>b.onpointerdown=e=>{
  e.preventDefault();if(!activeField)return;let k=b.dataset.key;if(k==='SHIFT'){shift=!shift;drawKeys();return}
  const f=activeField;let start=f.selectionStart??f.value.length,end=f.selectionEnd??start;
  if(k==='BACK'){if(start===end)start=Math.max(0,start-1);k=''}else if(k==='SPACE')k=' ';else if(shift)k=k.toUpperCase();
  f.value=f.value.slice(0,start)+k+f.value.slice(end);f.focus();try{f.setSelectionRange(start+k.length,start+k.length)}catch{}
  f.dispatchEvent(new Event('input',{bubbles:true}));
 });
}
document.addEventListener('focusin',e=>{
 if(!touchKeyboard)return;const el=e.target;
 if(el.tagName==='TEXTAREA'||(el.tagName==='INPUT'&&['text','password','search','number'].includes(el.type))){activeField=el;const kb=$('#keyboard');(el.closest('dialog')||document.body).append(kb);kb.hidden=false;if(!kb.matches(':popover-open'))kb.showPopover();document.body.classList.add('keyboard-open');drawKeys();setTimeout(()=>el.scrollIntoView({block:'center',behavior:'smooth'}),80)}
});
// Low-cost effects never intercept touches. Honor OS reduced-motion preference.
const canvas=$('#effects'), ctx=canvas.getContext('2d');let particles=[], frame=0;
function resize(){canvas.width=innerWidth;canvas.height=innerHeight;particles=Array.from({length:30},()=>({x:Math.random()*innerWidth,y:Math.random()*innerHeight,s:2+Math.random()*4,v:.4+Math.random(),phase:Math.random()*6}))}addEventListener('resize',resize);resize();
function animate(){requestAnimationFrame(animate);if(++frame%2)return;ctx.clearRect(0,0,canvas.width,canvas.height);if(!S||!$('#dark').hidden||$('#editor').open||$('#login').open||matchMedia('(prefers-reduced-motion:reduce)').matches)return;
 let effect=S.settings.effects;const month=Number(S.today.slice(5,7));const seasonal=month>=9&&month<=11?'leaves':month===12||month<=2?'snow':'off';
 if(effect==='seasonal')effect=seasonal;
 if(effect==='weather'){
  const w=S.weather;effect=seasonal;
  if(w?.current&&!w.stale){const code=w.current.weather_code;effect=([71,73,75,77,85,86].includes(code))?'snow':([51,53,55,56,57,61,63,65,66,67,80,81,82,95,96,99].includes(code))?'rain':seasonal}
 }
 if(effect==='off')return;
 for(const p of particles){p.y+=p.v*(effect==='rain'?9:1);p.x+=Math.sin(p.y/90+p.phase)*.45;if(p.y>canvas.height+12){p.y=-12;p.x=Math.random()*canvas.width}
 ctx.save();ctx.translate(p.x,p.y);
 if(effect==='leaves'){ctx.rotate(p.y/80+p.phase);ctx.fillStyle=['#b97839','#b09b42','#cb8b4f'][Math.floor(p.s)%3];ctx.beginPath();ctx.ellipse(0,0,p.s,p.s*1.8,.5,0,Math.PI*2);ctx.fill()}
 else if(effect==='rain'){ctx.strokeStyle='#7698a7';ctx.beginPath();ctx.moveTo(0,0);ctx.lineTo(-2,12);ctx.stroke()}
 else{ctx.strokeStyle='#91aeb3';ctx.lineWidth=.8;ctx.rotate(p.phase+p.y/180);for(let arm=0;arm<6;arm++){ctx.rotate(Math.PI/3);ctx.beginPath();ctx.moveTo(0,0);ctx.lineTo(0,p.s*1.5);ctx.moveTo(0,p.s);ctx.lineTo(-p.s*.4,p.s*.65);ctx.moveTo(0,p.s);ctx.lineTo(p.s*.4,p.s*.65);ctx.stroke()}}ctx.restore();
 }
}animate();
(async()=>{try{csrf=(await api('/api/session')).csrf;await refresh(true)}catch{showLogin()}})();
setInterval(()=>refresh(),10000);setInterval(updateAmbient,1000);
