import 'dotenv/config'
import express from 'express'
import cors from 'cors'
import pkg from 'pg'
const { Pool } = pkg
import jwt from 'jsonwebtoken'

const app = express()
app.use(cors({
  origin: ['http://localhost:5173', 'http://localhost:3000', 'http://localhost:8008'],
  credentials: true
}))
app.use(express.json())

// JWT 설정
const SECRET_KEY = process.env.JWT_SECRET ?? 'RANDOM_SECRET_KEY'
const ALGORITHM = 'HS256'
const ISSUER = 'simple-auth-server'

// PostgreSQL 연결 설정 
const pool = new Pool({
  host:     process.env.DB_HOST     ?? 'localhost',
  port:     parseInt(process.env.DB_PORT ?? '5432'),
  user:     process.env.DB_USER     ?? 'postgres',
  password: process.env.DB_PASSWORD ?? '',
  database: 'skala_db',
})

// DB 연결 확인
pool.connect((err, client, release) => {
  if (err) {
    return console.error('[DB] PostgreSQL 연결 실패:', err.stack)
  }
  console.log('[DB] PostgreSQL (skala_db) 연결 성공! 회원가입이 가능합니다.')
  release()
})

// 인증 미들웨어
const authenticateToken = (req, res, next) => {
  const authHeader = req.headers['authorization']
  const token = authHeader && authHeader.split(' ')[1]

  if (!token) return res.status(401).json({ error: '인증 토큰이 필요합니다.' })

  jwt.verify(token, SECRET_KEY, { issuer: ISSUER, algorithms: [ALGORITHM] }, (err, user) => {
    if (err) return res.status(403).json({ error: '유효하지 않은 토큰입니다.' })
    req.user = user
    next()
  })
}

/** ─── 회원가입 API ─── **/
app.post('/api/manager/register', async (req, res) => {
  const { username, password } = req.body
  if (!username || !password) {
    return res.status(400).json({ success: false, error: '아이디와 비밀번호를 입력하세요.' })
  }

  try {
    // 스키마 명시
    await pool.query(
      'INSERT INTO project_db.users (username, password) VALUES ($1, $2)',
      [username, password]
    )
    console.log(`[DB] 새 관리자 등록 성공: ${username}`)
    res.json({ success: true, message: '회원가입 성공!' })
  } catch (err) {
    if (err.code === '23505') {
      res.status(400).json({ success: false, error: '이미 존재하는 아이디입니다.' })
    } else {
      console.error('[DB] 회원가입 오류:', err.message)
      res.status(500).json({ success: false, error: '서버 오류가 발생했습니다.' })
    }
  }
})

/** ─── 로그인 API ─── **/
app.post('/api/manager/login', async (req, res) => {
  const { username, password } = req.body

  try {
    // 스키마 명시
    const result = await pool.query(
      'SELECT * FROM project_db.users WHERE username = $1 AND password = $2',
      [username, password]
    )

    if (result.rows.length > 0) {
      const user = result.rows[0]
      const token = jwt.sign(
        { sub: user.id, username: user.username },
        SECRET_KEY,
        { algorithm: ALGORITHM, issuer: ISSUER, expiresIn: '1h' }
      )
      res.json({ success: true, token })
    } else {
      res.status(401).json({ success: false, error: '아이디 또는 비밀번호가 틀립니다.' })
    }
  } catch (err) {
    console.error('[DB] 로그인 오류:', err.message)
    res.status(500).json({ success: false, error: '로그인 중 오류 발생' })
  }
})

/** ─── 이미지 로그 조회 ─── **/
app.get('/api/manager/images', authenticateToken, async (req, res) => {
  const testing = req.query.testing === 'true'
  if (testing) return res.json({ images: [], mode: 'testing' })

  try {
    // 스키마 명시
    const result = await pool.query('SELECT * FROM project_db.image_logs WHERE confidence_score < 0.5 AND updated = false')
    res.json({ images: result.rows, mode: 'live' })
  } catch (err) {
    console.error('[DB] 이미지 조회 오류:', err.message)
    res.status(500).json({ error: 'DB 조회 실패' })
  }
})

app.listen(3001, () => {
  console.log('[DB server] 3001번 포트에서 PostgreSQL 모드로 실행 중')
})
