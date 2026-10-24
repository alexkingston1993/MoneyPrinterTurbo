import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

const TG_TOKEN = process.env.TELEGRAM_BOT_TOKEN || '';
const AUTH_CHAT_ID = process.env.TELEGRAM_CHAT_ID || '';
const GH_REPO = process.env.GITHUB_REPO || 'alexkingston1993/MoneyPrinterTurbo';
const GH_TOKEN = process.env.GITHUB_PAT_TOKEN || process.env.GITHUB_TOKEN || '';

async function sendTelegram(chatId: number | string, text: string, replyMarkup?: object) {
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

async function answerCallbackQuery(callbackQueryId: string, text?: string) {
  if (!TG_TOKEN) return;
  await fetch(`https://api.telegram.org/bot${TG_TOKEN}/answerCallbackQuery`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      callback_query_id: callbackQueryId,
      text: text || 'Command received!',
    }),
  });
}

async function dispatchGitHubEvent(eventType: string, clientPayload: object = {}) {
  if (!GH_TOKEN) {
    return { ok: false, status: 401, text: () => Promise.resolve('Missing GITHUB_TOKEN') };
  }
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

// =====================================================================
// 💰 AFFILIATE & REVENUE LEDGER HELPERS (Zero-DB GitHub Repo Variables)
// =====================================================================
interface TelemetryShape {
  total_clicks: number;
  brokers: Record<string, number>;
  campaigns: Record<string, number>;
  updated_at: string;
}

function blankTelemetry(): TelemetryShape {
  return { total_clicks: 0, brokers: {}, campaigns: {}, updated_at: '' };
}

async function fetchAffiliateTelemetry(): Promise<TelemetryShape> {
  let data = blankTelemetry();
  if (!GH_TOKEN) return data;
  try {
    const res = await fetch(`https://api.github.com/repos/${GH_REPO}/actions/variables/AFFILIATE_TELEMETRY_JSON`, {
      headers: { Authorization: `Bearer ${GH_TOKEN}`, Accept: 'application/vnd.github+json', 'User-Agent': 'TheBullPrint-Telegram-Webhook' },
    });
    if (res.status === 404) return data; // Ledger not created yet
    if (res.ok) {
      const raw = (await res.json()).value;
      data = { ...blankTelemetry(), ...JSON.parse(raw) };
    }
  } catch {
    // Silent zero ledger on any network failure.
  }
  return data;
}

async function fetchPostStats(): Promise<{ total: number; last7: number }> {
  const stats = { total: 0, last7: 0 };
  try {
    const res = await fetch('https://the-bull-print.vercel.app/content/posts.json', { cache: 'no-store' });
    if (!res.ok) return stats;
    let posts: any = await res.json();
    if (!Array.isArray(posts)) posts = posts?.posts || [];
    stats.total = posts.length;
    const weekAgo = Date.now() - 7 * 24 * 60 * 60 * 1000;
    for (const p of posts) {
      const date = Date.parse(p?.date || p?.published || p?.created_at || '');
      if (!Number.isNaN(date) && date >= weekAgo) stats.last7 += 1;
    }
  } catch {
    // Silent zero stats on any fetch failure.
  }
  return stats;
}

function buildRevenueLedgerCard(t: TelemetryShape, content: { total: number; last7: number }): string {
  const brokerOrder: Array<[string, string]> = [
    ['tradingview', 'TradingView'],
    ['gocharting', 'GoCharting'],
    ['zerodha', 'Zerodha'],
    ['delta', 'Delta'],
    ['bybit', 'Bybit'],
  ];
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

async function handleRevenueCommand(chatId: number | string) {
  const [t, content] = await Promise.all([fetchAffiliateTelemetry(), fetchPostStats()]);
  await sendTelegram(chatId, buildRevenueLedgerCard(t, content));
}

function buildYtQuotaCard(): string {
  // The only slot Vercel reliably holds is YT_OAUTH_POOL_JSON (provisioned via
  // scripts/provision_yt_pool_cli.py). Everything else is cloud-managed.
  let slots: any[] = [];
  let poolSources: string[] = [];
  try {
    const raw = process.env.YT_OAUTH_POOL_JSON || '';
    if (raw) {
      const parsed = JSON.parse(raw);
      slots = Array.isArray(parsed) ? parsed : [parsed];
      poolSources = slots.map(
        (s: any) => `▫️ \`pool.json (ends …${String(s.client_id || '').slice(-14)})\``
      );
    }
  } catch {
    /* malformed pool json — report empty */
  }
  for (let i = 1; i <= 6; i++) {
    if (process.env[`YT_CLIENT_ID_${i}`] && process.env[`YT_REFRESH_TOKEN_${i}`]) {
      const cid = process.env[`YT_CLIENT_ID_${i}`]!;
      poolSources.push(`▫️ \`env YT_CLIENT_ID_${i} (ends …${cid.slice(-14)})\``);
    }
  }

  const n = poolSources.length;
  const capacity = n * 6; // 10,000 units/day ÷ 1,600 units per upload ≈ 6 videos/day/slot
  const lines = [
    '🔑 *AGENT ARIA: YT QUOTA ROTATOR STATUS* ⛽⚡',
    '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━',
    `🧩 *Active OAuth Slots:* \`${n}\` project slot(s)`,
    ...poolSources,
    '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━',
    `📊 *Daily Upload Capacity:* \`≈ ${capacity} videos/day\` (${n} × 6)`,
    'ℹ️ *Math:* 10,000 quota units/day/project ÷ 1,600 units per upload',
  ];
  if (n === 0) {
    lines.push('⚠️ *No pool detected on Vercel* (run scripts/provision_yt_pool_cli.py --sync)');
  } else {
    lines.push('🚀 *Rotation:* quotaExceeded on Slot #N auto-fails over to Slot #N+1 mid-upload');
  }
  lines.push('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  lines.push('🛡️ *Verdict:* the pipeline is duplicate-proof & quota-rotated 🐂');
  return lines.join('\n');
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();

    // 1. HANDLE INLINE BUTTON CALLBACKS (One-Tap Self-Healing, Rerun, Slot Dispatch)
    if (body.callback_query) {
      const cb = body.callback_query;
      const chatId = cb.message?.chat?.id;
      const data: string = cb.data || '';

      if (AUTH_CHAT_ID && String(chatId) !== String(AUTH_CHAT_ID)) {
        await answerCallbackQuery(cb.id, 'Unauthorized');
        return NextResponse.json({ ok: true, status: 'unauthorized_ignored' });
      }

      if (data === 'view_revenue') {
        await answerCallbackQuery(cb.id, 'Pulling the Revenue Ledger... 💰');
        await handleRevenueCommand(chatId);
        return NextResponse.json({ ok: true, handler: 'view_revenue' });
      }

      if (data === 'view_yt_quota') {
        await answerCallbackQuery(cb.id, 'Auditing YouTube Quota Slots... 🔑');
        await sendTelegram(chatId, buildYtQuotaCard());
        return NextResponse.json({ ok: true, handler: 'view_yt_quota' });
      }

      await answerCallbackQuery(cb.id, 'Engaging Agent Aria...');

      if (data.startsWith('rerun_failed:')) {
        const runId = data.split(':')[1];
        const rerunRes = await fetch(`https://api.github.com/repos/${GH_REPO}/actions/runs/${runId}/rerun-failed-jobs`, {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${GH_TOKEN}`,
            Accept: 'application/vnd.github.v3+json',
          },
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

      return NextResponse.json({ ok: true });
    }

    // 2. HANDLE SLASH COMMANDS SERVERLESSLY ON VERCEL
    const msg = body?.message;
    const text: string = (msg?.text || '').trim();
    const chatId = msg?.chat?.id;

    if (!chatId || (AUTH_CHAT_ID && String(chatId) !== String(AUTH_CHAT_ID))) {
      return NextResponse.json({ ok: true, status: 'unauthorized_ignored' });
    }

    const lower = text.toLowerCase();

    // Command: /status, /diagnose, or /health
    if (['/status', '/diagnose', '/health', 'status', 'diagnose'].includes(lower)) {
      if (!GH_TOKEN) {
        await sendTelegram(chatId, '⚠️ *Agent Aria:* `GITHUB_PAT_TOKEN` is not configured on Vercel.');
        return NextResponse.json({ ok: true });
      }

      const runsRes = await fetch(`https://api.github.com/repos/${GH_REPO}/actions/runs?per_page=3`, {
        headers: {
          Authorization: `Bearer ${GH_TOKEN}`,
          Accept: 'application/vnd.github.v3+json',
        },
      });

      if (!runsRes.ok) {
        await sendTelegram(chatId, `⚠️ *Agent Aria:* Could not reach GitHub API (HTTP ${runsRes.status}).`);
        return NextResponse.json({ ok: true });
      }

      const runsData = await runsRes.json();
      const latest = runsData.workflow_runs?.[0];

      if (!latest) {
        await sendTelegram(chatId, '🔍 *Agent Aria:* No recent workflow runs found in repository.');
        return NextResponse.json({ ok: true });
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
                [{ text: '🔄 Re-Run Failed Jobs', callback_data: `rerun_failed:${latest.id}` },
                  { text: '🩹 Force Clean Rebuild', callback_data: 'run_slot:Institutional Order Flow & Macro Liquidity' },
                ],
                [{ text: '💰 Revenue & Clicks', callback_data: 'view_revenue' },
                  { text: '🔑 YT Quota', callback_data: 'view_yt_quota' }],
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
                [{ text: '🔑 YT Quota Slot Capacity', callback_data: 'view_yt_quota' }],
              ],
            };

      await sendTelegram(chatId, report, inlineKeyboard);
      return NextResponse.json({ ok: true });
    }

    // Command: /run <topic>
    if (lower.startsWith('/run')) {
      const topic = text.replace(/^\/run/i, '').trim() || 'Institutional Order Flow & Macro Liquidity';
      const ghRes = await dispatchGitHubEvent('trigger_media_engine', { topic });
      await sendTelegram(
        chatId,
        ghRes.ok
          ? `🚀 *Agent Aria:* Cloud media pipeline dispatched to GitHub Actions!\n📌 *Topic:* \`${topic}\`\n\nI will monitor the execution and update your mission card.`
          : `⚠️ *Agent Aria:* Failed to dispatch GitHub Action (HTTP ${ghRes.status}). Verify \`GITHUB_PAT_TOKEN\`.`
      );
      return NextResponse.json({ ok: true, dispatched: ghRes.ok, topic });
    }

    // Command: /revenue, /clicks, or /analytics — the 💰 Affiliate & Revenue Ledger
    if (['/revenue', '/clicks', '/analytics', 'revenue', 'clicks'].includes(lower)) {
      await handleRevenueCommand(chatId);
      return NextResponse.json({ ok: true, handler: 'revenue_ledger' });
    }

    // Command: /ytquota or /quota — the 🔑 YouTube Quota Rotator capacity card
    if (['/ytquota', '/quota', 'yt quota', 'quota slots'].includes(lower)) {
      await sendTelegram(chatId, buildYtQuotaCard());
      return NextResponse.json({ ok: true, handler: 'yt_quota' });
    }

    return NextResponse.json({ ok: true });
  } catch (err: any) {
    return NextResponse.json({ ok: false, error: err?.message || 'Unknown error' }, { status: 500 });
  }
}
