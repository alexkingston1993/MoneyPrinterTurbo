// Vercel Serverless Function: Affiliate Redirect with UTM Preservation
const AFFILIATE_LINKS = {
  zerodha: 'https://zerodha.com/open-account?c=YOUR_CODE',
  tradingview: 'https://www.tradingview.com/?aff_id=YOUR_ID',
  gocharting: 'https://gocharting.com/pricing?code=YOUR_CODE',
  delta: 'https://www.delta.exchange/?code=YOUR_CODE'
};

export default function handler(req, res) {
  const { broker, utm_source, utm_medium, utm_campaign } = req.query;
  const key = (broker || '').toLowerCase();
  const target = AFFILIATE_LINKS[key];

  if (!target) {
    res.writeHead(302, { Location: '/tools.html' });
    return res.end();
  }

  const url = new URL(target);
  url.searchParams.set('utm_source', utm_source || 'youtube');
  url.searchParams.set('utm_medium', utm_medium || 'video_description');
  url.searchParams.set('utm_campaign', utm_campaign || 'auto_engine');

  res.writeHead(307, { Location: url.toString() });
  res.end();
}
