const Database = require('better-sqlite3');
const path = require('path');
const fs = require('fs');

const DATA_DIR = path.join(__dirname, '..', '..', 'data');
if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });

const db = new Database(path.join(DATA_DIR, 'regulator.db'));

// Enable WAL mode for better concurrent read performance
db.pragma('journal_mode = WAL');

// Create tables
db.exec(`
  CREATE TABLE IF NOT EXISTS competitors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    url TEXT NOT NULL,
    goal TEXT NOT NULL,
    profile TEXT DEFAULT 'lite',
    proxy_country TEXT,
    active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
  );

  CREATE TABLE IF NOT EXISTS scrape_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    competitor_id INTEGER NOT NULL REFERENCES competitors(id),
    scraped_at TEXT DEFAULT (datetime('now')),
    raw_result TEXT,
    error TEXT,
    duration_ms INTEGER
  );

  CREATE TABLE IF NOT EXISTS pricing (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    competitor_id INTEGER NOT NULL REFERENCES competitors(id),
    product_name TEXT NOT NULL,
    price REAL,
    currency TEXT DEFAULT 'USD',
    in_stock INTEGER,
    scraped_at TEXT DEFAULT (datetime('now'))
  );

  CREATE INDEX IF NOT EXISTS idx_pricing_competitor_date
    ON pricing(competitor_id, scraped_at);

  CREATE INDEX IF NOT EXISTS idx_pricing_product
    ON pricing(product_name, scraped_at);

  CREATE INDEX IF NOT EXISTS idx_scrape_results_competitor
    ON scrape_results(competitor_id, scraped_at);
`);

// Prepared statements
const stmts = {
  insertCompetitor: db.prepare(`
    INSERT OR IGNORE INTO competitors (name, url, goal, profile, proxy_country)
    VALUES (@name, @url, @goal, @profile, @proxyCountry)
  `),

  getActiveCompetitors: db.prepare(`
    SELECT * FROM competitors WHERE active = 1
  `),

  getCompetitor: db.prepare(`
    SELECT * FROM competitors WHERE id = ?
  `),

  insertScrapeResult: db.prepare(`
    INSERT INTO scrape_results (competitor_id, raw_result, error, duration_ms)
    VALUES (@competitorId, @rawResult, @error, @durationMs)
  `),

  insertPricing: db.prepare(`
    INSERT INTO pricing (competitor_id, product_name, price, currency, in_stock)
    VALUES (@competitorId, @productName, @price, @currency, @inStock)
  `),

  getLatestPricing: db.prepare(`
    SELECT p.*, c.name AS competitor_name
    FROM pricing p
    JOIN competitors c ON c.id = p.competitor_id
    WHERE p.scraped_at = (
      SELECT MAX(p2.scraped_at) FROM pricing p2
      WHERE p2.competitor_id = p.competitor_id AND p2.product_name = p.product_name
    )
    ORDER BY p.product_name, c.name
  `),

  getPriceHistory: db.prepare(`
    SELECT p.*, c.name AS competitor_name
    FROM pricing p
    JOIN competitors c ON c.id = p.competitor_id
    WHERE p.product_name = @productName
    ORDER BY p.scraped_at DESC
    LIMIT @limit
  `),

  getPriceChanges: db.prepare(`
    WITH ranked AS (
      SELECT p.*, c.name AS competitor_name,
        LAG(p.price) OVER (PARTITION BY p.competitor_id, p.product_name ORDER BY p.scraped_at) AS prev_price,
        LAG(p.scraped_at) OVER (PARTITION BY p.competitor_id, p.product_name ORDER BY p.scraped_at) AS prev_date
      FROM pricing p
      JOIN competitors c ON c.id = p.competitor_id
    )
    SELECT *, (price - prev_price) AS price_diff,
      CASE WHEN prev_price > 0 THEN ROUND((price - prev_price) / prev_price * 100, 2) ELSE NULL END AS pct_change
    FROM ranked
    WHERE prev_price IS NOT NULL AND price != prev_price
    ORDER BY scraped_at DESC
    LIMIT ?
  `),
};

// Batch insert for pricing rows (wrapped in a transaction)
const insertPricingBatch = db.transaction((rows) => {
  for (const row of rows) {
    stmts.insertPricing.run(row);
  }
});

module.exports = {
  db,
  addCompetitor: (data) => stmts.insertCompetitor.run(data),
  getActiveCompetitors: () => stmts.getActiveCompetitors.all(),
  getCompetitor: (id) => stmts.getCompetitor.get(id),
  insertScrapeResult: (data) => stmts.insertScrapeResult.run(data),
  insertPricing: (data) => stmts.insertPricing.run(data),
  insertPricingBatch,
  getLatestPricing: () => stmts.getLatestPricing.all(),
  getPriceHistory: (productName, limit = 100) => stmts.getPriceHistory.all({ productName, limit }),
  getPriceChanges: (limit = 50) => stmts.getPriceChanges.all(limit),
};
