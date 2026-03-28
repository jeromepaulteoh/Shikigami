const express = require('express');
const router = express.Router();

// Client data — TODO: replace with database
const clients = {
  'apex-trading': {
    id: 'apex-trading',
    name: 'Apex Trading Pte Ltd',
    uen: '201912345A',
    filingType: 'ACRA Annual Return FY2025',
    fye: '31 December 2025',
    lastFiled: '14 Mar 2025',
    deadline: '30 Apr 2026',
    changes: [
      {
        severity: 'warning',
        title: 'New: RONS/ROND registers now mandatory',
        description: 'Annual Return includes compliance declaration for nominee registers. Not required in your last filing.',
        meta: '16 Jun 2025 \u00B7 Penalty: up to S$25,000',
      },
      {
        severity: 'warning',
        title: 'CSP Act 2024 AML/CFT obligations',
        description: 'Source-of-wealth verification required before filing. Confirm records are current.',
        meta: '9 Jun 2025 \u00B7 Corporate Service Providers Act 2024',
      },
      {
        severity: 'info',
        title: 'BizFile+ portal redesigned',
        description: 'Interface updated December 2024. Form template aligned.',
        meta: 'Dec 2024 \u00B7 ACRA BizFile+',
      },
      {
        severity: 'ok',
        title: 'No changes to: deadlines, AGM rules, FYE requirements',
        description: 'All other requirements unchanged.',
        meta: 'Verified today',
      },
    ],
    bizfileFields: [
      { section: 'Section A: Company Information', label: 'Company Name', value: 'Apex Trading Pte Ltd' },
      { section: 'Section A: Company Information', label: 'UEN', value: '201912345A' },
      { section: 'Section A: Company Information', label: 'Registered Address', value: '71 Robinson Road #14-01, Singapore 068895' },
      { section: 'Section A: Company Information', label: 'Financial Year End', value: '31 December 2025' },
      { section: 'Section A: Company Information', label: 'Date of AGM', value: '15 March 2026' },
      { section: 'Section A: Company Information', label: 'Revenue (S$)', value: '2,847,300' },
      { section: 'Section B: Directors', label: 'Director 1', value: 'Lim Kai Wen (S8XXXXXXXA) \u2014 Singaporean' },
      { section: 'Section B: Directors', label: 'Director 2', value: 'Chen Wei Ming (A52XXXXXX) \u2014 Malaysian' },
      { section: 'Section C: Nominee Registers (New)', label: 'RONS maintained?', value: 'Yes' },
      { section: 'Section C: Nominee Registers (New)', label: 'ROND maintained?', value: 'Yes' },
      { section: 'Section C: Nominee Registers (New)', label: 'Nominee shareholders?', value: 'No' },
    ],
  },
};

// GET /api/clients/:id
router.get('/:id', (req, res) => {
  const client = clients[req.params.id];
  if (!client) return res.status(404).json({ error: 'Client not found' });
  res.json(client);
});

// GET /api/clients/:id/review — returns extracted fields + flags for review step
router.get('/:id/review', (req, res) => {
  const client = clients[req.params.id];
  if (!client) return res.status(404).json({ error: 'Client not found' });

  // TODO: Pull these from actual extracted document data
  res.json({
    fields: [
      { id: 'company-name', section: 'Company Particulars', label: 'Company name', value: 'Apex Trading Pte Ltd', status: 'ok' },
      { id: 'uen', section: 'Company Particulars', label: 'UEN', value: '201912345A', status: 'ok' },
      { id: 'address', section: 'Company Particulars', label: 'Registered address', value: '71 Robinson Rd #14-01, S(068895)', status: 'ok' },
      { id: 'fye', section: 'Company Particulars', label: 'Financial year-end', value: '31 December 2025', status: 'ok' },
      { id: 'agm', section: 'Company Particulars', label: 'AGM date', value: '15 March 2026', status: 'ok' },
      { id: 'revenue', section: 'Company Particulars', label: 'Revenue', value: 'S$2,847,300', status: 'warn' },
      { id: 'dir1', section: 'Directors & Shareholders', label: 'Director 1', value: 'Lim Kai Wen (S8XXXXXXXA)', status: 'ok' },
      { id: 'dir2', section: 'Directors & Shareholders', label: 'Director 2', value: 'Chen Wei Ming (A52XXXXXX)', status: 'warn' },
      { id: 'rons', section: 'Nominee Registers (New)', sectionWarning: true, label: 'RONS maintained?', value: null, status: 'error', missing: true },
      { id: 'rond', section: 'Nominee Registers (New)', sectionWarning: true, label: 'ROND maintained?', value: null, status: 'error', missing: true },
    ],
    flags: [
      {
        severity: 'warning',
        type: 'Action',
        message: 'Confirm with client re Apex Holdings Ltd (BVI) nominee status.',
        resolveLabel: 'Resolved \u2014 no nominees',
        resolution: {
          fieldUpdates: [
            { fieldId: 'rons', label: 'RONS maintained?', value: 'Yes \u2014 no nominees' },
            { fieldId: 'rond', label: 'ROND maintained?', value: 'Yes \u2014 no nominees' },
          ],
        },
      },
      {
        severity: 'info',
        type: 'Note',
        message: 'Director Chen Wei Ming passport expires Aug 2026.',
        resolveLabel: 'Client notified',
        resolution: {},
      },
    ],
  });
});

module.exports = router;
