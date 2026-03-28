const express = require('express');
const multer = require('multer');
const path = require('path');
const fs = require('fs');

const router = express.Router();

// Ensure uploads directory exists
const uploadsDir = path.join(__dirname, '..', '..', 'uploads');
if (!fs.existsSync(uploadsDir)) fs.mkdirSync(uploadsDir, { recursive: true });

const storage = multer.diskStorage({
  destination: uploadsDir,
  filename: (req, file, cb) => {
    const unique = Date.now() + '-' + Math.round(Math.random() * 1e6);
    cb(null, unique + '-' + file.originalname);
  },
});
const upload = multer({ storage });

// POST /api/upload
router.post('/', upload.single('file'), async (req, res) => {
  if (!req.file) return res.status(400).json({ error: 'No file provided' });

  const ext = path.extname(req.file.originalname).toLowerCase();

  // TODO: Integrate real document extraction (OCR, PDF parsing, etc.)
  // For now, return mock extracted fields based on file type
  let extractedFields = [];
  if (ext === '.pdf') {
    extractedFields = ['UEN', 'directors', 'address'];
  } else if (ext === '.xlsx' || ext === '.xls') {
    extractedFields = ['Revenue', 'assets', 'solvency'];
  } else if (['.jpg', '.jpeg', '.png'].includes(ext)) {
    extractedFields = ['Name', 'passport', 'expiry'];
  }

  res.json({
    filename: req.file.originalname,
    size: req.file.size,
    path: req.file.path,
    extractedFields,
  });
});

module.exports = router;
