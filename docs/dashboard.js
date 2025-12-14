const PAGE_SIZE = 10;
let page = 1;
let lingering = [];

function hours(a,b){ return (new Date(b)-new Date(a))/36e5; }
function days(a,b){ return (new Date(b)-new Date(a))/(36e5*24); }

function percentile(arr,p){
  if(!arr.length) return null;
  arr = [...arr].sort((a,b)=>a-b);
  return arr[Math.floor(arr.length*p)];
}

fetch("data.json",{cache:"no-store"}).then(r=>r.json()).then(data=>{
  const prs = data.pull_requests;
  const now = new Date();

  /* -------- Time to first response -------- */
  const ttfr = [];
  prs.forEach(pr=>{
    const first = pr.events
      .filter(e=>e.author!==pr.author)
      .sort((a,b)=>new Date(a.created_at)-new Date(b.created_at))[0];
    if(first)
      ttfr.push(hours(pr.created_at, first.created_at));
  });

  new Chart(responseChart,{
    type:"bar",
    data:{
      labels:["p50","p90"],
      datasets:[{
        label:"Hours",
        data:[percentile(ttfr,0.5), percentile(ttfr,0.9)]
      }]
    }
  });

  /* -------- Throughput -------- */
  const open={}, close={};
  prs.forEach(pr=>{
    const c = pr.created_at?.slice(0,10);
    const cl = pr.closed_at?.slice(0,10);
    if(c) open[c]=(open[c]||0)+1;
    if(cl) close[cl]=(close[cl]||0)+1;
  });

  const labels = [...new Set([...Object.keys(open),...Object.keys(close)])].sort();
  new Chart(throughputChart,{
    type:"line",
    data:{
      labels,
      datasets:[
        {label:"Opened", data:labels.map(l=>open[l]||0)},
        {label:"Closed", data:labels.map(l=>close[l]||0)}
      ]
    }
  });

  /* -------- Unassigned PRs -------- */
  const unassigned = prs.filter(pr=>!pr.review_requests.length && !pr.closed_at);
  unassignedDiv.innerHTML =
    `${unassigned.length} / ${prs.filter(p=>!p.closed_at).length} open PRs unassigned`;

  /* -------- Lingering PRs -------- */
  lingering = prs
    .filter(pr=>!pr.closed_at && days(pr.updated_at, now)>=7)
    .sort((a,b)=>days(b.updated_at,now)-days(a.updated_at,now));

  renderLingering();
});

function renderLingering(){
  const tbody = lingerTable.querySelector("tbody");
  tbody.innerHTML="";
  const start=(page-1)*PAGE_SIZE;
  lingering.slice(start,start+PAGE_SIZE).forEach(pr=>{
    tbody.innerHTML+=`
      <tr>
        <td>${pr.number}</td>
        <td><a href="${pr.html_url}" target="_blank">${pr.title}</a></td>
        <td>${Math.floor(days(pr.updated_at,new Date()))}</td>
      </tr>`;
  });

  pager.innerHTML="";
  for(let i=1;i<=Math.ceil(lingering.length/PAGE_SIZE);i++){
    const b=document.createElement("button");
    b.textContent=i;
    b.disabled=i===page;
    b.onclick=()=>{page=i;renderLingering();}
    pager.appendChild(b);
  }
}
