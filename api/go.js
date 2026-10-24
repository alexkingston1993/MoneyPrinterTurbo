// Vercel Serverless Function: Affiliate Redirect with UTM Preservation + Zero-DB Click Telemetry
const AFFILIATE_LINKS = {
  zerodha: 'https://zerodha.com/open-account?c=YOUR_CODE',
  tradingview: 'https://www.tradingview.com/?aff_id=YOUR_ID',
  gocharting: 'https://gocharting.com/pricing?code=YOUR_CODE',
  delta: 'https://www.delta.exchange/?code=YOUR_CODE',
  bybit: 'https://www.bybit.com/invite?ref=YOUR_CODE'
};

const GITHUB_API = 'https://api.github.com';
const TELEMETRY_VAR = 'AFFILIATE_TELEMETRY_JSON';

function blankTelemetry() {
  return { total_clicks: 0, brokers: {}, campaigns: {}, updated_at: '' };
}

function ghHeaders(token) {
  return {
    Authorization: `token ${token}`,
    Accept: 'application/vnd.github+json',
    'Content-Type': 'application/json',
    'User-Agent': 'TheBullPrint-Go-Telemetry'
  };
}

/**
 * Zero-DB click telemetry: increments counters inside the GitHub Actions
 * Repository Variable AFFILIATE_TELEMETRY_JSON. All network work is best-effort
 * and silent — the user's redirect is never slowed down or failed by telemetry.
 */
async function trackAffiliateClick(repo, token, brokerKey, utmMedium, utmCampaign) {
  if (!token) return;
  const headers = ghHeaders(token);

  let data = blankTelemetry();
  try {
    const res = await fetch(`${GITHUB_API}/repos/${repo}/actions/variables/${TELEMETRY_VAR}`, { headers });
    if (res.status === 404) {
      // First-ever click: create the ledger variable, then keep going.
      await fetch(`${GITHUB_API}/repos/${repo}/actions/variables`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ name: TELEMETRY_VAR, value: JSON.stringify(data) })
      });
    } else if (res.ok) {
      const raw = (await res.json()).value;
      data = { ...blankTelemetry(), ...JSON.parse(raw) };
    }
  } catch {
    // Start from a blank ledger when GitHub is unreachable; never block.
  }

  data.total_clicks = (data.total_clicks || 0) + 1;
  data.brokers = data.brokers || {};
  data.brokers[brokerKey] = (data.brokers[brokerKey] || 0) + 1;
  data.campaigns = data.campaigns || {};
  data.campaigns[utmCampaign || 'none'] = (data.campaigns[utmCampaign || 'none'] || 0) + 1;
  data.updated_at = new Date().toISOString();

  try {
    await fetch(`${GITHUB_API}/repos/${repo}/actions/variables/${TELEMETRY_VAR}`, {
      method: 'PATCH',
      headers,
      body: JSON.stringify({ value: JSON.stringify(data) })
    });
  } catch {
    // Silently drop the write; GA UTMs remain the authoritative backup.
  }
}

export default function handler(req, res) {
  const { broker, utm_source, utm_medium, utm_campaign } = req.query;
  const key = (broker || '').toLowerCase();
  const target = AFFILIATE_LINKS[key];

  if (!target) {
    res.writeHead(302, { Location: '/tools.html' });
    return res.end();
  }

  // Fire-and-forget click telemetry — never awaited, never throws.
  const repo = process.env.GITHUB_REPO || 'alexkingston1993/MoneyPrinterTurbo';
  const token = process.env.GITHUB_PAT_TOKEN || process.env.GITHUB_TOKEN || '';
  trackAffiliateClick(repo, token, key, utm_medium, utm_campaign).catch(() => {});

  const url = new URL(target);
  url.searchParams.set('utm_source', utm_source || 'youtube');
  url.searchParams.set('utm_medium', utm_medium || 'video_description');
  url.searchParams.set('utm_campaign', utm_campaign || 'auto_engine');

  res.writeHead(307, { Location: url.toString() });
  res.end();
}
