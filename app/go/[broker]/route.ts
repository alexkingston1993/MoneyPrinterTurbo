import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

const AFFILIATE_LINKS: Record<string, string> = {
  zerodha: 'https://zerodha.com/open-account?c=YOUR_CODE',
  tradingview: 'https://www.tradingview.com/?aff_id=YOUR_ID',
  gocharting: 'https://gocharting.com/pricing?code=YOUR_CODE',
  delta: 'https://www.delta.exchange/?code=YOUR_CODE',
};

export async function GET(
  request: NextRequest,
  { params }: { params: { broker: string } }
) {
  const brokerKey = params.broker?.toLowerCase() || '';
  const targetUrl = AFFILIATE_LINKS[brokerKey];

  if (!targetUrl) {
    return NextResponse.redirect(new URL('/tools', request.url));
  }

  // Parse incoming UTMs from YouTube descriptions, email newsletters, or social links
  const urlObj = new URL(targetUrl);
  const searchParams = request.nextUrl.searchParams;

  urlObj.searchParams.set('utm_source', searchParams.get('utm_source') || 'youtube');
  urlObj.searchParams.set('utm_medium', searchParams.get('utm_medium') || 'video_description');
  urlObj.searchParams.set('utm_campaign', searchParams.get('utm_campaign') || 'auto_engine');

  return NextResponse.redirect(urlObj.toString(), { status: 307 });
}
