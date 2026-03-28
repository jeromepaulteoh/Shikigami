// Core app state and navigation
const API = '';  // Same origin — served by Express

const state = {
  currentScreen: 'dashboard',
  currentClient: null,
  currentStep: 1,
  timerInterval: null,
  timerSeconds: 0,
  resolvedFlags: 0,
  requiredFlags: 0,
  uploadedFiles: [],
  extractedFields: [],
};

// Navigation
function showScreen(name) {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('visible'));
  document.getElementById('screen-' + name).classList.add('visible');
  state.currentScreen = name;

  if (name === 'dashboard') {
    document.getElementById('bc').innerHTML = '<span>Dashboard</span>';
    document.getElementById('timer').style.display = 'none';
    stopTimer();
    loadDashboard();
  }
  if (name === 'client') {
    document.getElementById('bc').innerHTML =
      '<span style="color:var(--text4);cursor:pointer" onclick="showScreen(\'dashboard\')">Dashboard</span>' +
      '<span style="color:var(--text4)"> / </span><strong>Apex Trading</strong>';
    document.getElementById('timer').style.display = 'flex';
    resetTimer();
    startTimer();
    loadClient('apex-trading');
  }
}

// Step navigation
function goP(n) {
  state.currentStep = n;
  for (let i = 1; i <= 5; i++) {
    document.getElementById('p' + i).style.display = i === n ? 'block' : 'none';
    const s = document.getElementById('si' + i);
    if (i < n) s.className = 'si done';
    else if (i === n) s.className = 'si active';
    else s.className = 'si';
  }
  document.querySelector('.content').scrollTop = 0;

  if (n === 4) startAutofill();
  if (n === 5) stopTimer();
}

// Timer
function startTimer() {
  state.timerInterval = setInterval(() => {
    state.timerSeconds++;
    const m = Math.floor(state.timerSeconds / 60);
    const s = state.timerSeconds % 60;
    document.getElementById('tv').textContent = m + ':' + (s < 10 ? '0' : '') + s;
  }, 1000);
}
function stopTimer() { clearInterval(state.timerInterval); }
function resetTimer() {
  stopTimer();
  state.timerSeconds = 0;
  document.getElementById('tv').textContent = '0:00';
}
function getElapsed() {
  const m = Math.floor(state.timerSeconds / 60);
  const s = state.timerSeconds % 60;
  return m + ':' + (s < 10 ? '0' : '') + s;
}

// Clock
function updateClock() {
  const now = new Date();
  document.getElementById('clock').textContent = now.toLocaleDateString('en-SG', {
    day: 'numeric', month: 'short', year: 'numeric'
  }) + ', ' + now.toLocaleTimeString('en-SG', { hour: 'numeric', minute: '2-digit' });
}
updateClock();
setInterval(updateClock, 60000);

// Init
loadDashboard();
