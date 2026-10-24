// Vercel Serverless Function: Agent Aria Telegram Webhook (The Bull Print)
// Handles /status /diagnose /health /run /revenue /clicks /analytics + inline callback buttons.
const TG_TOKEN = process.env.TELEGRAM_BOT_TOKEN || '';
const AUTH_CHAT_ID = process.env.TELEGRAM_CHAT_ID || '';
const GH_REPO = process.env.GITHUB_REPO || 'alexkingston1993/MoneyPrinterTurbo';
const GH_TOKEN = process.env.GITHUB_PAT_TOKEN || process.env.GITHUB_TOKEN || '';

async function sendTelegram(chatId, text, replyMarkup) {
  if (!TG_TOKEN) return;
  await fetch(`https://api.telegram.org/bot${TG_TOKEN}/sendMessage`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      chat_id: chatId,
      text,
      parse_mode: 'Markdown',
      reply_markup: replyMarkup,
      disable_web_page_preview: false,
    }),
  });
}

async function answerCallbackQuery(callbackQueryId, text) {
  if (!TG_TOKEN) return;
  await fetch(`https://api.telegram.org/bot${TG_TOKEN}/answerCallbackQuery`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ callback_query_id: callbackQueryId, text: text || 'Command received!' }),
  });
}

async function dispatchGitHubEvent(eventType, clientPayload = {}) {
  if (!GH_TOKEN) return { ok: false, status: 401 };
  return fetch(`https://api.github.com/repos/${GH_REPO}/dispatches`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${GH_TOKEN}`,
      Accept: 'application/vnd.github.v3+json',
      'Content-Type': 'application/json',
      'User-Agent': 'TheBullPrint-Telegram-Webhook',
    },
    body: JSON.stringify({ event_type: eventType, client_payload: clientPayload }),
  });
}

// ---- 💰 Affiliate & Revenue Ledger (Zero-DB GitHub Repo Variables) ----
function blankTelemetry() {
  return { total_clicks: 0, brokers: {}, campaigns: {}, updated_at: '' };
}

async function fetchAffiliateTelemetry() {
  let data = blankTelemetry();
  if (!GH_TOKEN) return data;
  try {
    const res = await fetch(`https://api.github.com/repos/${GH_REPO}/actions/variables/AFFILIATE_TELEMETRY_JSON`, {
      headers: { Authorization: `Bearer ${GH_TOKEN}`, Accept: 'application/vnd.github+json', 'User-Agent': 'TheBullPrint-Aria-Revenue' },
    });
    if (res.ok) data = { ...blankTelemetry(), ...JSON.parse((await res.json()).value) };
  } catch {
    // Silent zero ledger.
  }
  return data;
}

async function fetchPostStats() {
  const stats = { total: 0, last7: 0 };
  try {
    const res = await fetch('https://the-bull-print.vercel.app/content/posts.json', { cache: 'no-store' });
    if (!res.ok) return stats;
    let posts = await res.json();
    if (!Array.isArray(posts)) posts = posts?.posts || [];
    stats.total = posts.length;
    const weekAgo = Date.now() - 7 * 24 * 60 * 60 * 1000;
    for (const p of posts) {
      const date = Date.parse(p?.date || p?.published || p?.created_at || '');
      if (!Number.isNaN(date) && date >= weekAgo) stats.last7 += 1;
    }
  } catch {
    // Silent zero stats.
  }
  return stats;
}

function buildRevenueLedgerCard(t, content) {
  const brokerOrder = [['tradingview', 'TradingView'], ['gocharting', 'GoCharting'], ['zerodha', 'Zerodha'], ['delta', 'Delta'], ['bybit', 'Bybit']];
  const total = Number(t.total_clicks || 0);
  const breakdown = brokerOrder.map(([key, label]) => `${label}: \`${t.brokers?.[key] || 0}\``).join(' | ');
  const estReferrals = total * 0.04; // 4% conversion assumption
  const projectedInr = estReferrals * 500; // blended INR kickback/month
  const updatedAt = (t.updated_at || '—').replace('T', ' ').split('.')[0];
  return (
    `💰 *THE BULL PRINT — AFFILIATE & REVENUE LEDGER* 🐂\n` +
    `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n` +
    `🖱️ *Total Affiliate Clicks:* \`${total}\`\n` +
    `📊 *Breakdown by Broker:* ${breakdown}\n` +
    `🎓 *Published Research Dossiers:* \`${content.total}\` (+${content.last7} this week)\n` +
    `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n` +
    `📈 *Est. Active Referrals* (4% CVR): \`${estReferrals.toFixed(1)}\`\n` +
    `₹ *Projected Monthly Recurring RevShare:* \`₹${projectedInr.toLocaleString('en-IN', { maximumFractionDigits: 0 })}\`\n` +
    `🕒 *Ledger Updated:* \`${updatedAt}\`\n` +
    `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n` +
    `💡 *Verdict:* Every YouTube description fires \`/go/{broker}\` — keep publishing dossiers and the flywheel compounds! ☕🚀`
  );
}

async function handleRevenueCommand(chatId) {
  const [t, content] = await Promise.all([fetchAffiliateTelemetry(), fetchPostStats()]);
  await sendTelegram(chatId, buildRevenueLedgerCard(t, content));
}

function readJsonBody(req) {
  return new Promise((resolve, reject) => {
    let raw = '';
    req.on('data', (chunk) => {
      raw += chunk;
    });
    req.on('end', () => {
      try {
        resolve(raw ? JSON.parse(raw) : {});
      } catch (e) {
        resolve({});
      }
    });
    req.on('error', reject);
  });
}

export default async function handler(req, res) {
  try {
    const body = await readJsonBody(req);

    // 1. INLINE BUTTON CALLBACKS
    if (body.callback_query) {
      const cb = body.callback_query;
      const chatId = cb.message?.chat?.id;
      const data = cb.data || '';

      if (AUTH_CHAT_ID && String(chatId) !== String(AUTH_CHAT_ID)) {
        await answerCallbackQuery(cb.id, 'Unauthorized');
        return res.status(200).json({ ok: true, status: 'unauthorized_ignored' });
      }

      if (data === 'view_revenue') {
        await answerCallbackQuery(cb.id, 'Pulling the Revenue Ledger... 💰');
        await handleRevenueCommand(chatId);
        return res.status(200).json({ ok: true, handler: 'view_revenue' });
      }

      await answerCallbackQuery(cb.id, 'Engaging Agent Aria...');

      if (data.startsWith('rerun_failed:')) {
        const runId = data.split(':')[1];
        const rerunRes = await fetch(`https://api.github.com/repos/${GH_REPO}/actions/runs/${runId}/rerun-failed-jobs`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${GH_TOKEN}`, Accept: 'application/vnd.github.v3+json' },
        });
        if (rerunRes.ok) {
          await sendTelegram(chatId, `🔄 *Agent Aria:* Successfully re-dispatched failed jobs for Workflow Run \`#${runId}\`! Telemetry monitoring active. ☕🚀`);
        } else {
          await sendTelegram(chatId, `⚠️ *Agent Aria:* GitHub Actions re-run notice (HTTP ${rerunRes.status}).`);
        }
      } else if (data.startsWith('run_slot:')) {
        const slot = data.split(':')[1];
        const ghRes = await dispatchGitHubEvent('trigger_media_engine', { topic: slot, mode: 'slot_override' });
        if (ghRes.ok) {
          await sendTelegram(chatId, `🚀 *Agent Aria:* Dispatched market cycle for \`${slot}\` to GitHub Actions cloud runner!`);
        } else {
          await sendTelegram(chatId, `⚠️ *Agent Aria:* Failed to dispatch workflow (HTTP ${ghRes.status}).`);
        }
      }
      return res.status(200).json({ ok: true });
    }

    // 2. SLASH COMMANDS
    const msg = body?.message;
    const text = (msg?.text || '').trim();
    const chatId = msg?.chat?.id;

    if (!chatId || (AUTH_CHAT_ID && String(chatId) !== String(AUTH_CHAT_ID))) {
      return res.status(200).json({ ok: true, status: 'unauthorized_ignored' });
    }

    const lower = text.toLowerCase();

    // /status /diagnose /health
    if (['/status', '/diagnose', '/health', 'status', 'diagnose'].includes(lower)) {
      if (!GH_TOKEN) {
        await sendTelegram(chatId, '⚠️ *Agent Aria:* `GITHUB_PAT_TOKEN` is not configured on Vercel.');
        return res.status(200).json({ ok: true });
      }
      const runsRes = await fetch(`https://api.github.com/repos/${GH_REPO}/actions/runs?per_page=3`, {
        headers: { Authorization: `Bearer ${GH_TOKEN}`, Accept: 'application/vnd.github.v3+json' },
      });
      if (!runsRes.ok) {
        await sendTelegram(chatId, `⚠️ *Agent Aria:* Could not reach GitHub API (HTTP ${runsRes.status}).`);
        return res.status(200).json({ ok: true });
      }
      const runsData = await runsRes.json();
      const latest = runsData.workflow_runs?.[0];
      if (!latest) {
        await sendTelegram(chatId, '🔍 *Agent Aria:* No recent workflow runs found in repository.');
        return res.status(200).json({ ok: true });
      }
      const statusEmoji = latest.conclusion === 'success' ? '✅' : latest.conclusion === 'failure' ? '💥' : '⏳';
      const conclusionText = latest.conclusion || latest.status || 'in_progress';
      const report =
        `🛰️ *AGENT ARIA — LIVE CLOUD TELEMETRY* 🕶️☕\n` +
        `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n` +
        `${statusEmoji} *Latest Workflow:* \`${latest.name}\`\n` +
        `⚡ *Run ID:* \`#${latest.id}\` (\`${conclusionText.toUpperCase()}\`)\n` +
        `📅 *Triggered Via:* \`${latest.event}\` at \`${latest.updated_at.replace('T', ' ').replace('Z', ' UTC')}\`\n` +
        `🌐 *Web Portal:* \`https://the-bull-print.vercel.app\`\n` +
        `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`;
      const inlineKeyboard =
        latest.conclusion === 'failure'
          ? {
              inline_keyboard: [
                [
                  { text: '🔄 Re-Run Failed Jobs', callback_data: `rerun_failed:${latest.id}` },
                  { text: '🩹 Force Clean Rebuild', callback_data: 'run_slot:Institutional Order Flow & Macro Liquidity' },
                ],
                [{ text: '💰 Revenue & Clicks', callback_data: 'view_revenue' }],
              ],
            }
          : {
              inline_keyboard: [
                [
                  { text: '🌅 Pre-Market Brief', callback_data: 'run_slot:Pre-Market Morning Brief & Global Liquidity' },
                  { text: '🔔 Closing Bell', callback_data: 'run_slot:Closing Bell Institutional Absorption' },
                ],
                [
                  { text: '🎓 Weekend Masterclass', callback_data: 'run_slot:Weekend Wealth & Market Structure Masterclass' },
                  { text: '💰 Revenue & Clicks', callback_data: 'view_revenue' },
                ],
              ],
            };
      await sendTelegram(chatId, report, inlineKeyboard);
      return res.status(200).json({ ok: true });
    }

    // /run <topic>
    if (lower.startsWith('/run')) {
      const topic = text.replace(/^\/run/i, '').trim() || 'Institutional Order Flow & Macro Liquidity';
      const ghRes = await dispatchGitHubEvent('trigger_media_engine', { topic });
      await sendTelegram(
        chatId,
        ghRes.ok
          ? `🚀 *Agent Aria:* Cloud media pipeline dispatched to GitHub Actions!\n📌 *Topic:* \`${topic}\`\n\nI will monitor the execution and update your mission card.`
          : `⚠️ *Agent Aria:* Failed to dispatch GitHub Action (HTTP ${ghRes.status}). Verify \`GITHUB_PAT_TOKEN\`.`
      );
      return res.status(200).json({ ok: true, dispatched: ghRes.ok, topic });
    }

    // /revenue /clicks /analytics
    if (['/revenue', '/clicks', '/analytics', 'revenue', 'clicks'].includes(lower)) {
      await handleRevenueCommand(chatId);
      return res.status(200).json({ ok: true, handler: 'revenue_ledger' });
    }

    return res.status(200).json({ ok: true });
  } catch (err) {
    return res.status(500).json({ ok: false, error: err?.message || 'Unknown error' });
  }
}
