// Autofill — calls backend Tinyfish endpoint via SSE for real-time streaming
function startAutofill() {
  const log = document.getElementById('agent-log');
  log.innerHTML = '';
  const statusEl = document.getElementById('agent-status');
  statusEl.innerHTML = '<div class="as-row"><div class="spinner"></div><span style="font-size:.72rem;color:var(--text3)">Connecting to Tinyfish...</span></div>';

  // Reset BizFile+ form fields
  const bizForm = document.getElementById('bizfile-form');
  bizForm.querySelectorAll('.biz-input').forEach(el => {
    el.textContent = '';
    el.className = 'biz-input';
  });
  const submitBtn = document.getElementById('biz-submit');
  if (submitBtn) submitBtn.style.opacity = '.4';

  // Open SSE connection to backend
  const params = new URLSearchParams({ clientId: state.currentClient });
  const evtSource = new EventSource(API + '/api/tinyfish/autofill?' + params);

  evtSource.addEventListener('log', (e) => {
    const data = JSON.parse(e.data);
    addAgentLog(data.message, data.time);
  });

  evtSource.addEventListener('status', (e) => {
    const data = JSON.parse(e.data);
    statusEl.innerHTML = `<div class="as-row"><div class="spinner"></div><span style="font-size:.72rem;color:var(--tf)">${data.message}</span></div>`;
  });

  evtSource.addEventListener('fill', (e) => {
    const data = JSON.parse(e.data);
    fillBizField(data.fieldIndex, data.value, data.label);
  });

  evtSource.addEventListener('complete', (e) => {
    const data = JSON.parse(e.data);
    evtSource.close();

    statusEl.innerHTML = `<div class="as-row"><span class="as-done">&#10003; ${data.message}</span></div>`;
    addAgentLog('<span class="tf-highlight">&#10003; Complete.</span> ' + data.message);

    if (submitBtn) submitBtn.style.opacity = '1';

    // Auto-advance to done
    setTimeout(() => {
      addAgentLog('Rachel clicks <strong>Review &amp; Submit</strong>. Filing submitted to ACRA.');
      setTimeout(() => goP(5), 1500);
    }, 2500);
  });

  evtSource.addEventListener('error', (e) => {
    // Check if it's a real error vs stream ending
    if (evtSource.readyState === EventSource.CLOSED) return;
    evtSource.close();
    statusEl.innerHTML = '<div class="as-row"><span style="color:var(--warm);font-weight:600">Connection error</span></div>';
    addAgentLog('<span style="color:var(--warm)">Error: Lost connection to Tinyfish agent.</span>');
  });
}

function fillBizField(index, value, label) {
  const el = document.getElementById('bf-' + index);
  if (!el) return;

  el.className = 'biz-input filling';
  el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

  // Typing animation
  let chars = 0;
  const typeInt = setInterval(() => {
    chars += 2;
    el.textContent = value.substring(0, Math.min(chars, value.length));
    if (chars >= value.length) {
      clearInterval(typeInt);
      el.className = 'biz-input filled';
    }
  }, 35);
}

function addAgentLog(message, time) {
  const log = document.getElementById('agent-log');
  const el = document.createElement('div');
  el.className = 'agent-entry';
  el.innerHTML = `<div class="ae-time">${time || getElapsed()}</div><div class="ae-text">${message}</div>`;
  log.appendChild(el);
  log.scrollTop = log.scrollHeight;
}

// Render summary on step 5
const origGoPForSummary = goP;
goP = function (n) {
  origGoPForSummary(n);
  if (n === 5) renderSummary();
};

function renderSummary() {
  const elapsed = getElapsed();
  const fieldCount = state.clientData?.bizfileFields?.length || 11;
  const el = document.getElementById('summary');
  el.innerHTML = `
    <div style="font-size:2rem;margin-bottom:.4rem">&#9989;</div>
    <h3>Filed in ${elapsed}. Powered by Tinyfish.</h3>
    <p>All fields populated, rule changes caught, compliance verified, and form submitted via BizFile+.</p>
    <div class="sum-row">
      <div class="sum-i"><span class="sum-n">${fieldCount}</span><span class="sum-l">fields auto-filled</span></div>
      <div class="sum-i"><span class="sum-n">0</span><span class="sum-l">manual keystrokes</span></div>
    </div>`;
}
