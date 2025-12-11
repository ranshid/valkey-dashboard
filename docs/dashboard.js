async function loadData(){
  try {
    const resp = await fetch('data.json', {cache: "no-store"});
    if (!resp.ok) throw new Error('data.json not found');
    const data = await resp.json();

    document.getElementById('lastUpdated').textContent = 'Data updated: ' + (data.generated_at || 'unknown');

    document.getElementById('overview').innerHTML = `
      <strong>Total open PRs:</strong> ${data.total_open_prs} <br/>
      <strong>Mean hours since last update:</strong> ${data.mean_response_hours ? data.mean_response_hours.toFixed(1) : '—'} hrs <br/>
      <strong>PRs older than threshold:</strong> ${data.stale_prs.length}
    `;

    const tbody = document.querySelector('#staleTable tbody');
    tbody.innerHTML = '';
    data.stale_prs.forEach(pr => {
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${pr.number}</td><td><a href="${pr.html_url}" target="_blank">${escapeHtml(pr.title)}</a></td><td>${pr.days_open}</td><td>${pr.last_updated_hours}</td>`;
      tbody.appendChild(tr);
    });

    // Chart
    const labels = data.stale_prs.map(p => '#' + p.number);
    const values = data.stale_prs.map(p => p.days_open);
    const ctx = document.getElementById('staleChart').getContext('2d');
    if(window._staleChart) window._staleChart.destroy();
    window._staleChart = new Chart(ctx, {
      type: 'bar',
      data: { labels, datasets: [{ label: 'Days Open', data: values }] },
      options: { responsive: true, maintainAspectRatio: false }
    });

  } catch (err) {
    document.getElementById('overview').innerHTML = '<strong>Error loading data.json</strong><br/>' + err;
    console.error(err);
  }
}

function escapeHtml(text) {
  return text.replace(/[&<>"']/g, (m) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));
}

loadData();

