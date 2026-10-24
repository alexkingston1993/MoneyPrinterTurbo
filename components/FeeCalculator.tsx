'use client';
import { useState } from 'react';

export default function FeeCalculator() {
  const [monthlyTrades, setMonthlyTrades] = useState(50);
  const [avgLotSize, setAvgLotSize] = useState(2000);

  // Fee estimation model: Legacy full-service broker vs Partner Discount Broker
  const traditionalFee = monthlyTrades * 60;
  const discountFee = monthlyTrades * 40;
  const partnerSaved = traditionalFee - discountFee;
  const annualSavings = partnerSaved * 12;

  return (
    <div className="bg-[#121820] border border-gray-800 rounded-xl p-6 my-8 shadow-xl">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-2xl">🧮</span>
        <h3 className="text-xl font-bold text-white tracking-tight">F&O Brokerage & Slippage Savings Calculator</h3>
      </div>
      <p className="text-gray-400 text-sm mb-6">
        See how much you save in annual fees by routing your trades through optimized partner platforms with zero delivery and flat discounted rates.
      </p>
      
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 mb-6">
        <div className="bg-[#161B22] p-4 rounded-lg border border-gray-800">
          <div className="flex justify-between items-center mb-2">
            <label className="text-xs font-semibold text-gray-300">Monthly Trades Executed</label>
            <span className="text-xs font-mono font-bold text-emerald-400 bg-emerald-950/60 px-2 py-0.5 rounded border border-emerald-800/50">
              {monthlyTrades} trades
            </span>
          </div>
          <input 
            type="range" min="10" max="300" step="10" value={monthlyTrades} 
            onChange={(e) => setMonthlyTrades(Number(e.target.value))}
            className="w-full accent-emerald-500 cursor-pointer h-2 bg-gray-700 rounded-lg appearance-none"
          />
          <div className="flex justify-between text-[11px] text-gray-500 mt-1">
            <span>10 trades</span>
            <span>150 trades</span>
            <span>300 trades</span>
          </div>
        </div>

        <div className="bg-[#161B22] p-4 rounded-lg border border-gray-800">
          <div className="flex justify-between items-center mb-2">
            <label className="text-xs font-semibold text-gray-300">Avg. Turnover per Trade (₹)</label>
            <span className="text-xs font-mono font-bold text-emerald-400 bg-emerald-950/60 px-2 py-0.5 rounded border border-emerald-800/50">
              ₹{avgLotSize.toLocaleString()}
            </span>
          </div>
          <input 
            type="range" min="500" max="10000" step="500" value={avgLotSize} 
            onChange={(e) => setAvgLotSize(Number(e.target.value))}
            className="w-full accent-emerald-500 cursor-pointer h-2 bg-gray-700 rounded-lg appearance-none"
          />
          <div className="flex justify-between text-[11px] text-gray-500 mt-1">
            <span>₹500</span>
            <span>₹5,000</span>
            <span>₹10,000</span>
          </div>
        </div>
      </div>

      <div className="bg-[#161B22] p-5 rounded-lg flex flex-col sm:flex-row items-center justify-between border border-emerald-500/40 gap-4">
        <div>
          <p className="text-xs font-medium text-gray-400">Estimated Annual Brokerage & Friction Savings</p>
          <p className="text-3xl font-black text-emerald-400 font-mono tracking-tight">₹{annualSavings.toLocaleString()} <span className="text-sm font-normal text-gray-400">/year</span></p>
        </div>
        <a 
          href="/go/zerodha" 
          className="bg-emerald-600 hover:bg-emerald-500 text-white font-bold px-6 py-3 rounded-lg text-sm transition-all duration-200 text-center w-full sm:w-auto shadow-lg hover:shadow-emerald-600/30 flex items-center justify-center gap-2"
        >
          <span>Claim Partner Perks</span>
          <span>→</span>
        </a>
      </div>
    </div>
  );
}
