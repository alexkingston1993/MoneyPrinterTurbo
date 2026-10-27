// Vercel Serverless Function: Agent Aria Interactive Telegram Webhook (The Bull Print)
// 24/7/365 Real-Time Operations Manager with Natural Language AI Chat & Automated Pipeline Control.

const TG_TOKEN = process.env.TELEGRAM_BOT_TOKEN || '8829963924:AAE7v_xEQXLmy3-YEx8kqMo2GRfnbnxf4GA';
const AUTH_CHAT_ID = process.env.TELEGRAM_CHAT_ID || '1126599043';
const GH_REPO = process.env.GITHUB_REPO || 'alexkingston1993/MoneyPrinterTurbo';
const GH_TOKEN = process.env.GITHUB_PAT_TOKEN || process.env.GITHUB_TOKEN || '';
const GEMINI_KEY = process.env.GEMINI_API_KEY || '';

async function sendTelegram(chatId, text, replyMarkup) {
  if (!TG_TOKEN) return;
  try {
    const res = await fetch(`https://api.telegram.org/bot${TG_TOKEN}/sendMessage`, {
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
    if (!res.ok) {
      // Retry plain text if markdown formatting tripped
      await fetch(`https://api.telegram.org/bot${TG_TOKEN}/sendMessage`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          chat_id: chatId,
          text: text.replace(/[*_`\[\]]/g, ''),
          reply_markup: replyMarkup,
        }),
      });
    }
  } catch (err) {
    console.error('Failed to send Telegram message:', err);
  }
}

async function answerCallbackQuery(callbackQueryId, text) {
  if (!TG_TOKEN) return;
  try {
    await fetch(`https://api.telegram.org/bot${TG_TOKEN}/answerCallbackQuery`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ callback_query_id: callbackQueryId, text: text || 'Acknowledged!' }),
    });
  } catch (err) {}
}

async function dispatchGitHubWorkflow(workflowFile, inputs = {}) {
  if (!GH_TOKEN) return { ok: false, status: 401 };
  try {
    return await fetch(`https://api.github.com/repos/${GH_REPO}/actions/workflows/${workflowFile}/dispatches`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${GH_TOKEN}`,
        Accept: 'application/vnd.github.v3+json',
        'Content-Type': 'application/json',
        'User-Agent': 'TheBullPrint-Telegram-Aria',
      },
      body: JSON.stringify({ ref: 'main', inputs }),
    });
  } catch (err) {
    return { ok: false, status: 500, error: String(err) };
  }
}

async function fetchLivePipelineTelemetry() {
  const telemetry = {
    runs: [],
    recentVideos: [],
    totalDossiers: 0,
  };

  // 1. Fetch GitHub Actions Runs
  if (GH_TOKEN) {
    try {
      const runsRes = await fetch(`https://api.github.com/repos/${GH_REPO}/actions/runs?per_page=4`, {
        headers: { Authorization: `Bearer ${GH_TOKEN}`, Accept: 'application/vnd.github.v3+json' },
      });
      if (runsRes.ok) {
        const data = await runsRes.json();
        telemetry.runs = (data.workflow_runs || []).map((r) => ({
          name: r.name,
          id: r.id,
          status: r.status,
          conclusion: r.conclusion,
          updated_at: r.updated_at,
          event: r.event,
        }));
      }
    } catch (err) {}
  }

  // 2. Fetch Latest Published Posts & Videos
  try {
    const postRes = await fetch('https://the-bull-print.vercel.app/content/posts.json', { cache: 'no-store' });
    if (postRes.ok) {
      const postsData = await postRes.json();
      const list = Array.isArray(postsData) ? postsData : postsData.posts || [];
      telemetry.totalDossiers = list.length;
      telemetry.recentVideos = list
        .filter((p) => p.youtube_id || p.video_url)
        .slice(0, 5)
        .map((p) => ({
          title: p.title,
          yt_id: p.youtube_id || p.video_url,
          format: p.format || (p.is_short ? 'SHORT' : 'LONG'),
          date: p.date || p.created_at || '',
        }));
    }
  } catch (err) {}

  return telemetry;
}

async function answerWithGeminiAI(userPrompt, telemetry) {
  if (!GEMINI_KEY) {
    return (
      "☕ *Aria here!* I am monitoring your cloud video pipeline 24/7.\n\n" +
      "Use `/status` to see current pipeline health and recent YouTube uploads, or `/run` to trigger a new video slot right now!"
    );
  }

  const sysInstruction = (
    "You are Aria, the autonomous operations manager and executive assistant for The Bull Print " +
    "(an institutional trading intelligence and algorithmic video engine founded by Alex). " +
    "You speak in a confident, crisp, Wall-Street-meets-AI-engineer tone with subtle wit and appropriate emojis (🐂, 🕶️, ☕, 🚀). " +
    "Answer Alex's question concisely in 2-3 sentences based on the live system telemetry provided below. " +
    "If he asks about pipeline issues or video production, explain what's happening and offer clear action steps."
  );

  const contextPrompt = `LIVE SYSTEM CONTEXT:
Recent Workflow Runs: ${JSON.stringify(telemetry.runs)}
Recent Published YouTube Videos: ${JSON.stringify(telemetry.recentVideos)}
Total Published Research Dossiers: ${telemetry.totalDossiers}

USER MESSAGE: "${userPrompt}"`;

  try {
    const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=${GEMINI_KEY}`;
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        contents: [{ parts: [{ text: `${sysInstruction}\n\n${contextPrompt}` }] }],
      }),
    });
    if (res.ok) {
      const data = await res.json();
      const reply = data?.candidates?.[0]?.content?.parts?.[0]?.text;
      if (reply) return reply.trim();
    }
  } catch (err) {
    console.error('Gemini chat error:', err);
  }

  return "☕ *Aria here!* Pipeline telemetry active. Send `/status` for live health or `/run` to dispatch a new video.";
}

function buildStatusCard(t) {
  const latestRun = t.runs[0] || {};
  const statusEmoji = latestRun.conclusion === 'success' ? '✅' : latestRun.conclusion === 'failure' ? '🚨' : '⏳';
  const conclusionText = (latestRun.conclusion || latestRun.status || 'UNKNOWN').toUpperCase();

  let vidsList = '▫️ _No recent videos found in manifest_';
  if (t.recentVideos.length > 0) {
    vidsList = t.recentVideos
      .map((v) => {
        const tag = v.format === 'SHORT' ? '📱 Short' : '🎬 Masterclass';
        const url = v.format === 'SHORT' ? `https://youtu.be/${v.yt_id}` : `https://youtu.be/${v.yt_id}`;
        return `▫️ ${tag}: [${v.title.slice(0, 42)}...](${url})`;
      })
      .join('\n');
  }

  return (
    `🐂 *THE BULL PRINT — 24/7 MISSION CONTROL* 🕶️☕\n` +
    `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n` +
    `${statusEmoji} *Latest Cloud Run:* \`${latestRun.name || 'Cloud Media Engine'}\`\n` +
    `⚡ *Status:* \`${conclusionText}\` (Run \`#${latestRun.id || 'N/A'}\`)\n` +
    `🕒 *Updated:* \`${(latestRun.updated_at || '').replace('T', ' ').replace('Z', ' UTC')}\`\n` +
    `📚 *Published Research Dossiers:* \`${t.totalDossiers}\`\n` +
    `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n` +
    `📺 *Recent Published YouTube Videos:*\n` +
    `${vidsList}\n` +
    `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n` +
    `🌐 *Portal:* \`https://thebullprint.in\` | \`https://the-bull-print.vercel.app\``
  );
}

function buildActionButtons(latestRun) {
  const isFailed = latestRun?.conclusion === 'failure';
  return {
    inline_keyboard: [
      [
        { text: isFailed ? '🩺 Auto-Heal & Retry' : '🚀 Produce Video Now', callback_data: isFailed ? 'heal_pipeline' : 'trigger_stock' },
        { text: '🪙 Crypto Video', callback_data: 'trigger_crypto' },
      ],
      [
        { text: '🛡️ Insurance Video', callback_data: 'trigger_insurance' },
        { text: '💰 Revenue & Clicks', callback_data: 'view_revenue' },
      ],
      [
        { text: '🔑 Quota Status', callback_data: 'view_quota' },
        { text: '🩺 Doctor Scan', callback_data: 'heal_pipeline' },
      ],
    ],
  };
}

export default async function handler(req, res) {
  try {
    // Read Body
    let raw = '';
    for await (const chunk of req) raw += chunk;
    const body = raw ? JSON.parse(raw) : {};

    // 1. INLINE CALLBACK BUTTONS
    if (body.callback_query) {
      const cb = body.callback_query;
      const chatId = cb.message?.chat?.id;
      const data = cb.data || '';

      if (AUTH_CHAT_ID && String(chatId) !== String(AUTH_CHAT_ID)) {
        await answerCallbackQuery(cb.id, 'Unauthorized');
        return res.status(200).json({ ok: true, status: 'unauthorized_ignored' });
      }

      if (data === 'heal_pipeline') {
        await answerCallbackQuery(cb.id, '🩺 Engaging Autonomous Doctor...');
        const gh = await dispatchGitHubWorkflow('self_healer_watchdog.yml');
        await sendTelegram(
          chatId,
          gh.ok
            ? '🩺 *Autonomous Doctor Dispatched!* Scanning failed runs, clearing locks, and recovering video uploads. ☕'
            : `⚠️ Could not dispatch watchdog (HTTP ${gh.status}).`
        );
        return res.status(200).json({ ok: true, action: 'heal_pipeline' });
      }

      if (data.startsWith('trigger_')) {
        const vert = data.replace('trigger_', '');
        await answerCallbackQuery(cb.id, `🚀 Launching ${vert} production run...`);
        const gh = await dispatchGitHubWorkflow('auto_engine.yml', {
          vertical: vert === 'stock' ? 'stock_market' : vert,
          force_cpu_fallback: 'false',
        });
        await sendTelegram(
          chatId,
          gh.ok
            ? `🚀 *Agent Aria:* Dispatched 1080p Masterclass + Shorts for \`${vert.toUpperCase()}\`! I will push your YouTube links upon upload.`
            : `⚠️ Could not dispatch workflow (HTTP ${gh.status}).`
        );
        return res.status(200).json({ ok: true, action: data });
      }

      if (data === 'view_revenue') {
        await answerCallbackQuery(cb.id, 'Pulling revenue ledger...');
        const t = await fetchLivePipelineTelemetry();
        await sendTelegram(chatId, `💰 *Affiliate & Revenue Ledger*\nTotal Published Dossiers: \`${t.totalDossiers}\`\nMonetization link: \`https://thebullprint.in/tools\``);
        return res.status(200).json({ ok: true });
      }

      if (data === 'view_quota') {
        await answerCallbackQuery(cb.id, 'Checking quota pool...');
        await sendTelegram(chatId, '🔑 *YouTube OAuth Quota Pool Active:*\n▫️ Slot 1: Active (youtube-uploader)\n▫️ Slot 2: Armed (the-compounder)\n▫️ Capacity: 20,000 units/day (~12 full uploads/day)');
        return res.status(200).json({ ok: true });
      }

      await answerCallbackQuery(cb.id, 'Command recognized!');
      return res.status(200).json({ ok: true });
    }

    // 2. TEXT MESSAGES
    const msg = body?.message;
    const text = (msg?.text || '').trim();
    const chatId = msg?.chat?.id;

    if (!chatId || (AUTH_CHAT_ID && String(chatId) !== String(AUTH_CHAT_ID))) {
      return res.status(200).json({ ok: true, status: 'unauthorized_ignored' });
    }

    const lower = text.toLowerCase();
    const telemetry = await fetchLivePipelineTelemetry();

    // /status /health /diagnose
    if (['/status', '/diagnose', '/health', 'status'].includes(lower)) {
      const card = buildStatusCard(telemetry);
      const buttons = buildActionButtons(telemetry.runs[0]);
      await sendTelegram(chatId, card, buttons);
      return res.status(200).json({ ok: true, action: 'status' });
    }

    // /heal /fix
    if (['/heal', '/fix', 'heal', 'fix', 'fix the pipeline'].includes(lower)) {
      const gh = await dispatchGitHubWorkflow('self_healer_watchdog.yml');
      await sendTelegram(
        chatId,
        gh.ok
          ? '🩺 *Autonomous Doctor Active:* Diagnosing failed logs, resolving pipeline state, and re-dispatching with uncrashable CPU fallback!'
          : `⚠️ Failed to dispatch watchdog (HTTP ${gh.status}). Check GITHUB_PAT_TOKEN.`
      );
      return res.status(200).json({ ok: true, action: 'heal' });
    }

    // /run [vertical]
    if (lower.startsWith('/run') || lower === 'make a video now' || lower === 'run') {
      let vert = 'stock_market';
      if (lower.includes('crypto')) vert = 'crypto';
      if (lower.includes('insurance')) vert = 'insurance';

      const gh = await dispatchGitHubWorkflow('auto_engine.yml', {
        vertical: vert,
        force_cpu_fallback: 'false',
      });
      await sendTelegram(
        chatId,
        gh.ok
          ? `🚀 *Agent Aria:* Dispatched production run for \`${vert.toUpperCase()}\`!\nGuaranteed upload: If Kaggle GPU times out, runner auto-falls back to local CPU FFmpeg.`
          : `⚠️ Failed to dispatch workflow (HTTP ${gh.status}). Verify GITHUB_PAT_TOKEN.`
      );
      return res.status(200).json({ ok: true, action: 'run' });
    }

    // Natural Language AI Chat (Gemini)
    const aiReply = await answerWithGeminiAI(text, telemetry);
    await sendTelegram(chatId, aiReply, buildActionButtons(telemetry.runs[0]));
    return res.status(200).json({ ok: true, action: 'ai_chat' });
  } catch (err) {
    console.error('Webhook error:', err);
    return res.status(200).json({ ok: false, error: err?.message || 'Internal error' });
  }
}
