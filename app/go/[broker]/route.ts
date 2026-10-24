import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

const AFFILIATE_LINKS: Record<string, string> = {
  zerodha: 'https://zerodha.com/open-account?c=YOUR_CODE',
  tradingview: 'https://www.tradingview.com/?aff_id=YOUR_ID',
  gocharting: 'https://gocharting.com/pricing?code=YOUR_CODE',
  delta: 'https://www.delta.exchange/?code=YOUR_CODE',
  bybit: 'https://www.bybit.com/invite?ref=YOUR_CODE',
};

const GITHUB_API = 'https://api.github.com';
const TELEMETRY_VAR = 'AFFILIATE_TELEMETRY_JSON';

interface TelemetryShape {
  total_clicks: number;
  brokers: Record<string, number>;
  campaigns: Record<string, number>;
  updated_at: string;
}

function blankTelemetry(): TelemetryShape {
  return { total_clicks: 0, brokers: {}, campaigns: {}, updated_at: '' };
}

function ghHeaders(token: string) {
  return {
    Authorization: `token ${token}`,
    Accept: 'application/vnd.github+json',
    'Content-Type': 'application/json',
    'User-Agent': 'TheBullPrint-Go-Telemetry',
  };
}

/**
 * Zero-DB click telemetry: increments counters inside the GitHub Actions
 * Repository Variable AFFILIATE_TELEMETRY_JSON. All network work is best-effort
 * and silent — the user's redirect is never slowed down or failed by telemetry.
 */
async function trackAffiliateClick(
  repo: string,
  token: string,
  brokerKey: string,
  utmSource: string,
  utmMedium: string,
  utmCampaign: string
): Promise<void> {
  if (!token) return;
  const headers = ghHeaders(token);

  let data = blankTelemetry();
  try {
    const res = await fetch(`${GITHUB_API}/repos/${repo}/actions/variables/${TELEMETRY_VAR}`, { headers });
    if (res.status === 404) {
      await fetch(`${GITHUB_API}/repos/${repo}/actions/variables`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ name: TELEMETRY_VAR, value: JSON.stringify(data) }),
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
      body: JSON.stringify({ value: JSON.stringify(data) }),
    });
  } catch {
    // Silently drop the write; GA UTMs remain the authoritative backup.
  }
}

export async function GET(
  request: NextRequest,
  { params }: { params: { broker: string } }
) {
  const brokerKey = params.broker?.toLowerCase() || '';
  const targetUrl = AFFILIATE_LINKS[brokerKey];

  if (!targetUrl) {
    return NextResponse.redirect(new URL('/tools', request.url));
  }

  // Bounded-wait telemetry: serverless freezes after the response is returned and
  // kills fire-and-forget promises, so we track FIRST but cap the wait at ~1.2s —
  // the redirect ALWAYS fires (no lost clicks, no failed/slow redirects).
  const repo = process.env.GITHUB_REPO || 'alexkingston1993/MoneyPrinterTurbo';
  const token = process.env.GITHUB_PAT_TOKEN || process.env.GITHUB_TOKEN || '';
  await Promise.race([
    trackAffiliateClick(
      repo,
      token,
      brokerKey,
      request.nextUrl.searchParams.get('utm_source') || '',
      request.nextUrl.searchParams.get('utm_medium') || '',
      request.nextUrl.searchParams.get('utm_campaign') || ''
    ),
    new Promise((resolve) => setTimeout(resolve, 1200)),
  ]);

  // Parse incoming UTMs from YouTube descriptions, email newsletters, or social links
  const urlObj = new URL(targetUrl);
  const searchParams = request.nextUrl.searchParams;

  urlObj.searchParams.set('utm_source', searchParams.get('utm_source') || 'youtube');
  urlObj.searchParams.set('utm_medium', searchParams.get('utm_medium') || 'video_description');
  urlObj.searchParams.set('utm_campaign', searchParams.get('utm_campaign') || 'auto_engine');

  return NextResponse.redirect(urlObj.toString(), { status: 307 });
}
