// Vercel Serverless Function: Mission Control Action Dispatcher
// Executes operator commands: DISPATCH_SLOT, DISPATCH_ALL_6, CANCEL_RUN,
// APPROVE_THUMBS, REGENERATE_THUMBS, UPDATE_SCRIPT_PAYLOAD, HALT_RUN.

const { verifyToken, parseCookies } = require('./auth');

const GH_REPO = process.env.GITHUB_REPO || 'alexkingston1993/MoneyPrinterTurbo';
const GH_TOKEN = process.env.GITHUB_PAT_TOKEN || process.env.GITHUB_TOKEN || '';
const BRANCH = 'telemetry-live';

async function dispatchWorkflow(inputs = {}) {
  const url = `https://api.github.com/repos/${GH_REPO}/actions/workflows/market_publisher.yml/dispatches`;
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${GH_TOKEN}`,
      Accept: 'application/vnd.github.v3+json',
      'Content-Type': 'application/json',
      'User-Agent': 'TheBullPrint-MissionControl',
    },
    body: JSON.stringify({
      ref: 'main',
      inputs: {
        vertical: inputs.vertical || '',
        shorts_count: String(inputs.shorts_count || ''),
        slot: String(inputs.slot || ''),
        topic: inputs.topic || '',
      },
    }),
  });
  return res.ok;
}

async function cancelRun(runId) {
  const url = `https://api.github.com/repos/${GH_REPO}/actions/runs/${runId}/cancel`;
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${GH_TOKEN}`,
      Accept: 'application/vnd.github.v3+json',
      'User-Agent': 'TheBullPrint-MissionControl',
    },
  });
  return res.ok;
}

async function writeControlCommand(slot, cmdObj) {
  const path = `control/slot_${slot}_cmd.json`;
  const getUrl = `https://api.github.com/repos/${GH_REPO}/contents/${path}?ref=${BRANCH}`;
  let sha = null;
  try {
    const getRes = await fetch(getUrl, {
      headers: {
        Authorization: `Bearer ${GH_TOKEN}`,
        Accept: 'application/vnd.github.v3+json',
        'User-Agent': 'TheBullPrint-MissionControl',
      },
      cache: 'no-store',
    });
    if (getRes.ok) {
      const d = await getRes.json();
      sha = d.sha;
    }
  } catch {}

  const putUrl = `https://api.github.com/repos/${GH_REPO}/contents/${path}`;
  const rawBytes = Buffer.from(JSON.stringify(cmdObj, null, 2)).toString('base64');
  const putPayload = {
    message: `operator cmd: ${cmdObj.action} on slot ${slot}`,
    content: rawBytes,
    branch: BRANCH,
  };
  if (sha) putPayload.sha = sha;

  const putRes = await fetch(putUrl, {
    method: 'PUT',
    headers: {
      Authorization: `Bearer ${GH_TOKEN}`,
      Accept: 'application/vnd.github.v3+json',
      'Content-Type': 'application/json',
      'User-Agent': 'TheBullPrint-MissionControl',
    },
    body: JSON.stringify(putPayload),
  });
  return putRes.ok;
}

module.exports = async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Credentials', 'true');
  res.setHeader('Access-Control-Allow-Origin', req.headers.origin || '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST,OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type,Authorization');

  if (req.method === 'OPTIONS') return res.status(200).end();
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' });

  // Auth gate
  const cookies = parseCookies(req);
  const isAuth = verifyToken(cookies.bp_mc_session);
  if (!isAuth && req.headers['x-admin-key'] !== process.env.ADMIN_DASHBOARD_PASS) {
    return res.status(401).json({ error: 'Unauthorized operator action.' });
  }

  let body = req.body;
  if (typeof body === 'string') {
    try {
      body = JSON.parse(body);
    } catch {
      body = {};
    }
  }

  const { action, slot, vertical, shorts_count, custom_headline, run_id, updated_payload, topic, custom_topic } = body || {};

  try {
    switch (action) {
      case 'DISPATCH_SLOT': {
        const targetTopic = custom_topic || topic || '';
        const ok = await dispatchWorkflow({ slot, vertical, shorts_count, topic: targetTopic });
        return res.status(200).json({ ok, message: `Dispatched Slot #${slot} (${vertical})${targetTopic ? ` with topic: "${targetTopic.substring(0, 40)}..."` : ''}` });
      }

      case 'RUN_VIRAL_AUDIT': {
        const ok = await dispatchWorkflow({ slot: 1, vertical: 'stock_market', shorts_count: 1, topic: 'RUN_VIRAL_AUDIT' });
        return res.status(200).json({ ok, message: 'Viral Channel Audit & Outlier Radar refresh triggered!' });
      }

      case 'DISPATCH_ALL_6': {
        const slotsConfig = [
          { slot: 1, vertical: 'stock_market', shorts_count: 2 },
          { slot: 2, vertical: 'crypto', shorts_count: 2 },
          { slot: 3, vertical: 'insurance', shorts_count: 2 },
          { slot: 4, vertical: 'stock_market', shorts_count: 2 },
          { slot: 5, vertical: 'crypto', shorts_count: 1 },
          { slot: 6, vertical: 'insurance', shorts_count: 1 },
        ];
        for (const s of slotsConfig) {
          await dispatchWorkflow(s);
          await new Promise((r) => setTimeout(r, 600));
        }
        return res.status(200).json({ ok: true, message: 'All 6 market slots dispatched to GitHub Actions!' });
      }

      case 'CANCEL_RUN': {
        if (!run_id) return res.status(400).json({ error: 'run_id required for cancellation' });
        const ok = await cancelRun(run_id);
        if (slot) {
          await writeControlCommand(slot, { action: 'HALT_RUN', timestamp: Date.now() });
        }
        return res.status(200).json({ ok, message: `Run ${run_id} cancel signal sent.` });
      }

      case 'APPROVE_THUMBS': {
        if (!slot) return res.status(400).json({ error: 'slot number required' });
        const ok = await writeControlCommand(slot, { action: 'APPROVE_THUMBS', timestamp: Date.now() });
        return res.status(200).json({ ok, message: `Thumbnail approved for Slot #${slot}. Proceeding to GPU.` });
      }

      case 'REGENERATE_THUMBS': {
        if (!slot) return res.status(400).json({ error: 'slot number required' });
        const ok = await writeControlCommand(slot, {
          action: 'REGENERATE_THUMBS',
          custom_headline: custom_headline || '',
          timestamp: Date.now(),
        });
        return res.status(200).json({ ok, message: `Regeneration signal queued with headline: "${custom_headline}"` });
      }

      case 'UPDATE_SCRIPT_PAYLOAD': {
        if (!slot) return res.status(400).json({ error: 'slot number required' });
        const ok = await writeControlCommand(slot, {
          action: 'UPDATE_PAYLOAD',
          updated_payload: updated_payload || {},
          timestamp: Date.now(),
        });
        return res.status(200).json({ ok, message: `Payload update queued for Slot #${slot}` });
      }

      case 'HALT_RUN': {
        if (!slot) return res.status(400).json({ error: 'slot number required' });
        const ok = await writeControlCommand(slot, { action: 'HALT_RUN', timestamp: Date.now() });
        return res.status(200).json({ ok, message: `Emergency halt signal written for Slot #${slot}` });
      }

      default:
        return res.status(400).json({ error: `Unknown action: ${action}` });
    }
  } catch (err) {
    console.error('Action execution error:', err);
    return res.status(500).json({ error: 'Action execution failed: ' + err.message });
  }
};
