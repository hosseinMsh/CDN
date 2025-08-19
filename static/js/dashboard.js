// ===== Feature toggles =====
const FEATURE_THUMBS = false; // اگر خواستی thumbnail واقعی، این رو true کن (و endpoint رو داری)

// ===== Utilities =====
const $ = (s, r=document) => r.querySelector(s);
const fmtSize = n => { const u=['B','KB','MB','GB','TB']; let i=0; while(n>=1024&&i<u.length-1){n/=1024;i++} return (i? n.toFixed(1):n)+' '+u[i]; };
const pct = (a,b) => b? Math.min(100, Math.round(a/b*100)) : 0;
const joinPath = (...p) => p.filter(Boolean).join('/');
const debounce = (fn,t)=>{ let id; return (...a)=>{ clearTimeout(id); id=setTimeout(()=>fn(...a),t);} };

// ===== State =====
let currentPath = '';
let selected = new Set();
let cacheFolders = [];
let cacheFiles = [];
let spaces = [];
let currentSpaceId = null;
let ctxTarget = null;

// ===== Modal / Toast =====
const modal = $('#modal');
const modalTitle = $('#modalTitle');
const modalText  = $('#modalText');
const modalInput = $('#modalInput');
const modalOk    = $('#modalOk');
const modalCancel= $('#modalCancel');
const toast      = $('#toast');
let modalResolve = null;

function showModal({title, text, withInput=false, placeholder='', okText='OK', danger=false}) {
  modalTitle.textContent = title || '';
  modalText.textContent = text || '';
  modalInput.classList.toggle('hidden', !withInput);
  modalInput.value = '';
  modalInput.placeholder = placeholder || '';
  modalOk.textContent = okText || 'OK';
  modalOk.classList.toggle('danger', !!danger);
  modal.classList.remove('hidden');
  if (withInput) modalInput.focus();
  return new Promise((resolve)=> { modalResolve = resolve; });
}
function closeModal(val=null){
  modal.classList.add('hidden');
  if (modalResolve) { modalResolve(val); modalResolve = null; }
}
modalOk.addEventListener('click', ()=> closeModal(modalInput.classList.contains('hidden') ? true : modalInput.value.trim()));
modalCancel.addEventListener('click', ()=> closeModal(null));
modal.addEventListener('click', (e)=> { if(e.target===modal) closeModal(null); });
document.addEventListener('keydown', (e)=>{ if(e.key==='Escape') closeModal(null); });

function showToast(message, ms=2200){
  toast.textContent = message;
  toast.classList.remove('hidden');
  setTimeout(()=> toast.classList.add('hidden'), ms);
}

// ===== Tabs =====
const tabExplorer=$('#tab-explorer'), tabUpload=$('#tab-upload'), panelExplorer=$('#panel-explorer'), panelUpload=$('#panel-upload');
function switchTab(name){
  const ex = name==='explorer';
  tabExplorer.classList.toggle('active', ex);
  tabUpload.classList.toggle('active', !ex);
  panelExplorer.classList.toggle('hidden', !ex);
  panelUpload.classList.toggle('hidden', ex);
  $('#currentPathHint').textContent = '/'+currentPath;
}
tabExplorer.addEventListener('click', ()=>switchTab('explorer'));
tabUpload.addEventListener('click', ()=>switchTab('upload'));

// ===== Spaces + usage =====
async function loadSpaces(){
  const r = await fetch('/api/spaces'); const j = await r.json().catch(()=>({ok:false}));
  if(!j.ok){ showToast('Failed to load spaces'); return; }
  spaces = j.items || [];
  const sel = $('#spaceSel'); sel.innerHTML = '';
  spaces.forEach(s=>{
    const opt=document.createElement('option');
    opt.value=s.id; opt.textContent=`${s.name} (${s.slug})${s.is_default?' *':''}`;
    if(s.current){ opt.selected=true; currentSpaceId=s.id; updateUsage(s); }
    sel.appendChild(opt);
  });
  if(!currentSpaceId && spaces[0]){ currentSpaceId=spaces[0].id; updateUsage(spaces[0]); }
}
function updateUsage(s){
  $('#usageText').textContent = `${fmtSize(s.used_bytes)} / ${fmtSize(s.max_bytes)} · ${s.file_count}/${s.max_files} files`;
  $('#usageBar').style.width = pct(s.used_bytes, s.max_bytes) + '%';
}
$('#spaceSel').addEventListener('change', async (e)=>{
  const id = e.target.value;
  const r = await fetch('/api/space/set',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({space_id:id})});
  const j = await r.json().catch(()=>({ok:false}));
  if(!j.ok){ showToast('Failed to switch space'); return; }
  currentSpaceId = +id;
  const s = spaces.find(x=>x.id==id); if(s) updateUsage(s);
  currentPath=''; await browse();
});

// ===== Explorer =====
const grid = $('#grid'), emptyState = $('#empty'), crumbs = $('#crumbs'), skeleton = $('#skeleton');
function renderCrumbs(){
  crumbs.innerHTML = '';
  const rootBtn = document.createElement('button');
  rootBtn.className='px-2 py-1 rounded hover:bg-slate-100'; rootBtn.textContent='/';
  rootBtn.addEventListener('click', ()=>{ currentPath=''; browse(); });
  crumbs.appendChild(rootBtn);
  if(!currentPath) return;
  const parts=currentPath.split('/'); let acc='';
  parts.forEach((part, idx)=>{
    const sep=document.createElement('span'); sep.textContent='›'; sep.className='px-1 text-slate-400'; crumbs.appendChild(sep);
    acc=joinPath(acc,part);
    const btn=document.createElement('button'); btn.className='px-2 py-1 rounded hover:bg-slate-100'; btn.textContent=part;
    btn.addEventListener('click', ()=>{ currentPath=parts.slice(0, idx+1).join('/'); browse(); });
    crumbs.appendChild(btn);
  });
}

function tileFolder(name){
  const el = document.createElement('div');
  el.className = 'ui-tile cursor-pointer';
  el.setAttribute('tabindex','0');
  el.dataset.folder = name;

  el.innerHTML = `
    <div class="thumb flex items-center justify-center text-2xl">📁</div>
    <div class="meta">
      <div class="mt-2 font-medium truncate" title="${name}">${name}</div>
      <div class="text-xs text-slate-500">Folder</div>
    </div>
  `;

  el.addEventListener('click', (e)=>{
    if (e.target.closest('.dots')) return;
    if (navLock) return;
    currentPath = joinPath(currentPath, name);
    browse();
  });

  el.addEventListener('keydown', (e)=>{
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      if (navLock) return;
      currentPath = joinPath(currentPath, name);
      browse();
    }
  });

  return el;
}


function tileFile(a){
  const el=document.createElement('div'); el.className='ui-tile group';
  let thumbHTML = `<div class="thumb flex items-center justify-center text-3xl">📘</div>`;
  if (FEATURE_THUMBS && a.mime && a.mime.startsWith('image/')) {
    const tUrl = `/api/thumb?rel_path=${encodeURIComponent(currentPath)}&name=${encodeURIComponent(a.name)}&w=320&h=220`;
    thumbHTML = `<img class="thumb" src="${tUrl}" alt="${a.name}" loading="lazy">`;
  }
  el.innerHTML=`
    <button class="dots" aria-label="More" type="button">⋮</button>
    ${thumbHTML}
    <div class="meta">
      <div class="mt-2 font-medium truncate" title="${a.name}">${a.name}</div>
      <div class="text-xs text-slate-500">${a.size?fmtSize(a.size):''} · ${a.mime||''}</div>
      <div class="mt-2 flex items-center gap-3">
        <a class="text-sky-600 underline text-sm" href="${a.url}" target="_blank" rel="noopener">Open</a>
        <label class="text-xs text-slate-500 flex items-center gap-1 ml-auto">
          <input type="checkbox" data-name="${a.name}" class="ui-checkbox"> select
        </label>
      </div>
    </div>`;
  // select on tile click (not on link/button/checkbox)
  el.addEventListener('click', (e)=>{
    if(e.target.closest('.dots') || e.target.tagName==='A' || e.target.type==='checkbox') return;
    const cb = el.querySelector('input[type="checkbox"]');
    cb.checked = !cb.checked;
    cb.dispatchEvent(new Event('change'));
  });
  el.querySelector('input[type="checkbox"]').addEventListener('change', e=>{
    const n = e.target.dataset.name;
    if(e.target.checked) selected.add(n); else selected.delete(n);
    updateBatchUI();
  });
  el.querySelector('.dots').addEventListener('click', (e)=> showMenu(e, a));
  return el;
}

function renderGrid(){
  grid.innerHTML = '';
  cacheFolders.forEach(f => grid.appendChild(tileFolder(f)));
  cacheFiles.forEach(a => grid.appendChild(tileFile(a)));
  emptyState.classList.toggle('hidden', !!(cacheFolders.length || cacheFiles.length));
}

const ctx = $('#ctx');
function showMenu(ev, file){
  ev.stopPropagation();
  ctxTarget = file;
  ctx.style.left = ev.clientX + 'px';
  ctx.style.top  = ev.clientY + 'px';
  ctx.classList.remove('hidden');
}
document.addEventListener('click', ()=> ctx.classList.add('hidden'));
ctx.addEventListener('click', async (e)=>{
  const act = e.target.dataset.act; if(!act || !ctxTarget) return;
  ctx.classList.add('hidden');
  if(act==='open'){ window.open(ctxTarget.url, '_blank'); }
  if(act==='copy'){ await navigator.clipboard.writeText(location.origin + ctxTarget.url); showToast('Link copied'); }
  if(act==='delete'){ await deleteFile(ctxTarget.name); }
  if(act==='rename'){ await renameFile(ctxTarget.name); }
});

async function browse(){
  if (navLock) return;
  navLock = true;

  $('#skeleton').classList.remove('hidden');
  grid.innerHTML=''; emptyState.classList.add('hidden');

  try{
    const r = await fetch(`/api/browse?rel_path=${encodeURIComponent(currentPath)}`);
    const j = await r.json();
    if(!j.ok){ showToast('Failed to load folder'); return; }
    cacheFolders = j.folders||[]; cacheFiles = j.files||[];
    selected.clear(); updateBatchUI();
    renderCrumbs(); renderGrid();
  } finally {
    $('#skeleton').classList.add('hidden');
    navLock = false;
  }
}

function updateBatchUI(){
  $('#selCount').textContent = `${selected.size} selected`;
  $('#actDelete').disabled = selected.size===0;
  $('#actZip').disabled    = selected.size===0;
}
$('#selAll').addEventListener('change', e=>{
  selected.clear();
  if(e.target.checked){ cacheFiles.forEach(a=>selected.add(a.name)); }
  renderGrid(); updateBatchUI();
});

// Actions
$('#btnNewFolder').addEventListener('click', async ()=>{
  const name = await showModal({title:'New folder', text:'Enter folder name', withInput:true, placeholder:'MyFolder', okText:'Create'});
  if(!name) return;
  const r = await fetch('/api/mkdir',{method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({rel_path: currentPath, name})});
  const j = await r.json().catch(()=>({ok:false}));
  if(!j.ok){ showToast('Create folder failed'); return; }
  showToast('Folder created'); browse();
});

async function renameFile(oldName){
  const newName = await showModal({title:'Rename / Move', text:'Enter new name:', withInput:true, placeholder:oldName, okText:'Next'});
  if(newName===null) return;
  const newPath = await showModal({title:'Move (optional)', text:'Enter new relative path (empty = stay here):', withInput:true, placeholder: currentPath || '', okText:'Apply'});
  const body = { old_rel_path: currentPath, old_name: oldName, new_rel_path: (newPath||currentPath), new_name: (newName || oldName) };
  const r = await fetch('/api/rename',{method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
  const j = await r.json().catch(()=>({ok:false}));
  if(!j.ok){ showToast('Rename failed'); return; }
  showToast('Renamed'); browse();
}

async function deleteFile(name){
  const ok = await showModal({title:'Delete file', text:`Delete "${name}"?`, okText:'Delete', danger:true});
  if(!ok) return;
  const r = await fetch('/api/delete',{method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({rel_path: currentPath, name})});
  const j = await r.json().catch(()=>({ok:false}));
  if(!j.ok){ showToast('Delete failed'); return; }
  showToast('Deleted');
  await loadSpaces(); browse();
}

$('#actZip').addEventListener('click', async ()=>{
  if(!selected.size) return;
  const items = Array.from(selected).map(n=>({rel_path: currentPath, name:n}));
  const r = await fetch('/api/zip',{method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({items})});
  if(!r.ok){ showToast('ZIP failed'); return; }
  const blob = await r.blob(); const url = URL.createObjectURL(blob);
  const a = document.createElement('a'); a.href=url; a.download='download.zip'; document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
});

$('#actDelete').addEventListener('click', async ()=>{
  if(!selected.size) return;
  const ok = await showModal({title:'Delete selected', text:`Delete ${selected.size} files?`, okText:'Delete', danger:true});
  if(!ok) return;
  const items = Array.from(selected).map(n=>({rel_path: currentPath, name:n}));
  const r = await fetch('/api/delete-batch',{method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({items})});
  const j = await r.json().catch(()=>({ok:false}));
  if(!j.ok) showToast('Batch delete failed'); else showToast(`Deleted ${j.deleted}, failed ${j.failed}`);
  await loadSpaces(); await browse();
});

// Search
$('#q').addEventListener('input', debounce(listSearch,300));
async function listSearch(){
  const q = $('#q').value.trim();
  if(!q){ return browse(); }
  $('#skeleton').classList.remove('hidden'); grid.innerHTML='';
  const r = await fetch('/api/assets?q=' + encodeURIComponent(q)); const j = await r.json().catch(()=>({ok:false}));
  $('#skeleton').classList.add('hidden');
  if(!j.ok){ showToast('Search failed'); return; }
  cacheFolders=[]; cacheFiles = j.items.map(x=>({name:x.original_name,size:x.size,mime:x.mime,url:x.url}));
  selected.clear(); updateBatchUI(); renderCrumbs(); renderGrid();
}

// ===== Uploads with progress =====
const drop=$('#drop'), filesInput=$('#files'), folderInput=$('#folder');
const queueList=$('#queue'), queueEmpty=$('#queueEmpty'), startBtn=$('#startUpload');
let uploadQueue=[]; let running=false;

function addToQueue(file, relPath){
  uploadQueue.push({file, rel_path: relPath || currentPath});
  queueEmpty.classList.add('hidden');
  const row=document.createElement('div');
  row.className='border rounded-lg p-2'; row.dataset.name=file.name;
  row.innerHTML=`
    <div class="flex items-center justify-between gap-2">
      <div class="truncate">
        <div class="font-medium truncate" title="${file.name}">${file.name}</div>
        <div class="text-xs text-slate-500">${relPath ? relPath + '/' : ''}${file.name}</div>
      </div>
      <div class="text-xs" data-status>queued</div>
    </div>
    <div class="ui-progress mt-2"><div class="ui-progress-bar" data-bar style="width:0%"></div></div>`;
  queueList.appendChild(row);
}
function setRow(name, {text, pct, cls}){
  const row = queueList.querySelector(`div[data-name="${CSS.escape(name)}"]`); if(!row) return;
  if(text!=null){ const st=row.querySelector('[data-status]'); st.textContent=text; st.className='text-xs '+(cls||''); }
  if(pct!=null){ row.querySelector('[data-bar]').style.width = Math.max(0,Math.min(100,pct))+'%'; }
}
drop.addEventListener('dragover', e=>{ e.preventDefault(); drop.classList.add('drag'); });
drop.addEventListener('dragleave', ()=> drop.classList.remove('drag'));
drop.addEventListener('drop', e=>{ e.preventDefault(); drop.classList.remove('drag'); for(const f of e.dataTransfer.files){ addToQueue(f, currentPath); }});
filesInput.addEventListener('change', e=>{ for(const f of e.target.files){ addToQueue(f, currentPath); }});
folderInput.addEventListener('change', e=>{
  for(const f of e.target.files){
    const rp=(f.webkitRelativePath||'').split('/').slice(0,-1).join('/');
    const rel=joinPath(currentPath, rp); addToQueue(f, rel);
  }
});
function xhrUpload(url, formData, onProgress){
  return new Promise((resolve,reject)=>{
    const x=new XMLHttpRequest(); x.open('POST', url);
    x.upload.onprogress = e => onProgress(e.loaded, e.total);
    x.onload = () => (x.status>=200&&x.status<300) ? resolve(x.responseText) : reject(x.responseText);
    x.onerror = () => reject('network'); x.send(formData);
  });
}
$('#startUpload').addEventListener('click', async ()=>{
  if(running || !uploadQueue.length) return;
  running=true; startBtn.disabled=true;
  while(uploadQueue.length){
    const {file, rel_path} = uploadQueue.shift();
    setRow(file.name, {text:'uploading…', pct:0, cls:'text-slate-600'});
    const fd = new FormData(); fd.append('file', file);
    const url = `/api/upload?rel_path=${encodeURIComponent(rel_path)}`;
    try{
      await xhrUpload(url, fd, (loaded,total)=> setRow(file.name, {pct: total? loaded/total*100 : 0}))
        .then(async res=>{
          const data = JSON.parse(res);
          if(data.ok){ setRow(file.name, {text:'done ✓', pct:100, cls:'text-green-700'}); }
          else { setRow(file.name, {text:`error: ${data.error||'failed'}`, cls:'text-red-700'}); }
        }).catch(()=> setRow(file.name, {text:'error: network', cls:'text-red-700'}));
    }catch(e){ setRow(file.name, {text:'error', cls:'text-red-700'}); }
  }
  running=false; startBtn.disabled=false;
  await loadSpaces(); await browse();
});

// ===== Init =====
async function init(){
  await loadSpaces();
  switchTab('explorer');
  await browse();
  $('#currentPathHint').textContent = '/'+currentPath;
  // Allowed extensions (display-only)
  fetch('/api/allowed-extensions').then(r=>r.json()).then(j=>{
    $('#extInfo').textContent = j.ok ? `Allowed: ${j.items.join(', ')}` : 'Allowed: (error)';
  }).catch(()=> $('#extInfo').textContent = 'Allowed: (error)');
}
init();
