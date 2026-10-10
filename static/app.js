let DATA=null;
let polling=null;
const $=s=>document.querySelector(s); const $$=s=>[...document.querySelectorAll(s)];
const fa=n=>new Intl.NumberFormat('fa-IR',{maximumFractionDigits:0}).format(n||0);
const mil=n=>n==null?'—':`${(n/1_000_000).toLocaleString('fa-IR',{maximumFractionDigits:1})} م`;
const toman=n=>n==null?'—':(n>=1e9?`${(n/1e9).toLocaleString('fa-IR',{maximumFractionDigits:2})} میلیارد`:`${(n/1e6).toLocaleString('fa-IR',{maximumFractionDigits:0})} میلیون`);
function toast(msg){const t=$('#toast');t.textContent=msg;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),4200)}
function esc(v){return String(v??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]))}

async function load(){
  const r=await fetch('/api/dashboard'); DATA=await r.json(); render();
  if(DATA.last_run?.status==='running') showProgress(DATA.last_run);
}

async function startUpdate(){
  const b=$('#updateBtn'); b.disabled=true;
  try{
    const r=await fetch('/api/update',{method:'POST'}); const x=await r.json();
    if(!x.ok) throw new Error(x.error||'شروع بروزرسانی ناموفق بود');
    $('#progressBox').classList.remove('hidden');
    pollUpdate(x.run_id);
  }catch(e){toast('خطا: '+e.message);b.disabled=false}
}

function pollUpdate(runId){
  clearInterval(polling);
  const tick=async()=>{
    try{
      const r=await fetch('/api/update/status?run_id='+encodeURIComponent(runId)); const x=await r.json();
      if(!x.ok||!x.run) return;
      showProgress(x.run);
      if(x.run.status!=='running'){
        clearInterval(polling); polling=null; $('#updateBtn').disabled=false;
        if(x.run.status==='ok'){toast(x.run.message||'بروزرسانی تمام شد');await load()}
        else toast('خطا: '+(x.run.message||'بروزرسانی ناموفق بود'));
      }
    }catch(e){console.error(e)}
  };
  tick(); polling=setInterval(tick,1300);
}

function showProgress(run){
  const box=$('#progressBox'); box.classList.remove('hidden');
  const p=Math.max(0,Math.min(100,run.progress||0));
  $('#progressStage').textContent=run.stage||'در حال بروزرسانی';
  $('#progressPercent').textContent=fa(p)+'٪';
  $('#progressBar').style.width=p+'%';
  $('#progressMessage').textContent=run.message||'';
  $('#updateText').textContent=run.status==='running'?'در حال بروزرسانی…':'به‌روزرسانی از دیوار';
  $('#updateBtn').classList.toggle('loading',run.status==='running');
  $('#updateBtn').disabled=run.status==='running';
  if(run.status!=='running') setTimeout(()=>box.classList.add('hidden'),3500);
}

function render(){
  const s=DATA.summary;
  const hasData=s.active_count>0;
  $('#emptyState').classList.toggle('hidden',hasData);
  $('#appContent').classList.toggle('hidden',!hasData);
  $('#medianPpm').textContent=mil(s.median_ppm); $('#newMedianPpm').textContent=mil(s.new_build_median_ppm);
  $('#validCount').textContent=fa(s.valid_count); $('#districtCount').textContent=fa(s.district_count);
  $('#activeCount').textContent=fa(s.active_count); $('#detailCount').textContent=fa(s.detail_complete_count);
  $('#dupeCount').textContent=fa(s.duplicate_count); $('#outlierCount').textContent=fa(s.outlier_count);
  $('#newBuildLabel').textContent=`ساخت ۰ تا ${fa(DATA.new_build_max_age)} سال`;
  $('#sourceLabel').textContent=DATA.source_label||'دیوار — داده زنده';
  if(DATA.last_run){
    const d=new Date(DATA.last_run.finished_at||DATA.last_run.started_at);
    const coverage=DATA.last_run.complete_coverage?'پوشش کامل لیست':'پوشش محافظه‌کارانه';
    $('#lastUpdate').textContent=`آخرین بروزرسانی: ${d.toLocaleString('fa-IR')} • ${coverage}`;
  }
  renderDistrictPreview(); renderDistrictCards(); fillDistrictFilter(); renderListings(); drawHistory('#miniChart',true); drawHistory('#historyChart',false);
}

function renderDistrictPreview(){
  const box=$('#districtPreview'); const arr=DATA.districts.slice(0,9); const max=Math.max(...arr.map(x=>x.q3_ppm||0),1);
  box.innerHTML=arr.map(d=>`<div class="district-row"><div class="district-name">${esc(d.district)}</div><div class="rangebar" title="${mil(d.q1_ppm)} تا ${mil(d.q3_ppm)}"><span style="width:${Math.max(8,(d.q3_ppm/max)*100)}%"></span></div><div class="district-price">${mil(d.median_ppm)}</div></div>`).join('')||'<div class="empty">داده‌ای نیست.</div>'
}

function renderDistrictCards(){
  const q=($('#districtSearch').value||'').trim(); let arr=DATA.districts.filter(d=>!q||d.district.includes(q));
  $('#districtCards').innerHTML=arr.map((d,i)=>`<article class="district-card"><div class="top"><h2>${esc(d.district)}</h2><span class="rank">#${fa(i+1)}</span></div><strong class="big">${mil(d.median_ppm)}</strong><div class="sub">میانه قیمت هر متر</div><div class="range-text">بازه رایج ${mil(d.q1_ppm)} تا ${mil(d.q3_ppm)}</div><div class="mini-stats"><div><span>فایل معتبر</span><b>${fa(d.count)}</b></div><div><span>میانه نوساز</span><b>${mil(d.new_build_median_ppm)}</b></div><div><span>نوساز معتبر</span><b>${fa(d.new_build_count)}</b></div><div><span>کمینه / بیشینه</span><b>${mil(d.min_ppm)} / ${mil(d.max_ppm)}</b></div></div></article>`).join('')||'<div class="empty">محله‌ای پیدا نشد.</div>'
}

function fillDistrictFilter(){
  const sel=$('#districtFilter'); const val=sel.value; sel.innerHTML='<option value="">همه محله‌ها</option>'+DATA.districts.map(d=>`<option>${esc(d.district)}</option>`).join(''); sel.value=val;
}
function sizeOK(s,f){if(!f)return true;if(f==='lt70')return s<70;if(f==='70-100')return s>=70&&s<100;if(f==='100-130')return s>=100&&s<130;if(f==='130-160')return s>=130&&s<160;if(f==='gt160')return s>=160;return true}
function diffBadge(v){if(v==null)return '<span class="diff neutral">—</span>'; const cls=v<=-5?'good':v>=5?'bad':'neutral';const sign=v>0?'+':'';return `<span class="diff ${cls}">${sign}${v.toLocaleString('fa-IR',{maximumFractionDigits:1})}٪</span>`}

function renderListings(){
  let arr=[...DATA.listings]; const d=$('#districtFilter').value,a=$('#ageFilter').value,z=$('#sizeFilter').value,q=$('#qualityFilter').value,txt=($('#listingSearch').value||'').trim();
  arr=arr.filter(x=>(!d||x.district===d)&&(!txt||(x.title||'').includes(txt))&&sizeOK(x.size_m2||0,z));
  if(a==='new')arr=arr.filter(x=>x.building_age!=null&&x.building_age<=DATA.new_build_max_age); else if(a!=='')arr=arr.filter(x=>x.building_age==+a);
  if(q==='valid')arr=arr.filter(x=>!x.duplicate_of&&!x.is_outlier&&x.price_per_m2);
  if(q==='opportunity')arr=arr.filter(x=>!x.duplicate_of&&!x.is_outlier&&x.price_per_m2&&x.market_diff_pct!=null&&x.market_diff_pct<0);
  if(q==='outlier')arr=arr.filter(x=>x.is_outlier); if(q==='duplicate')arr=arr.filter(x=>x.duplicate_of);
  arr.sort((a,b)=>(a.market_diff_pct??9999)-(b.market_diff_pct??9999));
  $('#listingCount').textContent=`${fa(arr.length)} آگهی`;
  $('#listingRows').innerHTML=arr.slice(0,600).map(x=>{
    let st='<span class="tag">معتبر</span>'; if(x.duplicate_of)st='<span class="tag warn">تکراری</span>'; else if(x.is_outlier)st='<span class="tag bad">پرت</span>'; else if(x.is_new)st='<span class="tag new">جدید</span>';
    const raw=x.district_raw&&x.district_raw!==x.district?`<small>${esc(x.district_raw)}</small>`:'';
    const year=x.year_built?fa(x.year_built):(x.building_age===0?'نوساز':'—');
    return `<tr><td><b>${esc(x.district||'—')}</b>${raw}</td><td class="title">${esc(x.title||'—')}</td><td>${x.size_m2?fa(x.size_m2)+' متر':'—'}</td><td>${year}</td><td>${toman(x.total_price)}</td><td><b>${mil(x.price_per_m2)}</b></td><td>${diffBadge(x.market_diff_pct)}</td><td>${st}</td><td>${x.url?`<a class="link" target="_blank" rel="noopener" href="${esc(x.url)}">دیوار ↗</a>`:'—'}</td></tr>`
  }).join('')||'<tr><td colspan="9" class="empty">موردی با این فیلترها نیست.</td></tr>'
}

function drawHistory(selector,mini){
  const c=$(selector),ctx=c.getContext('2d'),hist=DATA.history;ctx.clearRect(0,0,c.width,c.height);
  const empty=$(mini?'#chartEmpty':'#historyEmpty'); if(!hist.length){empty.classList.remove('hidden');return}else empty.classList.add('hidden');
  const days=[...new Set(hist.map(x=>x.day))]; const districts=[...new Set(hist.map(x=>x.district))].slice(0,mini?4:8); const vals=hist.filter(x=>districts.includes(x.district)).map(x=>x.median_ppm).filter(Boolean); if(!vals.length)return;
  const min=Math.min(...vals)*.94,max=Math.max(...vals)*1.06;ctx.strokeStyle='#26303d';ctx.lineWidth=1;for(let i=0;i<5;i++){const y=25+i*(c.height-55)/4;ctx.beginPath();ctx.moveTo(45,y);ctx.lineTo(c.width-15,y);ctx.stroke()}
  const palette=['#8be9b2','#69d9ff','#ffd166','#ff8aa1','#b39cff','#75e0d1','#f5a97f','#a6da95'];districts.forEach((dist,di)=>{const pts=days.map((day,idx)=>{const r=hist.find(h=>h.day===day&&h.district===dist);if(!r)return null;return{x:55+idx*Math.max(1,(c.width-80)/Math.max(1,days.length-1)),y:20+(max-r.median_ppm)/(max-min||1)*(c.height-55)}});ctx.strokeStyle=palette[di%palette.length];ctx.lineWidth=2;ctx.beginPath();let started=false;pts.forEach(p=>{if(!p)return;if(!started){ctx.moveTo(p.x,p.y);started=true}else ctx.lineTo(p.x,p.y)});ctx.stroke();if(!mini){ctx.fillStyle=palette[di%palette.length];ctx.font='12px sans-serif';ctx.fillText(dist,15+di*95,c.height-10)}})
}

$$('.nav').forEach(b=>b.onclick=()=>{$$('.nav').forEach(x=>x.classList.remove('active'));b.classList.add('active');$$('.tabpage').forEach(x=>x.classList.remove('active'));$('#'+b.dataset.tab).classList.add('active')});
$('#updateBtn').onclick=startUpdate; $('#emptyUpdateBtn').onclick=startUpdate; $('#districtSearch').oninput=renderDistrictCards; $('#listingSearch').oninput=renderListings;
['#districtFilter','#ageFilter','#sizeFilter','#qualityFilter'].forEach(s=>$(s).onchange=renderListings);
load();
