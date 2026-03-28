const express = require('express');
const router = express.Router();
const db = require('../services/db');

// GET /api/pricing — latest prices across all competitors
router.get('/', (req, res) => {
  res.json(db.getLatestPricing());
});

// GET /api/pricing/changes — recent price changes
router.get('/changes', (req, res) => {
  const limit = Math.min(parseInt(req.query.limit) || 50, 200);
  res.json(db.getPriceChanges(limit));
});

// GET /api/pricing/history?product=Name — price history for a product
router.get('/history', (req, res) => {
  const { product } = req.query;
  if (!product) return res.status(400).json({ error: 'product query param required' });
  const limit = Math.min(parseInt(req.query.limit) || 100, 500);
  res.json(db.getPriceHistory(product, limit));
});

// GET /api/pricing/competitors — list active competitors
router.get('/competitors', (req, res) => {
  res.json(db.getActiveCompetitors());
});

module.exports = router;
