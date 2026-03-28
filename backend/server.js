require('dotenv').config();
const express = require('express');
const cors = require('cors');
const path = require('path');

const dashboardRoutes = require('./routes/dashboard');
const clientRoutes = require('./routes/clients');
const uploadRoutes = require('./routes/upload');
const tinyfishRoutes = require('./routes/tinyfish');
const pricingRoutes = require('./routes/pricing');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json());

// Serve frontend static files
app.use(express.static(path.join(__dirname, '..', 'frontend')));

// API routes
app.use('/api/dashboard', dashboardRoutes);
app.use('/api/clients', clientRoutes);
app.use('/api/upload', uploadRoutes);
app.use('/api/tinyfish', tinyfishRoutes);
app.use('/api/pricing', pricingRoutes);

// SPA fallback
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, '..', 'frontend', 'index.html'));
});

app.listen(PORT, () => {
  console.log(`Regulator server running on http://localhost:${PORT}`);
});
