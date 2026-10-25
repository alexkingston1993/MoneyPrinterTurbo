// Vercel Serverless Function: Mission Control Auth Gate
// Validates operator credentials and issues an HttpOnly 30-day signed session cookie.

const crypto = require('crypto');

const ADMIN_USER = process.env.ADMIN_DASHBOARD_USER || 'bullprint_admin';
const ADMIN_PASS = process.env.ADMIN_DASHBOARD_PASS || 'bullprintadmin@123#';
const SECRET_KEY = process.env.SESSION_SECRET || 'the-bull-print-institutional-secret-key-2026';

function signToken(username) {
  const payload = JSON.stringify({
    u: username,
    exp: Date.now() + 30 * 24 * 60 * 60 * 1000, // 30 days
  });
  const b64 = Buffer.from(payload).toString('base64url');
  const sig = crypto.createHmac('sha256', SECRET_KEY).update(b64).digest('base64url');
  return `${b64}.${sig}`;
}

function verifyToken(token) {
  if (!token || !token.includes('.')) return false;
  const [b64, sig] = token.split('.');
  const expectedSig = crypto.createHmac('sha256', SECRET_KEY).update(b64).digest('base64url');
  if (sig !== expectedSig) return false;
  try {
    const data = JSON.parse(Buffer.from(b64, 'base64url').toString('utf8'));
    if (Date.now() > data.exp) return false;
    return data.u === ADMIN_USER;
  } catch {
    return false;
  }
}

function parseCookies(req) {
  const list = {};
  const rc = req.headers.cookie;
  if (rc) {
    rc.split(';').forEach((cookie) => {
      const parts = cookie.split('=');
      list[parts.shift().trim()] = decodeURI(parts.join('='));
    });
  }
  return list;
}

module.exports = async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Credentials', 'true');
  res.setHeader('Access-Control-Allow-Origin', req.headers.origin || '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET,POST,DELETE,OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type,Authorization');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  // GET: Check active session status
  if (req.method === 'GET') {
    const cookies = parseCookies(req);
    const token = cookies.bp_mc_session;
    const isValid = verifyToken(token);
    return res.status(200).json({
      authenticated: isValid,
      user: isValid ? ADMIN_USER : null,
    });
  }

  // DELETE: Logout
  if (req.method === 'DELETE') {
    res.setHeader(
      'Set-Cookie',
      'bp_mc_session=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0'
    );
    return res.status(200).json({ ok: true, message: 'Logged out successfully' });
  }

  // POST: Login
  if (req.method === 'POST') {
    let body = req.body;
    if (typeof body === 'string') {
      try {
        body = JSON.parse(body);
      } catch {
        body = {};
      }
    }
    const { username, password } = body || {};

    if (username === ADMIN_USER && password === ADMIN_PASS) {
      const sessionToken = signToken(username);
      // 30 days cookie
      res.setHeader(
        'Set-Cookie',
        `bp_mc_session=${sessionToken}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${30 * 24 * 3600}`
      );
      return res.status(200).json({
        ok: true,
        user: ADMIN_USER,
        message: 'Authorization successful',
      });
    }

    return res.status(401).json({
      ok: false,
      error: 'Invalid operator credentials. Access denied.',
    });
  }

  return res.status(405).json({ error: 'Method not allowed' });
};

module.exports.verifyToken = verifyToken;
module.exports.parseCookies = parseCookies;
