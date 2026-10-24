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
                [
                  { text: '🔄 Re-Run Failed Jobs', callback_data: `rerun_failed:${latest.id}` },
                  { text: '🩹 Force Clean Rebuild', callback_data: 'run_slot:Institutional Order Flow & Macro Liquidity' },
                ],
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
                ],
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

    return NextResponse.json({ ok: true });
  } catch (err: any) {
    return NextResponse.json({ ok: false, error: err?.message || 'Unknown error' }, { status: 500 });
  }
}
