// Dashboard — fetches stats and filings from backend
async function loadDashboard() {
  try {
    const res = await fetch(API + '/api/dashboard');
    const data = await res.json();
    renderDashStats(data.stats);
    renderFilingsTable(data.filings);
  } catch (err) {
    console.error('Failed to load dashboard:', err);
  }
}

function renderDashStats(stats) {
  const el = document.getElementById('dash-stats');
  el.innerHTML = stats.map(s => `
    <div class="ds">
      <div class="ds-label">${s.label}</div>
      <div class="ds-val ${s.class || ''}">${s.value}</div>
    </div>
  `).join('');
}

function renderFilingsTable(filings) {
  const el = document.getElementById('filings-table');
  el.innerHTML = filings.map(f => `
    <tr onclick="showScreen('client')">
      <td><span class="cn">${f.client}</span></td>
      <td>${f.filing}</td>
      <td>${f.deadline}</td>
      <td><span class="pill pill-${f.statusClass}">${f.status}</span></td>
      <td><span class="ac">${f.alerts}</span></td>
    </tr>
  `).join('');
}
