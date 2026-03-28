// Client view — loads client details and change feed
async function loadClient(clientId) {
  state.currentClient = clientId;
  state.currentStep = 1;
  state.resolvedFlags = 0;
  state.uploadedFiles = [];
  state.extractedFields = [];

  // Reset step bar
  for (let i = 1; i <= 5; i++) {
    document.getElementById('p' + i).style.display = i === 1 ? 'block' : 'none';
    const s = document.getElementById('si' + i);
    s.className = i === 1 ? 'si active' : 'si';
  }

  try {
    const res = await fetch(API + '/api/clients/' + clientId);
    const data = await res.json();

    document.getElementById('client-name').textContent = data.name;
    document.getElementById('client-meta').textContent = `UEN ${data.uen} · ${data.filingType}`;

    document.getElementById('client-metrics').innerHTML = `
      <div class="cm-i"><div class="cm-l">Last filed</div><div class="cm-v">${data.lastFiled}</div></div>
      <div class="cm-i"><div class="cm-l">Deadline</div><div class="cm-v" style="color:var(--warm)">${data.deadline}</div></div>
    `;

    renderChanges(data.changes, data.lastFiled);
    renderBizfileForm(data.bizfileFields);

    // Store for later steps
    state.requiredFlags = data.flags ? data.flags.length : 0;
    state.clientData = data;
  } catch (err) {
    console.error('Failed to load client:', err);
  }
}

function renderChanges(changes, lastFiled) {
  document.getElementById('changes-verified').textContent = 'Verified today ' +
    new Date().toLocaleTimeString('en-SG', { hour: 'numeric', minute: '2-digit' });

  const el = document.getElementById('changes-feed');
  el.innerHTML = changes.map(c => {
    const iconClass = c.severity === 'warning' ? 'warn' : c.severity === 'info' ? 'info' : 'ok';
    const iconChar = c.severity === 'warning' ? '!' : c.severity === 'info' ? 'i' : '&#10003;';
    return `
      <div class="fi">
        <div class="fi-icon ${iconClass}">${iconChar}</div>
        <div>
          <div class="fi-t">${c.title}</div>
          <div class="fi-d">${c.description}</div>
          <div class="fi-m">${c.meta}</div>
        </div>
      </div>`;
  }).join('');
}

function renderBizfileForm(fields) {
  if (!fields) return;
  const el = document.getElementById('bizfile-form');
  let html = `
    <div class="biz-title">Annual Return for ${state.clientData.name}</div>
    <div class="biz-sub">UEN: ${state.clientData.uen} · Financial Year Ended: ${state.clientData.fye}</div>`;

  let currentSection = '';
  fields.forEach((f, i) => {
    if (f.section !== currentSection) {
      if (currentSection) html += '</div>';
      html += `<div class="biz-section"><div class="biz-section-title">${f.section}</div>`;
      currentSection = f.section;
    }
    html += `<div class="biz-row"><span class="biz-label">${f.label}</span><span class="biz-input" id="bf-${i + 1}"></span></div>`;
  });
  html += '</div>';
  html += `<div class="biz-btn-row">
    <button class="biz-btn biz-btn-secondary">Save Draft</button>
    <button class="biz-btn biz-btn-primary" id="biz-submit" style="opacity:.4">Review &amp; Submit</button>
  </div>`;

  el.innerHTML = html;
}
