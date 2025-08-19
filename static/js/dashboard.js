// static/cdn/dashboard.js
// EdgeCDN Dashboard – all UI logic consolidated into one file.
// Handles: spaces load/switch, usage bar, explorer browse/render, breadcrumbs,
// batch actions (select all, delete, zip), mkdir, rename/move, search,
// uploads with progress, drag&drop, folder upload (webkitdirectory).

(function(){
  "use strict";

  // ---------- Utilities ----------
  const $  = (s, r=document) => r.querySelector(s);
  const $$ = (s, r=document) => Array.from(r.querySelectorAll(s));
  const fmtSize = (n)=>{ const u=['B','KB','MB','GB','TB']; let i=0; while(n>=1024&&i<u.length-1){n/=1024;i++} return (i? n.toFixed(1):n)+' '+u[i]; };
  const pct = (a,b)=> b? Math.min(100, Math.round(a/b*100)) : 0;
  const joinPath = (...parts)=> parts.filter(Boolean).join('/');
  const parentPath = p => { if(!p) return ''; const a=p.split('/'); a.pop(); return a.join('/'); };
  const iconFolder = ()=> '📁';
  const iconFile = (mime)=> mime?.startsWith('image/') ? '🖼️'
                          : (mime?.includes('zip')||mime?.includes('tar')) ? '🗜️'
                          : mime?.includes('pdf') ? '📕'
                          : mime?.includes('audio') ? '🎵'
                          : mime?.includes('video') ? '🎬'
                          : (mime?.includes('css')||mime?.includes('javascript')) ? '📄'
                          : '📘';

  const debounce = (fn, t)=>{ let id; return (...a)=>{ clearTimeout(id); id=setTimeout(()=>fn(...a), t); } };

  // CSRF helpers (Django)
  function getCookie(name){
    const v = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
    return v ? v.pop() : '';
  }
  const CSRF = ()=> getCookie('csrftoken');
  async function jfetch(url, opts={}){
    const headers = opts.headers || {};
    if(!('X-CSRFToken' in headers) && (!opts.method || opts.method !== 'GET')){
      headers['X-CSRFToken'] = CSRF();
    }
    headers['Accept'] = headers['Accept'] || 'application/json';
    opts.headers = headers;
    const res = await fetch(url, opts);
    // Return both raw Response and JSON where possible
    let data = null;
    try { data = await res.clone().json(); } catch { /* not json */ }
    return {res, data};
  }
  function downloadBlob(blob, filename){
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = filename || 'download';
    document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
  }

  // ---------- State ----------
  let currentPath = '';              // rel_path in explorer
  let selected    = new Set();       // selected file names in current folder
  let cacheFolders = [], cacheFiles = [];
  let spaces = [], currentSpaceId = null;

  // ---------- DOM ----------
  const tabExplorer   = $('#tab-explorer');
  const tabUpload     = $('#tab-upload');
  const panelExplorer = $('#panel-explorer');
  const panelUpload   = $('#panel-upload');

  const spaceSel   = $('#spaceSel');
  const usageText  = $('#usageText');
  const usageBar   = $('#usageBar');

  const bucketFilter = $('#bucketFilter');
  const crumbs = $('#crumbs');

  const btnNewFolder = $('#btnNewFolder');
  const searchInput  = $('#q');

  const selAll   = $('#selAll');
  const actDelete= $('#actDelete');
  const actZip   = $('#actZip');
  const selCount = $('#selCount');

  const grid     = $('#grid');
  const empty    = $('#empty');

  const ctxMenu  = $('#ctx');
  let   ctxTarget = null; // {name, url, mime}

  // Upload controls
  const bucketInput = $('#bucket');
  const currentPathHint = $('#currentPathHint');
  const drop     = $('#drop');
  const filesInp = $('#files');
  const folderInp= $('#folder');
  const extInfo  = $('#extInfo');
  const startBtn = $('#startUpload');
  const queue    = $('#queue');
  const queueEmpty = $('#queueEmpty');
  let uploadQueue = [];
  let runningUpload = false;

  // ---------- Tabs ----------
  function switchTab(name){
    const ex = name === 'explorer';
    tabExplorer.classList.toggle('active', ex);
    tabExplorer.classList.toggle('border-b-2', ex);
    tabUpload.classList.toggle('active', !ex);
    tabUpload.classList.toggle('border-b-2', !ex);
    panelExplorer.classList.toggle('hidden', !ex);
    panelUpload.classList.toggle('hidden', ex);
    currentPathHint.textContent = '/' + currentPath;
  }
  tabExplorer.addEventListener('click', ()=>switchTab('explorer'));
  tabUpload  .addEventListener('click', ()=>switchTab('upload'));

  // ---------- Spaces & Usage ----------
  async function loadSpaces(){
    const {data} = await jfetch('/api/spaces');
    if(!data?.ok) return;
    spaces = data.items || [];
    spaceSel.innerHTML = '';
    spaces.forEach(s=>{
      const opt = document.createElement('option');
      opt.value = s.id;
      opt.textContent = `${s.name} (${s.slug})${s.is_default ? ' *' : ''}`;
      if(s.current){ opt.selected = true; currentSpaceId = s.id; updateUsage(s); }
      spaceSel.appendChild(opt);
    });
    if(!currentSpaceId && spaces.length){ currentSpaceId = spaces[0].id; updateUsage(spaces[0]); }
  }
  function updateUsage(s){
    usageText.textContent = `${fmtSize(s.used_bytes)} / ${fmtSize(s.max_bytes)} · ${s.file_count}/${s.max_files} files`;
    usageBar.style.width  = pct(s.used_bytes, s.max_bytes) + '%';
  }
  async function setSpace(id){
    await jfetch('/api/space/set',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({space_id:id})
    });
    currentSpaceId = +id;
    const s = spaces.find(x=> x.id == id);
    if(s) updateUsage(s);
    currentPath = '';
    await browse();
  }
  spaceSel.addEventListener('change', e => setSpace(e.target.value));

  async function reloadSpacesUsage(){
    const {data} = await jfetch('/api/spaces');
    if(!data?.ok) return;
    spaces = data.items || [];
    const s = spaces.find(x=> x.current) || spaces[0];
    if(s) updateUsage(s);
  }

  // ---------- Explorer ----------
  async function browse(){
    const bucket = bucketFilter.value.trim() || 'assets';
    const {data} = await jfetch(`/api/browse?bucket=${encodeURIComponent(bucket)}&rel_path=${encodeURIComponent(currentPath)}`);
    if(!data?.ok) return;
    cacheFolders = data.folders || [];
    cacheFiles   = data.files   || [];
    selected.clear(); updateBatchUI();
    renderCrumbs();
    renderGrid();
  }

  function renderCrumbs(){
    crumbs.innerHTML = '';
    const rootBtn = document.createElement('button');
    rootBtn.className = 'px-2 py-1 rounded hover:bg-slate-100';
    rootBtn.textContent = '/';
    rootBtn.addEventListener('click', ()=>{ currentPath=''; browse(); });
    crumbs.appendChild(rootBtn);

    if(!currentPath) return;
    const parts = currentPath.split('/'); let acc = '';
    parts.forEach((part, idx)=>{
      const sep = document.createElement('span'); sep.textContent='›'; sep.className='px-1 text-slate-400';
      crumbs.appendChild(sep);
      acc = joinPath(acc, part);
      const btn = document.createElement('button');
      btn.className = 'px-2 py-1 rounded hover:bg-slate-100';
      btn.textContent = part;
      btn.addEventListener('click', ()=>{ currentPath = parts.slice(0, idx+1).join('/'); browse(); });
      crumbs.appendChild(btn);
    });
  }

  function renderGrid(){
    grid.innerHTML = '';
    // Folders
    for(const f of cacheFolders){
      const el = document.createElement('div');
      el.className = 'tile cursor-pointer';
      el.innerHTML = `<div class="text-2xl">${iconFolder()}</div>
        <div class="mt-2 font-medium truncate" title="${f}">${f}</div>
        <div class="text-xs text-slate-500">Folder</div>`;
      el.addEventListener('dblclick', ()=>{ currentPath = joinPath(currentPath, f); browse(); });
      grid.appendChild(el);
    }
    // Files
    for(const a of cacheFiles){
      const el = document.createElement('div');
      el.className = 'tile';
      el.innerHTML = `
        <div class="flex items-start justify-between gap-2">
          <div class="text-2xl">${iconFile(a.mime)}</div>
          <label class="text-xs text-slate-500 flex items-center gap-1">
            <input type="checkbox" data-name="${a.name}" class="rounded border-slate-300"> select
          </label>
        </div>
        <div class="mt-2 font-medium truncate" title="${a.name}">${a.name}</div>
        <div class="text-xs text-slate-500">${fmtSize(a.size)} · ${a.mime || ''}</div>
        <div class="mt-2 flex items-center gap-3">
          <a class="text-sky-600 underline text-sm" href="${a.url}" target="_blank">Open</a>
          <button class="text-sm text-slate-600 hover:text-slate-900" data-menu>⋮</button>
        </div>`;
      // select
      el.querySelector('input[type="checkbox"]').addEventListener('change', e=>{
        const name = e.target.dataset.name;
        if(e.target.checked) selected.add(name); else selected.delete(name);
        updateBatchUI();
      });
      // context
      el.querySelector('[data-menu]').addEventListener('click', (e)=>{
        e.stopPropagation(); showCtx(e, a);
      });
      grid.appendChild(el);
    }
    empty.classList.toggle('hidden', !!(cacheFolders.length || cacheFiles.length));
  }

  function updateBatchUI(){
    selCount.textContent = `${selected.size} selected`;
    actDelete.disabled = selected.size===0;
    actZip.disabled = selected.size===0;
    // update "Select all" checkbox state based on files present
    if(cacheFiles.length === 0){ selAll.checked = false; selAll.indeterminate = false; }
    else {
      const sel = selected.size;
      selAll.checked = sel === cacheFiles.length;
      selAll.indeterminate = sel > 0 && sel < cacheFiles.length;
    }
  }

  // Batch buttons
  selAll.addEventListener('change', e=>{
    selected.clear();
    if(e.target.checked){ cacheFiles.forEach(a => selected.add(a.name)); }
    renderGrid(); updateBatchUI();
  });

  actZip.addEventListener('click', async ()=>{
    if(!selected.size) return;
    const bucket = bucketFilter.value.trim() || 'assets';
    const items = Array.from(selected).map(n => ({bucket, rel_path: currentPath, name:n}));
    const r = await fetch('/api/zip', {method:'POST', headers:{'Content-Type':'application/json','X-CSRFToken':CSRF()}, body: JSON.stringify({items})});
    if(!r.ok) return;
    const blob = await r.blob();
    downloadBlob(blob, 'download.zip');
  });

  actDelete.addEventListener('click', async ()=>{
    if(!selected.size || !confirm('Delete selected files?')) return;
    const bucket = bucketFilter.value.trim() || 'assets';
    const items = Array.from(selected).map(n => ({rel_path: currentPath, name:n}));
    const {data} = await jfetch('/api/delete-batch', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({bucket, items})
    });
    if(!data?.ok) alert('Delete failed');
    await reloadSpacesUsage();
    await browse();
  });

  // Context menu
  function showCtx(ev, file){
    ctxTarget = file;
    ctxMenu.style.left = (ev.clientX) + 'px';
    ctxMenu.style.top  = (ev.clientY) + 'px';
    ctxMenu.classList.remove('hidden');
  }
  document.addEventListener('click', ()=> ctxMenu.classList.add('hidden'));
  ctxMenu.addEventListener('click', async (e)=>{
    const act = e.target.dataset.act; if(!act || !ctxTarget) return;
    ctxMenu.classList.add('hidden');
    if(act==='open'){ window.open(ctxTarget.url, '_blank'); }
    if(act==='copy'){ navigator.clipboard.writeText(location.origin + ctxTarget.url); }
    if(act==='delete'){ await deleteSingle(ctxTarget.name); }
    if(act==='rename'){ await renameSingle(ctxTarget.name); }
  });

  async function deleteSingle(name){
    const bucket = bucketFilter.value.trim() || 'assets';
    const {data} = await jfetch('/api/delete', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({bucket, rel_path: currentPath, name})
    });
    if(!data?.ok) alert('Delete error: ' + (data?.error||''));
    await reloadSpacesUsage();
    await browse();
  }

  async function renameSingle(oldName){
    const bucket = bucketFilter.value.trim() || 'assets';
    const newName = prompt('New name (keep extension):', oldName) || oldName;
    const moveTo  = prompt('New path (relative, optional):', currentPath) || currentPath;
    const body = { bucket, old_rel_path: currentPath, old_name: oldName, new_rel_path: moveTo, new_name: newName };
    const {data} = await jfetch('/api/rename', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify(body)
    });
    if(!data?.ok) alert('Rename error: ' + (data?.error||'')); else await browse();
  }

  // New folder
  btnNewFolder.addEventListener('click', async ()=>{
    const name = prompt('Folder name');
    if(!name) return;
    const bucket = bucketFilter.value.trim() || 'assets';
    const {data} = await jfetch('/api/mkdir', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({bucket, rel_path: currentPath, name})
    });
    if(!data?.ok) alert('Error: ' + (data?.error || 'mkdir failed'));
    await browse();
  });

  // Search
  bucketFilter.addEventListener('change', async ()=>{
    bucketInput.value = bucketFilter.value;
    currentPath = '';
    await browse();
  });

  searchInput.addEventListener('input', debounce(listSearch, 300));
  async function listSearch(){
    const q = searchInput.value.trim();
    const bucket = bucketFilter.value.trim();
    if(!q){ return browse(); }
    const {data} = await jfetch('/api/assets?' + new URLSearchParams({q, bucket}).toString());
    if(!data?.ok) return;
    cacheFolders = [];
    cacheFiles = (data.items || []).map(x => ({name:x.original_name, size:x.size, mime:x.mime, url:x.url}));
    selected.clear(); updateBatchUI();
    renderCrumbs(); renderGrid();
  }

  // ---------- Upload ----------
  function addToQueue(file, relPath){
    uploadQueue.push({file, rel_path: relPath || currentPath});
    queueEmpty.classList.add('hidden');
    const row = document.createElement('div');
    row.className = 'border rounded-lg p-2';
    row.dataset.name = file.name;
    row.innerHTML = `
      <div class="flex items-center justify-between gap-2">
        <div class="truncate">
          <div class="font-medium truncate" title="${file.name}">${file.name}</div>
          <div class="text-xs text-slate-500">${relPath ? relPath + '/' : ''}${file.name}</div>
        </div>
        <div class="text-xs" data-status>queued</div>
      </div>
      <div class="h-2 bg-slate-100 rounded overflow-hidden mt-2"><div class="h-2 w-0" data-bar style="background:#0f172a"></div></div>
    `;
    queue.appendChild(row);
  }
  function setRow(name, {text, pct, cls}){
    const row = $(`div[data-name="${CSS.escape(name)}"]`, queue);
    if(!row) return;
    if(text!=null){ const st=row.querySelector('[data-status]'); st.textContent=text; st.className='text-xs '+(cls||''); }
    if(pct!=null){ row.querySelector('[data-bar]').style.width = Math.max(0,Math.min(100,pct))+'%'; }
  }

  drop.addEventListener('dragover', e=>{ e.preventDefault(); drop.classList.add('bg-slate-50'); });
  drop.addEventListener('dragleave', ()=> drop.classList.remove('bg-slate-50'));
  drop.addEventListener('drop', e=>{
    e.preventDefault(); drop.classList.remove('bg-slate-50');
    for(const f of e.dataTransfer.files){ addToQueue(f, currentPath); }
  });
  filesInp.addEventListener('change', e=>{
    for(const f of e.target.files){ addToQueue(f, currentPath); }
  });
  folderInp.addEventListener('change', e=>{
    for(const f of e.target.files){
      const rp  = (f.webkitRelativePath || '').split('/').slice(0,-1).join('/');
      const rel = joinPath(currentPath, rp);
      addToQueue(f, rel);
    }
  });

  async function loadExts(){
    const {data} = await jfetch('/api/allowed-extensions');
    extInfo.textContent = data?.ok ? `Allowed: ${data.items.join(', ')}` : 'Allowed: (error)';
  }

  function xhrUpload(url, formData, onProgress){
    return new Promise((resolve, reject)=>{
      const x = new XMLHttpRequest();
      x.open('POST', url);
      x.setRequestHeader('X-CSRFToken', CSRF()); // safe even if api_upload is csrf_exempt
      x.upload.onprogress = e => onProgress(e.loaded, e.total);
      x.onload  = () => (x.status>=200 && x.status<300) ? resolve(x.responseText) : reject(x.responseText);
      x.onerror = () => reject('network');
      x.send(formData);
    });
  }

  startBtn.addEventListener('click', async ()=>{
    if(runningUpload || !uploadQueue.length) return;
    runningUpload = true; startBtn.disabled = true;
    const bucket = bucketInput.value.trim() || 'assets';

    while(uploadQueue.length){
      const {file, rel_path} = uploadQueue.shift();
      setRow(file.name, {text:'uploading…', pct:0, cls:'text-slate-600'});
      const fd = new FormData(); fd.append('file', file);
      const url = `/api/upload?bucket=${encodeURIComponent(bucket)}&rel_path=${encodeURIComponent(rel_path)}`;
      try{
        await xhrUpload(url, fd, (loaded,total)=> setRow(file.name, {pct: total? loaded/total*100 : 0}))
          .then(async res=>{
            let data=null; try{ data=JSON.parse(res);}catch{}
            if(data?.ok){ setRow(file.name, {text:'done ✓', pct:100, cls:'text-green-700'}); }
            else { setRow(file.name, {text:`error: ${(data&&data.error)||'failed'}`, cls:'text-red-700'}); }
          }).catch(()=> setRow(file.name, {text:'error: network', cls:'text-red-700'}));
      }catch(e){
        setRow(file.name, {text:'error', cls:'text-red-700'});
      }
    }
    runningUpload=false; startBtn.disabled=false;
    await reloadSpacesUsage();
    await browse();
  });

  bucketFilter.addEventListener('change', ()=> bucketInput.value = bucketFilter.value );

  // ---------- Init ----------
  async function init(){
    await loadSpaces();
    await loadExts();
    switchTab('explorer');
    await browse();
    bucketInput.value = bucketFilter.value;
    currentPathHint.textContent = '/' + currentPath;
  }
  document.addEventListener('DOMContentLoaded', init);

})();
