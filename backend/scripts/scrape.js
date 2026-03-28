#!/usr/bin/env node
/**
 * One-off competitor scraper.
 *
 * Usage:
 *   npm run scrape                           # scrape all active competitors
 *   node backend/scripts/scrape.js --setup   # seed competitor list
 */
require('dotenv').config();
const { extractBatch } = require('../services/tinyfish');
const db = require('../services/db');

// ─── Configure your competitors here ────────────────────────────────
const COMPETITORS = [
  {
    name: 'Example Store A',
    url: 'https://example-store-a.com/products',
    goal: `Extract all products with their names, prices (numeric), currency, and whether they are in stock (true/false). Return as JSON array: [{"name": "...", "price": 29.99, "currency": "USD", "in_stock": true}]`,
    profile: 'lite',
    proxyCountry: null,
  },
  {
    name: 'Example Store B',
    url: 'https://example-store-b.com/pricing',
    goal: `Extract all pricing tiers or products with names, prices (numeric), currency, and availability. Return as JSON array: [{"name": "...", "price": 49.00, "currency": "USD", "in_stock": true}]`,
    profile: 'lite',
    proxyCountry: null,
  },
  // Add more competitors as needed
];

async function setup() {
  console.log('Seeding competitors...');
  for (const c of COMPETITORS) {
    db.addCompetitor(c);
    console.log(`  + ${c.name} → ${c.url}`);
  }
  console.log(`Done. ${COMPETITORS.length} competitors configured.`);
}

async function scrapeAll() {
  const competitors = db.getActiveCompetitors();
  if (!competitors.length) {
    console.log('No active competitors. Run with --setup first.');
    process.exit(1);
  }

  console.log(`Scraping ${competitors.length} competitor(s)...\n`);

  // Build task list for batch extraction
  const tasks = competitors.map(c => ({
    url: c.url,
    goal: c.goal,
    profile: c.profile,
    proxyCountry: c.proxy_country,
  }));

  const startTime = Date.now();
  const results = await extractBatch(tasks, 3);

  // Process and store results
  for (let i = 0; i < competitors.length; i++) {
    const competitor = competitors[i];
    const { result, error } = results[i];
    const durationMs = Date.now() - startTime;

    console.log(`[${competitor.name}]`);

    // Store raw scrape result
    db.insertScrapeResult({
      competitorId: competitor.id,
      rawResult: result ? JSON.stringify(result) : null,
      error: error || null,
      durationMs,
    });

    if (error) {
      console.log(`  ✗ Error: ${error}\n`);
      continue;
    }

    // Parse pricing data from result
    const products = parsePricingResult(result);
    if (products.length) {
      const rows = products.map(p => ({
        competitorId: competitor.id,
        productName: p.name,
        price: p.price,
        currency: p.currency || 'USD',
        inStock: p.in_stock ? 1 : 0,
      }));
      db.insertPricingBatch(rows);
      console.log(`  ✓ ${products.length} products stored`);
    } else {
      console.log('  ⚠ No products parsed from result');
    }
    console.log();
  }

  console.log(`\nCompleted in ${((Date.now() - startTime) / 1000).toFixed(1)}s`);
}

/**
 * Parse the Tinyfish result into a normalized pricing array.
 * Handles both direct arrays and wrapped results.
 */
function parsePricingResult(result) {
  if (!result) return [];

  // If result is already an array
  if (Array.isArray(result)) return result;

  // If result has a data/products/items key
  for (const key of ['data', 'products', 'items', 'results', 'pricing']) {
    if (Array.isArray(result[key])) return result[key];
  }

  // If it's a string, try parsing as JSON
  if (typeof result === 'string') {
    try {
      const parsed = JSON.parse(result);
      return Array.isArray(parsed) ? parsed : [];
    } catch { return []; }
  }

  return [];
}

// Entry point
const args = process.argv.slice(2);
if (args.includes('--setup')) {
  setup();
} else {
  scrapeAll().catch(err => {
    console.error('Fatal error:', err);
    process.exit(1);
  });
}
