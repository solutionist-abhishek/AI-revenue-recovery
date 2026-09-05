const gatewayCode = document.getElementById('gateway-code');
const gatewayMessage = document.getElementById('gateway-message');
const classifyBtn = document.getElementById('classify-btn');
const recoverBtn = document.getElementById('recover-btn');
const resetBtn = document.getElementById('reset-btn');
const runRecoveryBtn = document.getElementById('run-recovery-btn');
const recoveryResult = document.getElementById('recovery-result');
const classificationResult = document.getElementById('classification-result');
const decisionResult = document.getElementById('decision-result');
const classTag = document.getElementById('class-tag');
const decisionTag = document.getElementById('decision-tag');
const summaryGrid = document.getElementById('summary-grid');
const opportunityList = document.getElementById('opportunity-list');
const caseDetail = document.getElementById('case-detail');
const activityFeed = document.getElementById('activity-feed');
const auditFeed = document.getElementById('audit-feed');
const simulationGrid = document.getElementById('simulation-grid');
const reportSummary = document.getElementById('report-summary');
const chartBox = document.getElementById('chart-box');
const paymentsTableBody = document.querySelector('#payments-table tbody');
const uploadBtn = document.getElementById('upload-btn');
const exportBtn = document.getElementById('export-btn');
const uploadFile = document.getElementById('upload-file');
const loginBtn = document.getElementById('login-btn');
const logoutBtn = document.getElementById('logout-btn');
const loginPanel = document.getElementById('login-panel');
const appShell = document.getElementById('app-shell');
const currentUser = document.getElementById('current-user');
const loginUsername = document.getElementById('login-username');
const loginPassword = document.getElementById('login-password');
const recoveryStatus = document.getElementById('recovery-status');

const gatewayMessages = {
  NSF: ['insufficient_funds'],
  GATEWAY_ERROR: ['gateway error', 'network error'],
  TIMEOUT: ['timeout', 'network error'],
  BAD_REQUEST_ERROR: ['invalid_cvv'],
  RISK_DECLINE: ['card blocked', 'fraud suspected', 'stolen card'],
};

function updateGatewayMessages() {
  const messages = gatewayMessages[gatewayCode.value] || ['unknown payment failure'];
  gatewayMessage.innerHTML = messages
    .map((message) => `<option value="${message}">${message}</option>`)
    .join('');
}

function setTag(element, label, variant) {
  element.textContent = label;
  element.className = `tag ${variant}`;
}

function renderClassification(payload) {
  const category = payload.category || 'unknown';
  const confidence = payload.confidence || 0;
  const reason = payload.normalized_reason || 'unknown';
  const variant = category === 'retryable' ? 'success' : category === 'non_retryable' ? 'danger' : 'warning';

  setTag(classTag, category, variant);
  classificationResult.className = 'result-box';
  classificationResult.innerHTML = `
    <div><strong>Category:</strong> ${category}</div>
    <div><strong>Reason:</strong> ${reason}</div>
    <div><strong>Confidence:</strong> ${(confidence * 100).toFixed(0)}%</div>
    <div><strong>Gateway code:</strong> ${gatewayCode.value || '—'}</div>
    <div><strong>Gateway message:</strong> ${gatewayMessage.value || '—'}</div>
  `;
}

function renderDecision(payload) {
  const shouldRetry = payload.should_retry;
  const reason = payload.stop_reason || payload.reason || 'n/a';
  const maxAttempts = payload.max_attempts ?? 0;
  const schedule = payload.retry_schedule_minutes?.length ? payload.retry_schedule_minutes.join(', ') : 'none';

  setTag(decisionTag, shouldRetry ? 'Retry' : 'Stop', shouldRetry ? 'success' : 'danger');
  decisionResult.className = 'result-box';
  decisionResult.innerHTML = `
    <div><strong>Should retry:</strong> ${shouldRetry}</div>
    <div><strong>Reason:</strong> ${reason}</div>
    <div><strong>Max attempts:</strong> ${maxAttempts}</div>
    <div><strong>Retry windows (minutes):</strong> ${schedule}</div>
  `;
}

function setEmptyState() {
  classificationResult.className = 'result-box empty';
  decisionResult.className = 'result-box empty';
  classificationResult.textContent = 'Enter a gateway error to start.';
  decisionResult.textContent = 'Recovery logic will appear here.';
  setTag(classTag, 'Pending', 'neutral');
  setTag(decisionTag, 'Pending', 'neutral');
}

function formatCurrency(value) {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(value);
}

function renderSummary(summary) {
  const cards = [
    { label: 'Revenue at risk', value: formatCurrency(summary.revenue_at_risk) },
    { label: 'Expected recovery', value: formatCurrency(summary.expected_recovery) },
    { label: 'Recovery rate', value: `${summary.top_recovery_rate}%` },
    { label: 'High-priority cases', value: summary.high_priority_cases },
  ];

  summaryGrid.innerHTML = cards
    .map(
      (card) => `
        <div class="metric-card">
          <div class="metric-label">${card.label}</div>
          <div class="metric-value">${card.value}</div>
        </div>
      `,
    )
    .join('');
}

function renderOpportunities(opportunities) {
  opportunityList.innerHTML = opportunities
    .slice(0, 5)
    .map(
      (item, index) => `
        <div class="opportunity-item ${index === 0 ? 'active' : ''}" data-index="${index}">
          <div class="opportunity-header">
            <span class="opportunity-name">#${index + 1} ${item.customer}</span>
            <span class="tag ${item.risk === 'LOW' ? 'success' : item.risk === 'MEDIUM' ? 'warning' : 'danger'}">${item.risk}</span>
          </div>
          <div>${item.failure}</div>
          <div class="opportunity-header">
            <small>${formatCurrency(item.amount)}</small>
            <strong>${item.recoverability * 100}%</strong>
          </div>
          <div class="opportunity-header">
            <small>Expected</small>
            <strong>${formatCurrency(item.expected_recovery)}</strong>
          </div>
        </div>
      `,
    )
    .join('');

  const rows = [...document.querySelectorAll('.opportunity-item')];
  rows.forEach((row) => {
    row.addEventListener('click', () => {
      rows.forEach((item) => item.classList.remove('active'));
      row.classList.add('active');
      const selected = opportunities[Number(row.dataset.index)];
      renderCaseDetail(selected);
    });
  });

  if (opportunities.length) {
    renderCaseDetail(opportunities[0]);
  }
}

function renderCaseDetail(item) {
  if (!item) {
    caseDetail.textContent = 'Select a case to inspect the reasoning.';
    caseDetail.className = 'case-detail empty';
    return;
  }

  caseDetail.className = 'case-detail';
  caseDetail.innerHTML = `
    <div><strong>₹${item.amount.toLocaleString('en-IN')}</strong> at risk</div>
    <div><strong>AI DECISION</strong></div>
    <div>Recoverability: ${item.recoverability * 100}%</div>
    <div>Expected recovery: ${formatCurrency(item.expected_recovery)}</div>
    <div>Risk: ${item.risk}</div>
    <div>Confidence: ${(item.confidence * 100).toFixed(0)}%</div>
    <div><strong>Recommended action</strong> → ${item.recommended_action}</div>
    <div><strong>WHY?</strong></div>
    <ul>
      ${item.reasons.map((reason) => `<li>${reason}</li>`).join('')}
    </ul>
    <div>Approval required → ${item.approval_required ? 'YES' : 'NO'}</div>
  `;
}

function renderActivityFeed(events = []) {
  const defaultEvents = [
    'Recovery queue initialized',
    'AI diagnostics loaded',
    'Policy guardrails enabled',
    'Operational dashboard ready',
  ];

  const timeline = events.length ? events : defaultEvents;
  activityFeed.innerHTML = timeline
    .map(
      (event) => `
        <div class="activity-item">${event}</div>
      `,
    )
    .join('');
}

function renderAuditFeed(events = []) {
  auditFeed.className = events.length ? 'audit-feed' : 'audit-feed empty';
  auditFeed.innerHTML = events.length
    ? events.map((event) => `
        <div class="audit-item">
          <div><strong>${event.event_id}</strong><span class="tag ${event.status === 'recorded' ? 'success' : 'neutral'}">${event.status}</span></div>
          <small>${event.action} · ${event.reason} · ${event.actor}</small>
        </div>
      `).join('')
    : 'No webhook decisions recorded yet.';
}

function buildRecoveryTimeline(summary, opportunities, strategy) {
  const topCase = opportunities[0];
  const bestStrategy = strategy?.strategies?.[strategy.strategies.length - 1];

  return [
    `Portfolio scan complete: ${summary.high_priority_cases} high-priority cases identified.`,
    `Recovery value at risk: ${formatCurrency(summary.revenue_at_risk)}.`,
    `Expected recovery: ${formatCurrency(summary.expected_recovery)} (${summary.top_recovery_rate}% rate).`,
    `${topCase.customer} ranked first with ${formatCurrency(topCase.expected_recovery)} expected recovery.`,
    `${bestStrategy?.name || 'AI-assisted strategy'} projected at ${formatCurrency(bestStrategy?.expected_recovery || 0)}.`,
    'Policy guardrails validated; human approval required only where threshold rules apply.',
  ];
}

function renderRecoveryRun(result) {
  const timeline = result.actions.map((item) => {
    const status = item.status === 'approval_required' ? 'Awaiting human approval' : 'Queued automatically';
    return `${item.customer}: ${item.action} | ${status} | ${formatCurrency(item.expected_recovery)} expected.`;
  });

  renderActivityFeed([
    `Recovery run completed by ${result.operator}.`,
    `${result.queued_actions} actions queued automatically; ${result.approval_required} require human approval.`,
    `Expected recovery from this run: ${formatCurrency(result.expected_recovery)}.`,
    ...timeline,
  ]);
  recoveryResult.className = 'run-result success';
  recoveryResult.innerHTML = `
    <strong>Run complete</strong>
    <span>${result.queued_actions} queued · ${result.approval_required} approval pending</span>
    <b>${formatCurrency(result.expected_recovery)} expected</b>
  `;
}

function renderSimulation(data) {
  simulationGrid.innerHTML = data.strategies
    .map(
      (strategy) => `
        <div class="strategy-item">
          <div class="strategy-row"><strong>${strategy.name}</strong><span>${formatCurrency(strategy.expected_recovery)}</span></div>
          <div class="strategy-row"><small>Additional revenue</small><span>+${formatCurrency(strategy.delta)}</span></div>
        </div>
      `,
    )
    .join('');
}

function renderReport(report) {
  reportSummary.innerHTML = [
    { label: 'Failed', value: report.summary.total_failed },
    { label: 'At risk', value: formatCurrency(report.summary.total_at_risk) },
    { label: 'Expected', value: formatCurrency(report.summary.expected_recovery) },
    { label: 'Retryable', value: report.summary.retryable },
  ]
    .map(
      (card) => `
        <div class="report-card">
          <div class="metric-label">${card.label}</div>
          <div class="metric-value">${card.value}</div>
        </div>
      `,
    )
    .join('');

  const minValue = 10;
  const maxValue = Math.max(...report.chart.map((item) => item.value), 1);
  chartBox.innerHTML = report.chart
    .map(
      (item) => `
        <div class="chart-bar" style="height: ${Math.max((item.value / maxValue) * 130, minValue)}px;">
          <span>${item.value}</span>
        </div>
      `,
    )
    .join('');

  paymentsTableBody.innerHTML = report.records
    .map(
      (item) => `
        <tr>
          <td>${item.customer}</td>
          <td>${formatCurrency(item.amount)}</td>
          <td>${item.failure}</td>
          <td>${item.recoverability * 100}%</td>
          <td>${formatCurrency(item.expected_recovery)}</td>
          <td>${item.status}</td>
        </tr>
      `,
    )
    .join('');
}

async function loadSession() {
  try {
    const response = await fetch('/me');
    if (!response.ok) {
      showLogin();
      return null;
    }

    const user = await response.json();
    showApp(user);
    await loadDashboard();
    await loadSimulation();
    await loadReport();
    await loadAudit();
    return user;
  } catch (error) {
    showLogin();
    return null;
  }
}

async function login() {
  const username = loginUsername.value.trim();
  const password = loginPassword.value.trim();

  try {
    const response = await fetch('/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });

    if (!response.ok) {
      throw new Error('Invalid username or password');
    }

    const user = await response.json();
    showApp(user);
    await loadDashboard();
    await loadSimulation();
    await loadReport();
    await loadAudit();
  } catch (error) {
    alert(error.message);
  }
}

async function logout() {
  await fetch('/logout', { method: 'POST' });
  showLogin();
}

function showLogin() {
  loginPanel.classList.remove('hidden');
  appShell.classList.add('hidden');
  currentUser.textContent = 'Signed out';
  logoutBtn.classList.add('hidden');
}

function showApp(user) {
  loginPanel.classList.add('hidden');
  appShell.classList.remove('hidden');
  currentUser.textContent = `${user.name} • ${user.role}`;
  logoutBtn.classList.remove('hidden');
}

async function loadDashboard() {
  try {
    const response = await fetch('/dashboard');
    if (!response.ok) {
      showLogin();
      return null;
    }

    const data = await response.json();
    renderSummary(data.summary);
    renderOpportunities(data.opportunities);
    return data;
  } catch (error) {
    console.error('Dashboard load failed:', error);
    showLogin();
    return null;
  }
}

async function runRecovery() {
  runRecoveryBtn.disabled = true;
  runRecoveryBtn.textContent = 'Running recovery...';
  setTag(recoveryStatus, 'Running', 'warning');
  recoveryResult.className = 'run-result running';
  recoveryResult.textContent = 'Scanning ranked payments and applying guardrails...';

  try {
    const response = await fetch('/recovery-run', { method: 'POST' });
    if (!response.ok) {
      throw new Error(`Recovery run failed with status ${response.status}`);
    }

    const result = await response.json();
    renderRecoveryRun(result);
    await loadAudit();
    setTag(recoveryStatus, `${result.approval_required} approval pending`, result.approval_required ? 'warning' : 'success');
  } catch (error) {
    setTag(recoveryStatus, 'Failed', 'danger');
    recoveryResult.className = 'run-result error';
    recoveryResult.textContent = error.message;
    renderActivityFeed([`Recovery run failed: ${error.message}`]);
  } finally {
    runRecoveryBtn.disabled = false;
    runRecoveryBtn.textContent = '▶ Run Recovery';
  }
}

async function loadAudit() {
  try {
    const response = await fetch('/audit');
    if (!response.ok) {
      return null;
    }
    const data = await response.json();
    renderAuditFeed(data);
    return data;
  } catch (error) {
    console.error('Audit load failed:', error);
    return null;
  }
}

async function loadSimulation() {
  try {
    const response = await fetch('/simulate');
    const data = await response.json();
    renderSimulation(data);
    return data;
  } catch (error) {
    console.error('Simulation load failed:', error);
    return null;
  }
}

async function loadReport() {
  try {
    const response = await fetch('/report');
    const data = await response.json();
    renderReport(data);
    return data;
  } catch (error) {
    console.error('Report load failed:', error);
    return null;
  }
}

async function uploadBatch() {
  const file = uploadFile.files[0];
  if (!file) {
    alert('Please choose a JSON file first.');
    return;
  }

  try {
    const text = await file.text();
    const json = JSON.parse(text);
    const payload = { payments: json.payments || json || [] };

    const response = await fetch('/upload', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error(`Upload failed with status ${response.status}`);
    }

    const result = await response.json();
    alert(`${result.count} payments uploaded successfully.`);
    await loadReport();
  } catch (error) {
    alert(`Upload failed: ${error.message}`);
  }
}

async function exportReport() {
  try {
    const response = await fetch('/report');
    const data = await response.json();
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'recoverpay-report.json';
    a.click();
    URL.revokeObjectURL(url);
  } catch (error) {
    alert(`Export failed: ${error.message}`);
  }
}

async function callApi(endpoint) {
  const payload = {
    gateway_code: gatewayCode.value,
    gateway_message: gatewayMessage.value,
  };

  if (!payload.gateway_code.trim() && !payload.gateway_message.trim()) {
    setEmptyState();
    return;
  }

  try {
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error(`Request failed with status ${response.status}`);
    }

    const data = await response.json();

    if (endpoint === '/classify') {
      renderClassification(data);
    } else {
      renderClassification(data.classification);
      renderDecision(data.decision);
    }
  } catch (error) {
    classificationResult.className = 'result-box';
    decisionResult.className = 'result-box';
    classificationResult.textContent = `Error: ${error.message}`;
    decisionResult.textContent = 'Please check that the backend is running.';
    setTag(classTag, 'Error', 'danger');
    setTag(decisionTag, 'Error', 'danger');
  }
}

classifyBtn.addEventListener('click', () => callApi('/classify'));
recoverBtn.addEventListener('click', () => callApi('/recover'));
resetBtn.addEventListener('click', () => {
  gatewayCode.value = 'NSF';
  updateGatewayMessages();
  setEmptyState();
});
gatewayCode.addEventListener('change', updateGatewayMessages);
runRecoveryBtn.addEventListener('click', runRecovery);
loginBtn.addEventListener('click', login);
logoutBtn.addEventListener('click', logout);
uploadBtn.addEventListener('click', uploadBatch);
exportBtn.addEventListener('click', exportReport);

setEmptyState();
updateGatewayMessages();
renderActivityFeed();
showLogin();
loadSession();
