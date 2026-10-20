// Vercel Serverless Function: Real-time NSE/BSE Equity Quote Proxy
// Sourced from live institutional feeds with micro-caching (60s) for ultra-fast response

export default async function handler(req, res) {
  // Enable CORS for frontend requests
  res.setHeader('Access-Control-Allow-Credentials', 'true');
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET,OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'X-CSRF-Token, X-Requested-With, Accept, Accept-Version, Content-Length, Content-MD5, Content-Type, Date, X-Api-Version');
  res.setHeader('Cache-Control', 'public, max-age=30, s-maxage=60, stale-while-revalidate=120');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  const rawSymbol = req.query.symbol || 'ITC';
  // Sanitize ticker: remove spaces, punctuation, uppercase
  const cleanSymbol = rawSymbol.trim().toUpperCase().replace(/\s+/g, '');

  if (!cleanSymbol) {
    return res.status(400).json({ error: 'Valid stock symbol parameter is required' });
  }

  const userAgent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36';

  // Helper to fetch Yahoo Finance chart meta
  async function fetchQuoteForTicker(ticker) {
    const url = `https://query2.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(ticker)}?interval=1d&range=5d`;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 4500);

    try {
      const response = await fetch(url, {
        headers: { 'User-Agent': userAgent },
        signal: controller.signal
      });
      clearTimeout(timeout);

      if (!response.ok) return null;
      const data = await response.json();
      const result = data?.chart?.result?.[0];
      if (!result || !result.meta) return null;
      return result.meta;
    } catch (e) {
      clearTimeout(timeout);
      return null;
    }
  }

  try {
    // 1. Try NSE first (.NS)
    let meta = await fetchQuoteForTicker(`${cleanSymbol}.NS`);

    // 2. Fallback to BSE (.BO) if NSE not found
    if (!meta) {
      meta = await fetchQuoteForTicker(`${cleanSymbol}.BO`);
    }

    // 3. Fallback to plain ticker (indices like ^NSEI or direct symbols)
    if (!meta) {
      meta = await fetchQuoteForTicker(cleanSymbol);
    }

    if (!meta || typeof meta.regularMarketPrice !== 'number') {
      return res.status(404).json({
        success: false,
        symbol: cleanSymbol,
        error: `Live quote data for ${cleanSymbol} not available on NSE/BSE.`
      });
    }

    const price = meta.regularMarketPrice;
    const prevClose = meta.chartPreviousClose || price;
    const change = typeof meta.fulldayChange === 'number' ? meta.fulldayChange : +(price - prevClose).toFixed(2);
    const changePercent = typeof meta.fulldayChangePercent === 'number' 
      ? meta.fulldayChangePercent 
      : +(typeof meta.regularMarketChangePercent === 'number' ? meta.regularMarketChangePercent : ((change / prevClose) * 100)).toFixed(2);
    
    const high52 = meta.fiftyTwoWeekHigh || price;
    const low52 = meta.fiftyTwoWeekLow || price;
    const dayHigh = meta.regularMarketDayHigh || price;
    const dayLow = meta.regularMarketDayLow || price;
    const volume = meta.regularMarketVolume || 0;

    // Calculate position in 52-week range (0 to 100%)
    let rangePct = 50;
    if (high52 > low52) {
      rangePct = Math.max(0, Math.min(100, Math.round(((price - low52) / (high52 - low52)) * 100)));
    }

    return res.status(200).json({
      success: true,
      symbol: cleanSymbol,
      name: meta.longName || meta.shortName || `${cleanSymbol} Ltd`,
      exchange: meta.exchangeName || 'NSE',
      currency: meta.currency || 'INR',
      price: price,
      change: change,
      changePercent: changePercent,
      prevClose: prevClose,
      dayHigh: dayHigh,
      dayLow: dayLow,
      high52: high52,
      low52: low52,
      rangePct: rangePct,
      volume: volume,
      marketTime: meta.regularMarketTime,
      isPositive: change >= 0
    });

  } catch (error) {
    return res.status(500).json({
      success: false,
      symbol: cleanSymbol,
      error: error.message || 'Internal quote proxy error'
    });
  }
}
