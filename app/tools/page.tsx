import React from 'react';
import Head from 'next/head';
import FeeCalculator from '@/components/FeeCalculator';

export default function ToolsPage() {
  return (
    <div className="min-h-screen bg-[#0B0E14] text-gray-100 font-sans px-4 sm:px-6 lg:px-8 py-12">
      <Head>
        <title>Trading Stack, Charting Tools & Brokers | Flipzon</title>
        <meta name="description" content="Explore the exact charting software, order flow tools, and broker platforms I use for Indian Equities, F&O, and Global Crypto derivatives." />
      </Head>

      <div className="max-w-4xl mx-auto">
        
        {/* TOP COMPLIANCE & PARTNER DISCLOSURE BANNER */}
        <div className="bg-[#161B22] border border-gray-800 rounded-lg p-4 mb-8 text-xs text-gray-400">
          <span className="font-semibold text-gray-300">🔒 Partner & Regulatory Disclosure:</span> Some links on this page are partner/referral links. When you register through them, you unlock exclusive fee discounts, and we may earn a referral commission at no extra cost to you. We are not SEBI-registered Investment Advisers or Research Analysts.
        </div>

        {/* HERO HEADER */}
        <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-white mb-4">
          The Trading Stack: Platforms, Charting & Order Flow Tools
        </h1>
        <p className="text-gray-300 text-base sm:text-lg mb-8">
          Every week on YouTube, I get asked about my chart setup, Footprint indicators, and low-slippage brokers. Below is my complete battle-tested stack.
        </p>

        {/* QUICK COMPARISON TABLE */}
        <div className="overflow-x-auto mb-8 border border-gray-800 rounded-xl bg-[#121820]">
          <table className="w-full text-left border-collapse text-sm">
            <thead>
              <tr className="border-b border-gray-800 text-gray-400 bg-[#161B22]">
                <th className="p-4">Category</th>
                <th className="p-4">Platform</th>
                <th className="p-4">Partner Perk</th>
                <th className="p-4">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              <tr>
                <td className="p-4 font-medium text-white">Charting</td>
                <td className="p-4">TradingView</td>
                <td className="p-4 text-emerald-400">$15 Bonus Credit</td>
                <td className="p-4"><a href="/tv" className="text-blue-400 hover:underline">Claim Credit →</a></td>
              </tr>
              <tr>
                <td className="p-4 font-medium text-white">Order Flow</td>
                <td className="p-4">GoCharting</td>
                <td className="p-4 text-emerald-400">Partner Pricing</td>
                <td className="p-4"><a href="/gocharting" className="text-blue-400 hover:underline">Try Now →</a></td>
              </tr>
              <tr>
                <td className="p-4 font-medium text-white">Indian F&O</td>
                <td className="p-4">Zerodha</td>
                <td className="p-4 text-emerald-400">Free Sensibull Access</td>
                <td className="p-4"><a href="/zerodha" className="text-blue-400 hover:underline">Open Account →</a></td>
              </tr>
              <tr>
                <td className="p-4 font-medium text-white">Crypto Options</td>
                <td className="p-4">Delta Exchange</td>
                <td className="p-4 text-emerald-400">10% Fee Discount</td>
                <td className="p-4"><a href="/delta" className="text-blue-400 hover:underline">Get Discount →</a></td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* INTERACTIVE FEE CALCULATOR WIDGET */}
        <FeeCalculator />

        {/* SECTION 1: CHARTING SOFTWARE */}
        <section className="space-y-6 mb-12">
          <h2 className="text-2xl font-bold text-white border-b border-gray-800 pb-2">1. Charting & Order Flow Software</h2>
          
          <div className="bg-[#121820] border border-gray-800 rounded-xl p-6">
            <h3 className="text-xl font-semibold text-white mb-2">📈 TradingView</h3>
            <p className="text-gray-300 text-sm mb-4">Primary platform for multi-timeframe price action, macro market structure, and historical bar-replay backtesting sessions.</p>
            <a href="/tv" className="inline-block bg-emerald-600 hover:bg-emerald-500 text-white font-medium px-5 py-2.5 rounded-lg text-sm transition">
              Try TradingView & Claim $15 Credit
            </a>
          </div>

          <div className="bg-[#121820] border border-gray-800 rounded-xl p-6">
            <h3 className="text-xl font-semibold text-white mb-2">📊 GoCharting</h3>
            <p className="text-gray-300 text-sm mb-4">Essential browser-based Footprint clusters, Cumulative Volume Delta (CVD), and Volume Profile for Nifty, BankNifty, and Crypto.</p>
            <a href="/gocharting" className="inline-block bg-emerald-600 hover:bg-emerald-500 text-white font-medium px-5 py-2.5 rounded-lg text-sm transition">
              Explore GoCharting Partner Pricing
            </a>
          </div>
        </section>

        {/* SECTION 2: BROKERS */}
        <section className="space-y-6 mb-12">
          <h2 className="text-2xl font-bold text-white border-b border-gray-800 pb-2">2. Execution & Brokerage Platforms</h2>

          <div className="bg-[#121820] border border-gray-800 rounded-xl p-6">
            <h3 className="text-xl font-semibold text-white mb-2">🇮🇳 Zerodha (Indian Equities & F&O)</h3>
            <p className="text-gray-300 text-sm mb-4">Reliable execution, clean Kite UI, zero delivery fees, and 100% free access to Sensibull options analytics.</p>
            <a href="/zerodha" className="inline-block bg-blue-600 hover:bg-blue-500 text-white font-medium px-5 py-2.5 rounded-lg text-sm transition">
              Open Zerodha Account
            </a>
          </div>

          <div className="bg-[#121820] border border-gray-800 rounded-xl p-6">
            <h3 className="text-xl font-semibold text-white mb-2">⚡ Delta Exchange India (Crypto in INR)</h3>
            <p className="text-gray-300 text-sm mb-4">FIU-registered in India. Trade Bitcoin and Ethereum options/futures directly in Rupees via IMPS/NEFT with a 10% fee discount.</p>
            <a href="/delta" className="inline-block bg-blue-600 hover:bg-blue-500 text-white font-medium px-5 py-2.5 rounded-lg text-sm transition">
              Join Delta Exchange (10% Off Fees)
            </a>
          </div>
        </section>

        {/* LEGAL FOOTER */}
        <footer className="border-t border-gray-800 pt-6 text-xs text-gray-500 space-y-2">
          <p><strong>Disclaimer:</strong> Content provided strictly for educational purposes. We are not SEBI-registered Investment Advisers or Research Analysts. 9 out of 10 individual traders in equity F&O incur net losses.</p>
          <p>© 2026 Flipzon. All rights reserved.</p>
        </footer>

      </div>
    </div>
  );
}
