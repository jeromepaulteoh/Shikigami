#!/usr/bin/env node
/**
 * Daily pricing monitor.
 *
 * Scrapes all active competitors, stores results, and reports price changes.
 * Designed to run as a cron job:
 *
 *   # Run daily at 6am
 *   0 6 * * * cd /path/to/regulator && node backend/scripts/monitor.js >> data/monitor.log 2>&1
 *
 * Usage:
 *   npm run monitor              # run once
 *   npm run monitor -- --report  # show latest price changes without scraping
 */
require('dotenv').config();
const { extractBatch } = require('../services/tinyfish');
const db = require('../services/db');

function timestamp() {
  return new Date().toISOString().replace('T', ' ').slice(0, 19);
}

function log(msg) {
  console.log(`[${timestamp()}] ${msg}`);
}

async function monitor() {
  log('=== Daily pricing monitor started ===');

  const competitors = db.getActiveCompetitors();
  if (!competitors.length) {
    log('No active competitors configured. Run: npm run scrape -- --setup');
    return;
  }

  log(`Found ${competitors.length} active competitor(s)`);

  // Scrape each competitor
  const tasks = competitors.map(c => ({
    url: c.url,
    goal: c.goal,
    profile: c.profile,
    proxyCountry: c.proxy_country,
  }));

  const startTime = Date.now();
  const results = await extractBatch(tasks, 3);

  let totalProducts = 0;
  let totalErrors = 0;

  for (let i = 0; i < competitors.length; i++) {
    const competitor = competitors[i];
    const { result, error } = results[i];

    db.insertScrapeResult({
      competitorId: competitor.id,
      rawResult: result ? JSON.stringify(result) : null,
      error: error || null,
      durationMs: Date.now() - startTime,
    });

    if (error) {
      log(`  ✗ ${competitor.name}: ${error}`);
      totalErrors++;
      continue;
    }

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
      totalProducts += products.length;
      log(`  ✓ ${competitor.name}: ${products.length} products`);
    } else {
      log(`  ⚠ ${competitor.name}: no products parsed`);
    }
  }

  const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
  log(`Scraping complete: ${totalProducts} products, ${totalErrors} errors, ${elapsed}s`);

  // Report price changes
  reportChanges();

  log('=== Monitor complete ===\n');
}

function reportChanges() {
  const changes = db.getPriceChanges(20);

  if (!changes.length) {
    log('No price changes detected.');
    return;
  }

  log(`\n--- Price changes detected (${changes.length}) ---`);
  for (const c of changes) {
    const direction = c.price_diff > 0 ? '↑' : '↓';
    const sign = c.price_diff > 0 ? '+' : '';
    log(`  ${direction} ${c.competitor_name} | ${c.product_name}: ${c.prev_price} → ${c.price} (${sign}${c.pct_change}%)`);
  }
  log('---');
}

function showReport() {
  log('=== Latest price changes report ===');
  reportChanges();

  log('\n--- Current pricing snapshot ---');
  const latest = db.getLatestPricing();
  if (!latest.length) {
    log('No pricing data yet. Run monitor first.');
    return;
  }

  let currentProduct = '';
  for (const row of latest) {
    if (row.product_name !== currentProduct) {
      currentProduct = row.product_name;
      log(`\n  ${currentProduct}:`);
    }
    const stock = row.in_stock ? '✓' : '✗ out of stock';
    log(`    ${row.competitor_name}: ${row.currency} ${row.price} (${stock})`);
  }
}

function parsePricingResult(result) {
  if (!result) return [];
  if (Array.isArray(result)) return result;
  for (const key of ['data', 'products', 'items', 'results', 'pricing']) {
    if (Array.isArray(result[key])) return result[key];
  }
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
if (args.includes('--report')) {
  showReport();
} else {
  monitor().catch(err => {
    log(`Fatal error: ${err.message}`);
    console.error(err);
    process.exit(1);
  });
}
