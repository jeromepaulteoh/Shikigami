// Upload — handles real file uploads to backend for extraction
(function () {
  const uploadArea = document.getElementById('uz');
  const fileInput = document.getElementById('file-input');

  uploadArea.addEventListener('click', () => fileInput.click());

  uploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadArea.style.borderColor = 'var(--accent)';
    uploadArea.style.background = 'var(--accent-soft)';
  });

  uploadArea.addEventListener('dragleave', () => {
    uploadArea.style.borderColor = '';
    uploadArea.style.background = '';
  });

  uploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadArea.style.borderColor = '';
    uploadArea.style.background = '';
    handleFiles(e.dataTransfer.files);
  });

  fileInput.addEventListener('change', () => {
    handleFiles(fileInput.files);
    fileInput.value = '';
  });
})();

async function handleFiles(fileList) {
  if (!fileList.length) return;
  document.getElementById('uz').style.display = 'none';
  const container = document.getElementById('ufiles');
  container.innerHTML = '';

  for (const file of fileList) {
    const ext = file.name.split('.').pop().toLowerCase();
    const typeClass = ext === 'pdf' ? 'uf-pdf' : (ext === 'xlsx' || ext === 'xls') ? 'uf-xls' : 'uf-img';

    // Show file with progress bar
    const el = document.createElement('div');
    el.className = 'uf';
    el.innerHTML = `
      <div class="uf-icon ${typeClass}">${ext.toUpperCase()}</div>
      <div class="uf-info">
        <div class="uf-name">${file.name}</div>
        <div class="uf-det">${formatSize(file.size)}</div>
      </div>
      <div class="uf-status">
        <div class="uf-prog"><div class="uf-bar" style="width:0%"></div></div>
      </div>`;
    container.appendChild(el);

    const bar = el.querySelector('.uf-bar');
    const statusEl = el.querySelector('.uf-status');

    try {
      // Upload to backend
      bar.style.width = '30%';
      const formData = new FormData();
      formData.append('file', file);
      formData.append('clientId', state.currentClient);

      const res = await fetch(API + '/api/upload', { method: 'POST', body: formData });
      bar.style.width = '100%';

      const result = await res.json();
      state.uploadedFiles.push(result);

      // Show extracted fields
      setTimeout(() => {
        const extractedText = result.extractedFields
          ? result.extractedFields.join(', ')
          : 'Processed';
        statusEl.innerHTML = `<span style="font-size:.7rem;font-weight:500;color:var(--green)">&#10003; ${extractedText}</span>`;
      }, 300);
    } catch (err) {
      statusEl.innerHTML = `<span style="font-size:.7rem;font-weight:500;color:var(--warm)">&#10007; Upload failed</span>`;
    }
  }

  // Show continue button
  setTimeout(() => {
    document.getElementById('uact').style.display = 'flex';
  }, 500);
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1048576) return (bytes / 1024).toFixed(0) + ' KB';
  return (bytes / 1048576).toFixed(1) + ' MB';
}
