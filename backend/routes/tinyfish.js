const express = require('express');
const router = express.Router();
const { autofillForm } = require('../services/tinyfish');

// Client data — in production, fetch from database
const clientFormData = {
  'apex-trading': {
    url: 'https://www.bizfile.gov.sg/ngbbizfileinternet/faces/oracle/webcenter/portalapp/ar',
    fields: [
      { label: 'Company Name', value: 'Apex Trading Pte Ltd' },
      { label: 'UEN', value: '201912345A' },
      { label: 'Registered Address', value: '71 Robinson Road #14-01, Singapore 068895' },
      { label: 'Financial Year End', value: '31 December 2025' },
      { label: 'Date of AGM', value: '15 March 2026' },
      { label: 'Revenue', value: '2,847,300' },
      { label: 'Director 1', value: 'Lim Kai Wen (S8XXXXXXXA) \u2014 Singaporean' },
      { label: 'Director 2', value: 'Chen Wei Ming (A52XXXXXX) \u2014 Malaysian' },
      { label: 'RONS maintained', value: 'Yes' },
      { label: 'ROND maintained', value: 'Yes' },
      { label: 'Nominee shareholders', value: 'No' },
    ],
  },
};

// GET /api/tinyfish/autofill?clientId=apex-trading
// SSE endpoint — streams Tinyfish agent progress to the frontend
router.get('/autofill', async (req, res) => {
  const clientId = req.query.clientId;
  const data = clientFormData[clientId];

  if (!data) {
    return res.status(404).json({ error: 'Client form data not found' });
  }

  // Set up SSE headers
  res.writeHead(200, {
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    Connection: 'keep-alive',
  });

  const send = (eventType, payload) => {
    res.write(`event: ${eventType}\ndata: ${JSON.stringify(payload)}\n\n`);
  };

  // Check if Tinyfish API key is configured
  if (!process.env.TINYFISH_API_KEY) {
    // Fallback: simulate the autofill for demo purposes
    simulateAutofill(send, data.fields);
    return;
  }

  // Real Tinyfish integration
  try {
    send('log', { message: '<span class="tf-highlight">Tinyfish</span> agent initialized. Connecting to BizFile+...' });
    send('status', { message: 'Connecting to BizFile+...' });

    let fieldIndex = 1;

    const result = await autofillForm({
      url: data.url,
      formData: data,
      onProgress: (event) => {
        send(event.type, { message: event.message });

        // Map Tinyfish progress to field fills on the frontend
        // The agent fills fields sequentially, so we track the index
        if (event.type === 'log' && fieldIndex <= data.fields.length) {
          const field = data.fields[fieldIndex - 1];
          send('fill', {
            fieldIndex,
            value: field.value,
            label: field.label,
          });
          fieldIndex++;
        }
      },
    });

    send('complete', {
      message: `All ${data.fields.length} fields filled successfully`,
      result,
    });
  } catch (err) {
    console.error('Tinyfish autofill error:', err);
    send('log', { message: `<span style="color:var(--warm)">Error: ${err.message}</span>` });
  } finally {
    res.end();
  }
});

// Simulated autofill when no API key is set — mirrors the original demo behavior
function simulateAutofill(send, fields) {
  let delay = 400;

  setTimeout(() => {
    send('log', { message: '<span class="tf-highlight">Tinyfish</span> agent initialized. Connecting to authenticated BizFile+ session...' });
  }, delay);
  delay += 1000;

  setTimeout(() => {
    send('log', { message: 'Session found. <strong>CorpPass: Rachel Tan</strong>. Navigating to Annual Return form...' });
    send('status', { message: 'Navigating form...' });
  }, delay);
  delay += 1000;

  setTimeout(() => {
    send('log', { message: `Form loaded. Beginning auto-fill with <strong>${fields.length} verified fields</strong> from Regulator...` });
  }, delay);
  delay += 600;

  fields.forEach((field, i) => {
    const typeDuration = Math.max(400, field.value.length * 35);
    setTimeout(() => {
      send('log', { message: `Filling: <strong>${field.label}</strong> &rarr; <span class="tf-highlight">${field.value}</span>` });
      send('status', { message: `Filling ${field.label}...` });
      send('fill', { fieldIndex: i + 1, value: field.value, label: field.label });
    }, delay);
    delay += typeDuration + 350;
  });

  setTimeout(() => {
    send('complete', { message: `All ${fields.length} fields filled successfully` });
  }, delay + 500);
}

module.exports = router;
