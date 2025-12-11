const PRS_PER_PAGE = 10;
let currentPage = 1;
let lingeringPRs = [];

async function loadData() {
  const resp = await fetch("data.json", {cache: "no-store"});
  const data = await resp.json();

  // Filter lingering PRs (last update >= 7 days)
  lingeringPRs = (data.stale_prs || []).concat(
    (data.total_prs || []).filter(pr => pr.last_updated_hours >= 24*7)
  );

  // Sort descending by days open or hours since last update
  lingeringPRs.sort((a,b) => (b.days_open || 0) - (a.days_open || 0));

  renderTable();
  renderPagination();
}

function renderTable() {
  const tbody = document.querySelector("#prTable tbody");
  tbody.innerHTML = "";
  const start = (currentPage - 1) * PRS_PER_PAGE;
  const end = start + PRS_PER_PAGE;
  const pagePRs = lingeringPRs.slice(start, end);

  pagePRs.forEach(pr => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${pr.number}</td>
                    <td><a href="${pr.html_url}" target="_blank">${escapeHtml(pr.title)}</a></td>
                    <td>${pr.days_open ?? Math.round((pr.last_updated_hours||0)/24)}</td>`;
    tbody.appendChild(tr);
  });

  if(pagePRs.length === 0) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td colspan="3" style="text-align:center;">No lingering PRs</td>`;
    tbody.appendChild(tr);
  }
}

function renderPagination() {
  const pagination = document.getElementById("pagination");
  pagination.innerHTML = "";
  const totalPages = Math.ceil(lingeringPRs.length / PRS_PER_PAGE);
  if(totalPages <= 1) return;

  for(let i = 1; i <= totalPages; i++){
    const btn = document.createElement("button");
    btn.textContent = i;
    if(i === currentPage) btn.disabled = true;
    btn.addEventListener("click", () => {
      currentPage = i;
      renderTable();
      renderPagination();
    });
    pagination.appendChild(btn);
  }
}

function escapeHtml(text) {
  return text.replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));
}

loadData();
