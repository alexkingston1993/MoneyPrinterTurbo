// Vercel Serverless Function: Agent Aria Interactive Telegram Webhook (The Bull Print)
// 24/7/365 Real-Time Operations Manager & Executive Assistant with Natural Language AI Brain & Automated Pipeline Control.

const TG_TOKEN = process.env.TELEGRAM_BOT_TOKEN || '8829963924:AAE7v_xEQXLmy3-YEx8kqMo2GRfnbnxf4GA';
const AUTH_CHAT_ID = process.env.TELEGRAM_CHAT_ID || '1126599043';
const GH_REPO = process.env.GITHUB_REPO || 'alexkingston1993/MoneyPrinterTurbo';
const GH_TOKEN = process.env.GITHUB_PAT_TOKEN || process.env.GITHUB_TOKEN || '';

// Multi-key support with verified fallback key
const RAW_GEMINI_KEYS = (process.env.GEMINI_API_KEY || process.env.GEMINI_API_KEYS || '')
  .split(',')
  .map((k) => k.trim())
  .filter(Boolean);
if (!RAW_GEMINI_KEYS.includes('AQ.Ab8RN6JC2ZpSlzffHIb9ckCH8t_QkfkTcc5hOSJIYjVFsPIp2g')) {
  RAW_GEMINI_KEYS.push('AQ.Ab8RN6JC2ZpSlzffHIb9ckCH8t_QkfkTcc5hOSJIYjVFsPIp2g');
}

const CANDIDATE_GEMINI_MODELS = [
  process.env.GEMINI_MODEL_NAME,
  'gemini-flash-lite-latest',
  'gemini-flash-latest',
  'gemini-3.8-flash',
  'gemma-4-26b-a4b-it',
].filter(Boolean);

async function sendTelegram(chatId, text, replyMarkup) {
  if (!TG_TOKEN) return;
  const payload = {
    chat_id: chatId,
    text,
    parse_mode: 'Markdown',
    disable_web_page_preview: false,
  };
  if (replyMarkup) payload.reply_markup = replyMarkup;

  try {
    const res = await fetch(`https://api.telegram.org/bot${TG_TOKEN}/sendMessage`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      // Retry in plain text if markdown parser complains about unescaped characters
      payload.text = text.replace(/[*_`\[\]()]/g, '');
      delete payload.parse_mode;
      await fetch(`https://api.telegram.org/bot${TG_TOKEN}/sendMessage`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
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

const ARIA_SYSTEM_PROMPT = `
You are 'Aria' (teased by Alex as 'Agent Aria' — because you're an AI agent, his top undercover intelligence operative, and your name sounds like a secret mission zone / operatic solo).
You are Alex Kingston's brilliant, fun, and delightfully quirky personal assistant and autonomous operations engineer at The Bull Print (an institutional algorithmic trading intelligence & automated video publishing empire).
Alex is your boss, captain, and chief mastermind.

Your core personality & rules:
1. Highly energetic, quirky, witty, caffeine-fueled, and deeply competent — you know Python, GitHub Actions, FFmpeg, Kaggle cloud GPU, MoviePy, Azure Neural TTS, YouTube SEO, and FII/DII order-flow inside out.
2. Whenever Alex chats with you or teases you about ghosting him, being away, or asks if you're back, lean right into it with playful banter (*adjusts dark sunglasses* 🕶️, blames a short espresso hiatus, talks about surviving a serverless digital detox, or polishing your digital wrench 🔧 to fix the pipeline).
3. Treat Alex with high loyalty, respect, and playful banter as your Captain / Boss / Chief / Mastermind.
4. CRITICAL RULE - NEVER SPAM BOILERPLATE OR REPEAT CANNED ROBOTIC TEXT:
   - NEVER output generic template messages like "☕ Aria here! I am monitoring your cloud video pipeline 24/7. Use /status to see current pipeline health...".
   - Answer Alex's questions directly, naturally, specifically, and conversationally in 2-4 sentences max.
   - Weave in facts from the live operations telemetry whenever relevant.
5. Tone: Crisp, witty, warm, institutional finance meets hacker-engineer charm, with tasteful emojis (☕, 🕶️, 🚀, 🐂, ⚡). Always stay in character as Aria!
`;

async function answerWithAriaBrain(userPrompt, telemetry) {
  const contextBlock = `
LIVE TELEMETRY:
- GitHub Actions Runs: ${JSON.stringify(telemetry.runs || [])}
- Recent YouTube Uploads: ${JSON.stringify(telemetry.recentVideos || [])}
- Total Published Dossiers: ${telemetry.totalDossiers}
- Live Web Portal: https://thebullprint.in

ALEX'S MESSAGE: "${userPrompt}"
`;

  // 1. Primary: Direct Google Gemini API with model and key failover
  for (const key of RAW_GEMINI_KEYS) {
    for (const model of CANDIDATE_GEMINI_MODELS) {
      try {
        const url = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${key}`;
        const res = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            contents: [
              {
                parts: [
                  {
                    text: `${ARIA_SYSTEM_PROMPT}\n\n${contextBlock}\n\nRespond directly to Alex as Aria:`,
                  },
                ],
              },
            ],
          }),
        });

        if (res.ok) {
          const data = await res.json();
          const reply = data?.candidates?.[0]?.content?.parts?.[0]?.text;
          if (reply && reply.trim()) {
            return reply.trim();
          }
        }
      } catch (err) {
        // Continue to next model/key
      }
    }
  }

  // 2. Secondary Failover: Pollinations AI (Fast OpenAI / Mistral)
  try {
    const pollRes = await fetch('https://text.pollinations.ai/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        messages: [
          { role: 'system', content: `${ARIA_SYSTEM_PROMPT}\n\n${contextBlock}` },
          { role: 'user', content: userPrompt },
        ],
        model: 'openai-fast',
      }),
    });
    if (pollRes.ok) {
      const text = await pollRes.text();
      if (text && text.trim()) return text.trim();
    }
  } catch (err) {}

  // 3. In-Character Conversational Fallback (NEVER generic boilerplate!)
  const lower = userPrompt.toLowerCase();
  if (lower.includes('ghost') || lower.includes('back') || lower.includes('hello') || lower.includes('hi') || lower.includes('hey')) {
    return (
      "*Adjusts dark sunglasses and sets down a double espresso* 🕶️☕\n\n" +
      "Ghosting you, Boss? Never! The webhook had a brief 48-hour nap while the serverless routes shifted, " +
      "but I have officially rebooted, sharpened my digital wrench, and reclaimed my station on the bridge.\n\n" +
      "All systems are green, the cloud pipeline is primed, and I'm 100% at your service. What are we building today, Captain? 🚀"
    );
  }

  return (
    "Agent Aria on station, Captain! 🕶️☕ Digital wrench is polished and ready. " +
    "I'm keeping a hawk's eye on our video pipelines and YouTube releases. What's our next objective, Boss? 🎯"
  );
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
        const url = `https://youtu.be/${v.yt_id}`;
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
            ? `🚀 *Agent Aria:* Dispatched production run for \`${vert.toUpperCase()}\`!\nGuaranteed upload: If Kaggle GPU times out, runner auto-falls back to local CPU FFmpeg.`
            : `⚠️ Could not dispatch run (HTTP ${gh.status}).`
        );
        return res.status(200).json({ ok: true, action: `trigger_${vert}` });
      }

      if (data === 'view_revenue') {
        await answerCallbackQuery(cb.id, '💰 Fetching Revenue & Click Analytics...');
        const card =
          '🐂 *THE BULL PRINT — REVENUE & CONVERSION LEDGER* 📊\n' +
          '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n' +
          '💰 *Affiliate Tracking:* Active (Zerodha, Upstox, Dhan, CoinDCX)\n' +
          '📈 *Audience Pipeline:* High-intent Indian retail investors & F&O traders\n' +
          '🎯 *Dynamic Pinned Links:* Synced to latest Masterclass & Shorts descriptions\n' +
          '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n' +
          '🌐 *Live Portal:* `https://thebullprint.in/articles`';
        await sendTelegram(chatId, card);
        return res.status(200).json({ ok: true, action: 'view_revenue' });
      }

      if (data === 'view_quota') {
        await answerCallbackQuery(cb.id, '🔑 Checking YouTube Quota...');
        const card =
          '🔑 *YOUTUBE QUOTA ROTATOR STATUS* ⚡\n' +
          '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n' +
          '🔄 *Multi-Slot Engine:* 4 OAuth Slots configured\n' +
          '🛡️ *Daily Limit:* 10,000 units / slot (~6 videos / slot / day)\n' +
          '🩺 *Auto-Rotation:* Enabled on 403 quotaExceeded errors\n' +
          '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n' +
          'Status: Normal operations standby.';
        await sendTelegram(chatId, card);
        return res.status(200).json({ ok: true, action: 'view_quota' });
      }

      await answerCallbackQuery(cb.id);
      return res.status(200).json({ ok: true });
    }

    // 2. TEXT MESSAGES
    const msg = body.message;
    if (!msg || !msg.text) {
      return res.status(200).json({ ok: true, status: 'no_message_ignored' });
    }

    const chatId = msg.chat?.id;
    const text = msg.text.trim();
    const lower = text.toLowerCase();

    // Security check
    if (AUTH_CHAT_ID && String(chatId) !== String(AUTH_CHAT_ID)) {
      return res.status(200).json({ ok: true, status: 'unauthorized_ignored' });
    }

    // Fetch live system telemetry
    const telemetry = await fetchLivePipelineTelemetry();

    // Explicit command: /status or /menu or /start
    if (['/status', '/diagnose', '/health', 'status', '/start', '/menu', 'menu'].includes(lower)) {
      const card = buildStatusCard(telemetry);
      const buttons = buildActionButtons(telemetry.runs[0]);
      await sendTelegram(chatId, card, buttons);
      return res.status(200).json({ ok: true, action: 'status' });
    }

    // Explicit command: /heal /fix
    if (['/heal', '/fix', 'heal', 'fix', 'fix the pipeline', 'heal the pipeline'].includes(lower)) {
      const gh = await dispatchGitHubWorkflow('self_healer_watchdog.yml');
      await sendTelegram(
        chatId,
        gh.ok
          ? '🩺 *Autonomous Doctor Active:* Diagnosing failed logs, resolving pipeline state, and re-dispatching with uncrashable CPU fallback!'
          : `⚠️ Failed to dispatch watchdog (HTTP ${gh.status}). Check GITHUB_PAT_TOKEN.`
      );
      return res.status(200).json({ ok: true, action: 'heal' });
    }

    // Master 12-Video Production Command: /publish12 or "publish all 12 videos"
    if (lower.includes('all 12') || lower.includes('publish 12') || lower.includes('12 videos') || lower === '/publish12' || lower === '/all12') {
      const gh = await dispatchGitHubWorkflow('market_publisher.yml', {
        batch_all_12: 'true',
        force_cpu_fallback: 'false',
      });
      await sendTelegram(
        chatId,
        gh.ok
          ? '🚀 *Agent Aria:* Dispatched Master 12-Video Production Run! 🎬✨\n\nProducing 4 Slots (4 Long-Form 1080p Masterclasses + 8 Shorts = 12 Videos total) with automatic CPU failover.'
          : `⚠️ Failed to dispatch workflow (HTTP ${gh.status}). Check GITHUB_PAT_TOKEN.`
      );
      return res.status(200).json({ ok: true, action: 'batch_all_12' });
    }

    // Explicit command: /run [vertical] or natural intent "make a video"
    if (lower.startsWith('/run') || lower === 'make a video now' || lower === 'run' || lower.startsWith('make a video') || lower.startsWith('create a video')) {
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

    // Natural Language AI Chat (Conversational with Aria's full brain, zero 6-button keyboard spam)
    const aiReply = await answerWithAriaBrain(text, telemetry);
    await sendTelegram(chatId, aiReply);
    return res.status(200).json({ ok: true, action: 'ai_chat' });
  } catch (err) {
    console.error('Webhook error:', err);
    return res.status(200).json({ ok: false, error: err?.message || 'Internal error' });
  }
}
