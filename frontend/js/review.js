// Review — fetches pre-populated fields from backend, renders flags
async function loadReview() {
  try {
    const res = await fetch(API + '/api/clients/' + state.currentClient + '/review');
    const data = await res.json();
    state.extractedFields = data.fields;

    document.getElementById('fields-count').textContent = data.fields.length + ' fields extracted';
    renderReviewFields(data.fields);
    renderReviewFlags(data.flags);
  } catch (err) {
    console.error('Failed to load review:', err);
  }
}

function renderReviewFields(fields) {
  const el = document.getElementById('review-fields');
  let html = '';
  let currentSection = '';

  fields.forEach(f => {
    if (f.section !== currentSection) {
      const sectionStyle = f.sectionWarning ? ' style="color:var(--warm)"' : '';
      const prefix = f.sectionWarning ? '&#9888; ' : '';
      html += `<div class="fsl"${sectionStyle}>${prefix}${f.section}</div>`;
      currentSection = f.section;
    }

    const statusClass = f.status === 'ok' ? 'dg' : f.status === 'warn' ? 'da' : 'dr';
    const statusChar = f.status === 'ok' ? '&#10003;' : f.status === 'warn' ? '?' : '!';
    const valueClass = f.missing ? 'ff-v wbg empty' : f.needsReview ? 'ff-v wbg' : 'ff-v';
    const displayValue = f.missing ? 'Not declared' : f.value;

    html += `
      <div class="ff" id="rf-${f.id}">
        <span class="ff-l">${f.label}</span>
        <span class="${valueClass}">${displayValue}</span>
        <span class="ff-d ${statusClass}">${statusChar}</span>
      </div>`;
  });

  el.innerHTML = html;
}

function renderReviewFlags(flags) {
  if (!flags || !flags.length) return;
  state.requiredFlags = flags.length;
  state.resolvedFlags = 0;

  const container = document.getElementById('review-flags');
  container.innerHTML = flags.map((f, i) => {
    const cls = f.severity === 'warning' ? 'fw' : 'fi2';
    const icon = f.severity === 'warning' ? '&#9888;' : '&#8505;';
    return `
      <div class="fflag ${cls}" id="flag-${i}">
        <span>${icon}</span>
        <div>
          <strong>${f.type}:</strong> ${f.message}<br>
          <span class="fr-btn" onclick="resolveFlag(${i}, ${JSON.stringify(f.resolution).replace(/"/g, '&quot;')})">&#10003; ${f.resolveLabel}</span>
        </div>
      </div>`;
  }).join('');
}

function resolveFlag(index, resolution) {
  document.getElementById('flag-' + index).style.display = 'none';
  state.resolvedFlags++;

  // Update any associated fields
  if (resolution && resolution.fieldUpdates) {
    resolution.fieldUpdates.forEach(u => {
      const fieldEl = document.getElementById('rf-' + u.fieldId);
      if (fieldEl) {
        fieldEl.innerHTML = `
          <span class="ff-l">${u.label}</span>
          <span class="ff-v">${u.value}</span>
          <span class="ff-d dg">&#10003;</span>`;
      }
    });
  }

  checkFlagsResolved();
}

function checkFlagsResolved() {
  if (state.resolvedFlags >= state.requiredFlags) {
    const btn = document.getElementById('fill-btn');
    btn.style.opacity = '1';
    btn.style.pointerEvents = 'auto';
  }
}

// Auto-load review when step 3 is shown
const origGoP = goP;
goP = function (n) {
  if (n === 3) loadReview();
  origGoP(n);
};
