const { TinyFish } = require('@tiny-fish/sdk');

// Client auto-reads TINYFISH_API_KEY from env
const client = new TinyFish();

const MAX_RETRIES = 3;
const BASE_DELAY_MS = 1500;

/**
 * Exponential backoff with jitter for rate-limit and transient errors.
 */
function backoffDelay(attempt) {
  const base = BASE_DELAY_MS * Math.pow(2, attempt);
  const jitter = Math.random() * 1000;
  return base + jitter;
}

/**
 * Run a single Tinyfish extraction with streaming, retrying on transient errors.
 *
 * @param {object} opts
 * @param {string} opts.url         - Target URL
 * @param {string} opts.goal        - Natural-language extraction goal
 * @param {string} [opts.profile]   - 'lite' (default) or 'stealth'
 * @param {string} [opts.proxyCountry] - ISO country code for proxy routing
 * @param {function} [opts.onProgress] - Optional callback for PROGRESS events
 * @returns {Promise<object>}       - Structured result from Tinyfish
 */
async function extract({ url, goal, profile = 'lite', proxyCountry, onProgress }) {
  const params = { url, goal, browser_profile: profile };
  if (proxyCountry) {
    params.proxy_config = { country: proxyCountry };
  }

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      const stream = await client.agent.stream(params);
      let result = null;

      for await (const event of stream) {
        if (event.type === 'PROGRESS' && onProgress) {
          onProgress(event);
        } else if (event.type === 'COMPLETE') {
          result = event.result;
        }
      }

      return result;
    } catch (err) {
      const status = err.status || err.statusCode;
      const retryable = status === 429 || status >= 500;

      if (retryable && attempt < MAX_RETRIES) {
        const delay = backoffDelay(attempt);
        console.warn(`Tinyfish request failed (${status}), retrying in ${Math.round(delay)}ms... (attempt ${attempt + 1}/${MAX_RETRIES})`);
        await new Promise(r => setTimeout(r, delay));
        continue;
      }
      throw err;
    }
  }
}

/**
 * Run a single Tinyfish extraction synchronously (no streaming).
 * Simpler for batch jobs where you don't need progress events.
 */
async function extractSync({ url, goal, profile = 'lite', proxyCountry }) {
  const params = {
    url,
    goal,
    browser_profile: profile,
  };
  if (proxyCountry) {
    params.proxy_config = { country: proxyCountry };
  }

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      const result = await client.agent.run(params);
      return result;
    } catch (err) {
      const status = err.status || err.statusCode;
      const retryable = status === 429 || status >= 500;

      if (retryable && attempt < MAX_RETRIES) {
        const delay = backoffDelay(attempt);
        console.warn(`Tinyfish sync request failed (${status}), retrying in ${Math.round(delay)}ms...`);
        await new Promise(r => setTimeout(r, delay));
        continue;
      }
      throw err;
    }
  }
}

/**
 * Extract data from multiple URLs concurrently using batch async.
 * Queues all runs, then polls for completion.
 *
 * @param {Array<{url: string, goal: string, profile?: string}>} tasks
 * @param {number} [concurrency=5] - Max parallel runs
 * @returns {Promise<Array<{url: string, result: object, error?: string}>>}
 */
async function extractBatch(tasks, concurrency = 5) {
  const results = [];

  // Process in chunks to respect concurrency
  for (let i = 0; i < tasks.length; i += concurrency) {
    const chunk = tasks.slice(i, i + concurrency);
    const promises = chunk.map(async (task) => {
      try {
        const result = await extractSync({
          url: task.url,
          goal: task.goal,
          profile: task.profile || 'lite',
          proxyCountry: task.proxyCountry,
        });
        return { url: task.url, result, error: null };
      } catch (err) {
        console.error(`Failed to extract ${task.url}:`, err.message);
        return { url: task.url, result: null, error: err.message };
      }
    });

    const chunkResults = await Promise.all(promises);
    results.push(...chunkResults);

    // Small pause between chunks to avoid rate limits
    if (i + concurrency < tasks.length) {
      await new Promise(r => setTimeout(r, 1500));
    }
  }

  return results;
}

/**
 * Auto-fill a web form via Tinyfish with SSE progress streaming.
 * Used by the BizFile+ autofill route.
 */
async function autofillForm({ url, formData, onProgress }) {
  const fieldInstructions = formData.fields
    .map(f => `- Set "${f.label}" to "${f.value}"`)
    .join('\n');

  const goal = `
Fill in the following form fields exactly as specified:

${fieldInstructions}

After filling all fields, click "Review & Submit".
Do not modify any fields not listed above.
  `.trim();

  return extract({
    url,
    goal,
    profile: 'stealth',
    onProgress: (event) => {
      if (onProgress) onProgress(event);
    },
  });
}

module.exports = {
  extract,
  extractSync,
  extractBatch,
  autofillForm,
};
