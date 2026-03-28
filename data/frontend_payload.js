window.REGULATOR_PAYLOAD = {
  generated_at: "2026-03-28T09:04:00+08:00",
  client_name: "Atlas Restructuring Pte Ltd",
  workflow_name: "Withdrawal from Being Approved Liquidators",
  breadcrumb_name: "Atlas Restructuring",
  canary_status: "changed",
  stats: [
    ["Tracked fields", "5", ""],
    ["Review required", "2", "warn"],
    ["Missing", "1", "warn"],
    ["High confidence", "2", "ok"]
  ],
  table: [
    [
      "Atlas Restructuring Pte Ltd",
      "Withdrawal from Being Approved Liquidators",
      "28 Mar 2026, 09:02 AM",
      "2 changes",
      "warn",
      "graph refresh"
    ]
  ],
  changes: [
    {
      kind: "warn",
      title: "Eligibility wording changed on ACRA guidance page",
      desc: "Semantic diff marked the withdrawal eligibility language as material. The affected graph branch has been queued for refresh.",
      meta: "Node diff | material | section 3 guidance"
    },
    {
      kind: "warn",
      title: "Supporting document list expanded",
      desc: "Current extract includes an additional document expectation for withdrawal submissions.",
      meta: "Version history delta | detected this run"
    },
    {
      kind: "info",
      title: "Top-level navigation drift detected",
      desc: "Canary noticed site-structure drift. Maintenance rebuild should refresh the broader graph baseline.",
      meta: "Canary status | changed but non-blocking"
    }
  ],
  uploads: [
    ["acra_withdrawal_form.pdf", "Simulated preprocess", "OpenAI derives structured fields and TinyFish goals from the uploaded form"],
    ["supporting_statement.pdf", "Simulated preprocess", "Narrative grounds are normalized into reviewable field context"],
    ["regulatory_correspondence.pdf", "Simulated preprocess", "References are linked to graph nodes for deeper trace"]
  ],
  groups: [
    [
      "Withdrawal request",
      [
        ["Correct description/wording for withdrawal from approved liquidators lodgement on BizFile+", "Pending extraction", "review"],
        ["List of supporting documents required for withdrawal from approved liquidators", "Identity document, signed statement, supporting correspondence", "ok"]
      ]
    ],
    [
      "Supporting materials",
      [
        ["Which PDF form must be downloaded and attached for withdrawal from approved liquidators", "Pending extraction", "missing"]
      ]
    ],
    [
      "Regulatory checks",
      [
        ["Eligibility criteria and prerequisites for withdrawing as an approved liquidator", "Updated wording requires analyst review", "review"],
        ["Filing fees for withdrawal from approved liquidators on BizFile+", "No filing fee indicated", "ok"]
      ]
    ]
  ],
  actions: [
    ["warnbox", "Action", "Which PDF form must be downloaded and attached for withdrawal from approved liquidators: Requires analyst confirmation before simulated fill.", "Resolved - evidence attached"],
    ["notebox", "Note", "Eligibility criteria and prerequisites for withdrawing as an approved liquidator: Updated wording requires analyst review.", "Reviewed - accept updated wording"]
  ],
  fill: [
    ["Correct description/wording for withdrawal from approved liquidators lodgement on BizFile+", "Pending extraction"],
    ["Which PDF form must be downloaded and attached for withdrawal from approved liquidators", "Pending extraction"],
    ["List of supporting documents required for withdrawal from approved liquidators", "Identity document, signed statement, supporting correspondence"],
    ["Eligibility criteria and prerequisites for withdrawing as an approved liquidator", "Updated wording requires analyst review"],
    ["Filing fees for withdrawal from approved liquidators on BizFile+", "No filing fee indicated"]
  ],
  summary: {
    changes: 2,
    rebuilds: 1,
    simulated_fields: 5,
    real_submissions: 0,
    completion_ratio: 0.4
  }
};
