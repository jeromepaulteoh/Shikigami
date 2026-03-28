const express = require('express');
const router = express.Router();

// GET /api/dashboard
router.get('/', (req, res) => {
  // TODO: Replace with database queries
  res.json({
    stats: [
      { label: 'Active clients', value: 187, class: '' },
      { label: 'Filings due', value: 12, class: 'warn' },
      { label: 'Rule changes this week', value: 3, class: 'warn' },
      { label: 'Completed', value: 34, class: 'green' },
    ],
    filings: [
      {
        client: 'Apex Trading Pte Ltd',
        filing: 'ACRA Annual Return',
        deadline: '30 Apr 2026',
        status: 'Due 34 days',
        statusClass: 'due',
        alerts: '\u26A0 2 changes',
      },
      {
        client: 'Meridian Capital Advisory',
        filing: 'MAS Form 1A',
        deadline: '15 May 2026',
        status: 'In progress',
        statusClass: 'ok',
        alerts: '\u26A0 5 changes',
      },
      {
        client: 'Horizon Marine Services',
        filing: 'MOM EP Renewal (x3)',
        deadline: '12 Apr 2026',
        status: 'Due 16 days',
        statusClass: 'due',
        alerts: '\u26A0 1 update',
      },
    ],
  });
});

module.exports = router;
