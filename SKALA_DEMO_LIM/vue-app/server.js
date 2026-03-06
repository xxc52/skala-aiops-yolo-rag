import 'dotenv/config'
import express from 'express'
import cors from 'cors'
import mysql from 'mysql2/promise'

const app = express()
app.use(cors())
app.use(express.json())

const pool = mysql.createPool({
  host:     process.env.DB_HOST     ?? 'localhost',
  port:     parseInt(process.env.DB_PORT ?? '3306'),
  user:     process.env.DB_USER     ?? 'root',
  password: process.env.DB_PASSWORD ?? '',
  database: process.env.DB_NAME     ?? 'your_database',
  waitForConnections: true,
  connectionLimit: 10,
  queueLimit: 0,
})

const FAKE_IMAGES = [
  { uuid: '550e8400-e29b-41d4-a716-446655440001', imageUrl: '/sample_img1.jpg', confidenceScore: 0.12, category: null, updated: false },
  { uuid: '550e8400-e29b-41d4-a716-446655440002', imageUrl: '/sample_img2.jpg', confidenceScore: 0.38, category: null, updated: false },
  { uuid: '550e8400-e29b-41d4-a716-446655440003', imageUrl: '/sample_img3.jpg', confidenceScore: 0.47, category: null, updated: false },
  { uuid: '550e8400-e29b-41d4-a716-446655440004', imageUrl: '/sample_img1.jpg', confidenceScore: 0.29, category: null, updated: false },
  { uuid: '550e8400-e29b-41d4-a716-446655440005', imageUrl: '/sample_img2.jpg', confidenceScore: 0.05, category: null, updated: false },
]

app.get('/api/manager/images', async (req, res) => {
  const testing = req.query.testing === 'true'

  if (testing) {
    return res.json({ images: FAKE_IMAGES, mode: 'testing' })
  }

  try {
    const [rows] = await pool.query(
      `SELECT uuid, image_url, confidence_score, category, updated, updated_at, created_at
       FROM records
       WHERE confidence_score < 0.5
         AND updated = false
       ORDER BY confidence_score ASC`
    )
    const images = rows.map(row => ({
      uuid:            row.uuid,
      imageUrl:        row.image_url,
      confidenceScore: row.confidence_score,
      category:        row.category ?? null,
      updated:         Boolean(row.updated),
      updatedAt:       row.updated_at ?? null,
      createdAt:       row.created_at,
    }))
    res.json({ images, mode: 'live' })
  } catch (err) {
    console.error('[DB] Failed to fetch records:', err)
    res.status(500).json({ error: 'Failed to fetch records from database.' })
  }
})

app.post('/api/manager/update', async (req, res) => {
  const updates = req.body?.updates ?? []
  const testing = req.body?.testing === true

  if (!updates.length) {
    return res.status(400).json({ error: 'No updates provided' })
  }

  for (const item of updates) {
    if (!item.uuid || !item.category) {
      return res.status(400).json({ error: 'Invalid update item' })
    }
  }

  if (testing) {
    console.log('[Testing] Would have updated:', updates)
    return res.json({ success: true, updatedCount: updates.length, mode: 'testing' })
  }

  try {
    let updatedCount = 0
    for (const item of updates) {
      const [result] = await pool.query(
        `UPDATE records
         SET category   = ?,
             updated    = true,
             updated_at = NOW()
         WHERE uuid = ?`,
        [item.category, item.uuid]
      )
      updatedCount += result.affectedRows ?? 0
    }
    res.json({ success: true, updatedCount, mode: 'live' })
  } catch (err) {
    console.error('[DB] Failed to update records:', err)
    res.status(500).json({ error: 'Failed to update records in database.' })
  }
})

app.listen(3001, () => {
  console.log('[DB server] running on http://localhost:3001')
})
