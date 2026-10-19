// ==============================================================================
// DALAL STREET ALPHA — APPLICATION SCRIPT
// Quantitative Market Desk, Interactive RevShare Simulator & Fee Engine
// ==============================================================================

document.addEventListener("DOMContentLoaded", () => {
    let allPosts = [];
    let activeFeedCategory = "all";

    // ── 1. Dynamic Indian Standard Time (IST) Clock & Market Session ──
    const marketStatusPill = document.getElementById("market-status-pill");
    const marketStatusLabel = document.getElementById("market-status-label");
    const liveIstClock = document.getElementById("live-ist-clock");

    function updateMarketClock() {
        const now = new Date();
        // Convert to IST (UTC + 5:30)
        const utcMs = now.getTime() + (now.getTimezoneOffset() * 60000);
        const istDate = new Date(utcMs + (5.5 * 3600000));

        // Format Clock: HH:MM:SS.mmm IST
        const hours = String(istDate.getHours()).padStart(2, "0");
        const minutes = String(istDate.getMinutes()).padStart(2, "0");
        const seconds = String(istDate.getSeconds()).padStart(2, "0");
        const ms = String(istDate.getMilliseconds()).padStart(3, "0");
        if (liveIstClock) {
            liveIstClock.textContent = `${hours}:${minutes}:${seconds}.${ms} IST`;
        }

        const day = istDate.getDay(); // 0 = Sun, 6 = Sat
        const totalMinutes = (istDate.getHours() * 60) + istDate.getMinutes();

        const isWeekday = day >= 1 && day <= 5;
        const isOpen = isWeekday && totalMinutes >= (9 * 60 + 15) && totalMinutes <= (15 * 60 + 30);
        const isPreOpen = isWeekday && totalMinutes >= (9 * 60) && totalMinutes < (9 * 60 + 15);

        if (marketStatusPill && marketStatusLabel) {
            if (isOpen) {
                marketStatusPill.className = "market-status-pill open";
                marketStatusLabel.textContent = "LIVE TRADING";
            } else if (isPreOpen) {
                marketStatusPill.className = "market-status-pill open";
                marketStatusLabel.textContent = "PRE-OPEN";
            } else {
                marketStatusPill.className = "market-status-pill closed";
                marketStatusLabel.textContent = "MARKET CLOSED";
            }
        }
    }

    updateMarketClock();
    setInterval(updateMarketClock, 40);

    // ── 2. Hero Visual Switcher Tabs ──
    const visualTabs = document.querySelectorAll(".visual-tab-btn");
    const visualPanels = document.querySelectorAll(".visual-view-panel");

    visualTabs.forEach(tab => {
        tab.addEventListener("click", () => {
            const targetId = tab.getAttribute("data-target");
            visualTabs.forEach(t => t.classList.remove("active"));
            visualPanels.forEach(p => p.classList.remove("active"));

            tab.classList.add("active");
            const activePanel = document.getElementById(targetId);
            if (activePanel) activePanel.classList.add("active");
        });
    });

    // ── 3. Data Loading: Posts & Market Reports ──
    const heroTitle = document.getElementById("hero-title");
    const heroExcerpt = document.getElementById("hero-excerpt");
    const heroDate = document.getElementById("hero-date");
    const heroTag = document.getElementById("hero-tag");
    const heroVideoBox = document.getElementById("hero-video-box");
    const heroGeoText = document.getElementById("hero-geo-text");
    const heroReadBtn = document.getElementById("hero-read-full-btn");
    const articlesGrid = document.getElementById("articles-grid");
    const feedCountBadge = document.getElementById("feed-count-badge");
    const feedCategoryBtns = document.querySelectorAll(".feed-filter-tabs .nav-btn");

    async function loadContent() {
        try {
            const resp = await fetch("content/posts.json");
            if (resp.ok) {
                allPosts = await resp.json();
            } else {
                allPosts = getFallbackPosts();
            }
        } catch (e) {
            console.warn("Using embedded fallback dispatches:", e);
            allPosts = getFallbackPosts();
        }

        renderHero();
        renderFeedGrid();
    }

    function renderHero() {
        if (!allPosts || allPosts.length === 0) return;
        const latest = allPosts[0];

        if (heroTitle) heroTitle.textContent = latest.title;
        if (heroExcerpt) heroExcerpt.textContent = latest.excerpt;
        if (heroDate) heroDate.textContent = `Published: ${latest.date} IST`;
        if (heroTag) {
            heroTag.textContent = (latest.categories && latest.categories[0]) 
                ? latest.categories[0].toUpperCase() 
                : "NIFTY ANALYSIS";
        }

        if (heroGeoText && latest.excerpt) {
            heroGeoText.innerHTML = latest.excerpt;
        }

        if (heroReadBtn) {
            heroReadBtn.onclick = () => openReaderModal(latest);
        }

        // Render video if available
        if (heroVideoBox) {
            const hasRealVideo = latest.youtubeUrl && !latest.youtubeUrl.includes("dQw4w9WgXcQ");
            if (hasRealVideo) {
                const vidId = extractYouTubeId(latest.youtubeUrl);
                heroVideoBox.innerHTML = `
                    <div class="yt-embed-wrapper">
                        <iframe src="https://www.youtube.com/embed/${vidId}?rel=0" 
                                title="${latest.title}" 
                                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" 
                                allowfullscreen>
                        </iframe>
                    </div>
                `;
            } else {
                heroVideoBox.innerHTML = `
                    <div style="background:#020408; border-radius:8px; padding:30px; text-align:center;">
                        <span style="font-family:var(--font-mono); font-size:13px; color:#94a3b8; display:block; margin-bottom:12px;">
                            ⚡ LATEST ALGORITHMIC BROADCAST IN QUEUE
                        </span>
                        <h4 style="color:#ffffff; font-size:18px; margin-bottom:14px;">${latest.title}</h4>
                        <button class="btn-primary-glow btn-sm" onclick="document.getElementById('tab-btn-radar').click()">
                            View Quantitative Radar Analysis →
                        </button>
                    </div>
                `;
            }
        }
    }

    function renderFeedGrid() {
        if (!articlesGrid) return;
        articlesGrid.innerHTML = "";

        const filtered = activeFeedCategory === "all"
            ? allPosts
            : allPosts.filter(p => (p.categories || []).some(c => c.toLowerCase().includes(activeFeedCategory.toLowerCase())));

        if (feedCountBadge) {
            feedCountBadge.textContent = `${filtered.length} Market Report${filtered.length === 1 ? '' : 's'}`;
        }

        filtered.forEach(post => {
            const card = document.createElement("article");
            card.className = "article-card";
            card.innerHTML = `
                <div>
                    <div class="card-top">
                        <span class="card-cat">${(post.categories && post.categories[0]) || "ANALYSIS"}</span>
                        <span class="card-date">${post.date ? post.date.split(" ")[0] : "TODAY"}</span>
                    </div>
                    <h3 class="card-title">${post.title}</h3>
                    <p class="card-excerpt">${post.excerpt}</p>
                </div>
                <div class="card-footer">
                    <span class="read-link">Read Full Analysis →</span>
                    <span style="font-family:var(--font-mono); font-size:11.5px; color:#64748b;">4 min read</span>
                </div>
            `;
            card.addEventListener("click", () => openReaderModal(post));
            articlesGrid.appendChild(card);
        });
    }

    feedCategoryBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            feedCategoryBtns.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            activeFeedCategory = btn.getAttribute("data-category");
            renderFeedGrid();
        });
    });

    // ── 4. Modal Reader View ──
    const modal = document.getElementById("article-modal");
    const modalBackdrop = document.getElementById("modal-backdrop");
    const modalCloseBtn = document.getElementById("modal-close-btn");
    const modalContentBody = document.getElementById("modal-content-body");

    function openReaderModal(post) {
        if (!modal || !modalContentBody) return;
        modalContentBody.innerHTML = `
            <div style="margin-bottom:24px; border-bottom:1px solid var(--border-subtle); padding-bottom:18px;">
                <span style="font-size:11.5px; font-weight:700; color:#3b82f6; font-family:var(--font-mono); text-transform:uppercase; letter-spacing:0.5px;">
                    ${(post.categories || []).join(" • ")}
                </span>
                <h1 style="font-size:28px; line-height:1.3; margin:12px 0 14px 0; color:#ffffff; font-weight:800;">
                    ${post.title}
                </h1>
                <div style="font-size:12px; color:#64748b; font-family:var(--font-mono);">
                    Published by Dalal Street Alpha Desk • ${post.date || "Live"} IST
                </div>
            </div>
            ${post.html || post.excerpt}
        `;
        modal.classList.remove("hidden");
        document.body.style.overflow = "hidden";
    }

    function closeModal() {
        if (!modal) return;
        modal.classList.add("hidden");
        document.body.style.overflow = "";
    }

    if (modalCloseBtn) modalCloseBtn.addEventListener("click", closeModal);
    if (modalBackdrop) modalBackdrop.addEventListener("click", closeModal);
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && modal && !modal.classList.contains("hidden")) {
            closeModal();
        }
    });

    // ── 5. The Trader's Arsenal Category Filter ──
    const arsenalFilterBtns = document.querySelectorAll(".arsenal-filter-bar .filter-btn");
    const arsenalCards = document.querySelectorAll(".arsenal-card");

    arsenalFilterBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            arsenalFilterBtns.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            const filter = btn.getAttribute("data-filter");

            arsenalCards.forEach(card => {
                const category = card.getAttribute("data-category");
                if (filter === "all" || category === filter) {
                    card.style.display = "flex";
                } else {
                    card.style.display = "none";
                }
            });
        });
    });

    // ── 6. Interactive 24-Month RevShare & Kickback Growth Simulator ──
    const sliderNewTraders = document.getElementById("slider-new-traders");
    const valNewTraders = document.getElementById("val-new-traders");

    const sliderBrokerageCut = document.getElementById("slider-brokerage-cut");
    const valBrokerageCut = document.getElementById("val-brokerage-cut");

    const sliderNewSaas = document.getElementById("slider-new-saas");
    const valNewSaas = document.getElementById("val-new-saas");

    const sliderSaasCut = document.getElementById("slider-saas-cut");
    const valSaasCut = document.getElementById("val-saas-cut");

    const sliderChurn = document.getElementById("slider-churn");
    const valChurn = document.getElementById("val-churn");

    const sliderHorizon = document.getElementById("slider-horizon");
    const valHorizon = document.getElementById("val-horizon");

    // Output Elements
    const kpiMonthNum = document.getElementById("kpi-month-num");
    const kpiTotalMonthly = document.getElementById("kpi-total-monthly");
    const kpiActiveTraders = document.getElementById("kpi-active-traders");
    const kpiBrokerMonthly = document.getElementById("kpi-broker-monthly");
    const kpiActiveSaas = document.getElementById("kpi-active-saas");
    const kpiSaasMonthly = document.getElementById("kpi-saas-monthly");
    const kpiCumulativeTotal = document.getElementById("kpi-cumulative-total");
    const kpiCumMonths = document.getElementById("kpi-cum-months");
    const formulaMathDisplay = document.getElementById("formula-math-display");
    const revshareCanvas = document.getElementById("revshare-chart");

    function formatINR(num) {
        return "₹" + Math.round(num).toLocaleString("en-IN");
    }

    function calculateSimulator() {
        const newTraders = parseFloat(sliderNewTraders.value);
        const brokerCut = parseFloat(sliderBrokerageCut.value);
        const newSaas = parseFloat(sliderNewSaas.value);
        const saasCut = parseFloat(sliderSaasCut.value);
        const churnRate = parseFloat(sliderChurn.value) / 100.0;
        const saasChurnRate = churnRate * 0.65; // SaaS retention is typically ~35% higher than active trader churn
        const horizon = parseInt(sliderHorizon.value, 10);

        // Update Slider Label Displays
        valNewTraders.textContent = `${newTraders} traders`;
        valBrokerageCut.textContent = formatINR(brokerCut) + " / mo";
        valNewSaas.textContent = `${newSaas} users`;
        valSaasCut.textContent = formatINR(saasCut) + " / mo";
        valChurn.textContent = `${(churnRate * 100).toFixed(1)}%`;
        valHorizon.textContent = `${horizon} Months`;

        // Monthly Trajectory Arrays for Canvas Graph
        const trajectoryMonths = [];
        const brokerMonthlyList = [];
        const saasMonthlyList = [];
        const totalMonthlyList = [];

        let cumulativeTotal = 0;

        for (let m = 1; m <= horizon; m++) {
            // Formula: Active_Traders(m) = N * [1 - (1 - churn)^m] / churn
            const activeTraders_m = newTraders * (1.0 - Math.pow(1.0 - churnRate, m)) / churnRate;
            const activeSaas_m = newSaas * (1.0 - Math.pow(1.0 - saasChurnRate, m)) / saasChurnRate;

            const brokerCut_m = activeTraders_m * brokerCut;
            const saasCut_m = activeSaas_m * saasCut;
            const totalMonthly_m = brokerCut_m + saasCut_m;

            cumulativeTotal += totalMonthly_m;

            trajectoryMonths.push(m);
            brokerMonthlyList.push(brokerCut_m);
            saasMonthlyList.push(saasCut_m);
            totalMonthlyList.push(totalMonthly_m);
        }

        const finalActiveTraders = newTraders * (1.0 - Math.pow(1.0 - churnRate, horizon)) / churnRate;
        const finalActiveSaas = newSaas * (1.0 - Math.pow(1.0 - saasChurnRate, horizon)) / saasChurnRate;
        const finalBrokerMonthly = finalActiveTraders * brokerCut;
        const finalSaasMonthly = finalActiveSaas * saasCut;
        const finalTotalMonthly = finalBrokerMonthly + finalSaasMonthly;

        // Update Dashboard Elements
        if (kpiMonthNum) kpiMonthNum.textContent = horizon;
        if (kpiTotalMonthly) kpiTotalMonthly.innerHTML = `${formatINR(finalTotalMonthly)} <span class="per-mo">/ month</span>`;
        if (kpiActiveTraders) kpiActiveTraders.textContent = finalActiveTraders.toFixed(1);
        if (kpiBrokerMonthly) kpiBrokerMonthly.textContent = formatINR(finalBrokerMonthly);
        if (kpiActiveSaas) kpiActiveSaas.textContent = finalActiveSaas.toFixed(1);
        if (kpiSaasMonthly) kpiSaasMonthly.textContent = formatINR(finalSaasMonthly);
        if (kpiCumulativeTotal) kpiCumulativeTotal.textContent = formatINR(cumulativeTotal);
        if (kpiCumMonths) kpiCumMonths.textContent = horizon;

        if (formulaMathDisplay) {
            formulaMathDisplay.textContent = 
                `Active Pool = ${newTraders} × [1 - (1 - ${churnRate.toFixed(2)})^${horizon}] / ${churnRate.toFixed(2)} ≈ ${finalActiveTraders.toFixed(1)} Traders`;
        }

        // Draw Canvas Curve
        drawChart(trajectoryMonths, totalMonthlyList, brokerMonthlyList, saasMonthlyList);
    }

    function drawChart(months, total, broker, saas) {
        if (!revshareCanvas) return;
        const ctx = revshareCanvas.getContext("2d");
        const w = revshareCanvas.width;
        const h = revshareCanvas.height;

        ctx.clearRect(0, 0, w, h);

        const paddingLeft = 65;
        const paddingRight = 20;
        const paddingTop = 20;
        const paddingBottom = 35;

        const plotW = w - paddingLeft - paddingRight;
        const plotH = h - paddingTop - paddingBottom;

        const maxVal = Math.max(...total) * 1.15 || 10000;
        const len = months.length;

        // Draw Grid Lines
        ctx.strokeStyle = "rgba(255, 255, 255, 0.06)";
        ctx.lineWidth = 1;
        ctx.beginPath();
        for (let i = 0; i <= 4; i++) {
            const y = paddingTop + (plotH / 4) * i;
            ctx.moveTo(paddingLeft, y);
            ctx.lineTo(w - paddingRight, y);

            // Y-Axis Labels
            const valLabel = Math.round(maxVal - (maxVal / 4) * i);
            ctx.fillStyle = "#64748b";
            ctx.font = "10px JetBrains Mono";
            ctx.textAlign = "right";
            ctx.fillText("₹" + (valLabel >= 1000 ? (valLabel / 1000).toFixed(0) + "k" : valLabel), paddingLeft - 8, y + 3);
        }
        ctx.stroke();

        // X-Axis Labels (Months)
        ctx.fillStyle = "#64748b";
        ctx.textAlign = "center";
        const stepX = plotW / (len - 1);
        for (let i = 0; i < len; i += Math.ceil(len / 6)) {
            const x = paddingLeft + i * stepX;
            ctx.fillText(`M${months[i]}`, x, h - 12);
        }

        // Helper to plot a curve
        function plotLine(data, color, isFill) {
            ctx.strokeStyle = color;
            ctx.lineWidth = 2.5;
            ctx.beginPath();

            for (let i = 0; i < len; i++) {
                const x = paddingLeft + i * stepX;
                const y = paddingTop + plotH - (data[i] / maxVal) * plotH;
                if (i === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            }
            ctx.stroke();

            if (isFill) {
                ctx.lineTo(paddingLeft + (len - 1) * stepX, paddingTop + plotH);
                ctx.lineTo(paddingLeft, paddingTop + plotH);
                ctx.closePath();
                const grad = ctx.createLinearGradient(0, paddingTop, 0, paddingTop + plotH);
                grad.addColorStop(0, "rgba(59, 130, 246, 0.25)");
                grad.addColorStop(1, "rgba(59, 130, 246, 0.0)");
                ctx.fillStyle = grad;
                ctx.fill();
            }
        }

        // Plot Curves: SaaS (Gold), Broker (Cyan), Total (Blue)
        plotLine(saas, "#f59e0b", false);
        plotLine(broker, "#06b6d4", false);
        plotLine(total, "#3b82f6", true);
    }

    [sliderNewTraders, sliderBrokerageCut, sliderNewSaas, sliderSaasCut, sliderChurn, sliderHorizon].forEach(sl => {
        if (sl) sl.addEventListener("input", calculateSimulator);
    });

    calculateSimulator();

    // ── 7. Fee & Slippage Comparison Calculator ──
    const calcSegment = document.getElementById("calc-segment");
    const calcOrdersDay = document.getElementById("calc-orders-day");
    const calcTradingDays = document.getElementById("calc-trading-days");
    const calcTurnover = document.getElementById("calc-turnover");

    const feeResMonthlyBrokerage = document.getElementById("fee-res-monthly-brokerage");
    const feeResMonthlyStt = document.getElementById("fee-res-monthly-stt");
    const feeResMonthlyGst = document.getElementById("fee-res-monthly-gst");
    const feeResMonthlyTotal = document.getElementById("fee-res-monthly-total");
    const feeResAnnualDrain = document.getElementById("fee-res-annual-drain");
    const feeResSavings = document.getElementById("fee-res-savings");

    function calculateFees() {
        if (!calcOrdersDay || !calcTradingDays || !calcTurnover) return;

        const segment = calcSegment.value;
        const ordersDay = parseFloat(calcOrdersDay.value) || 0;
        const tradingDays = parseFloat(calcTradingDays.value) || 0;
        const turnoverPerOrder = parseFloat(calcTurnover.value) || 0;

        const totalOrdersMonth = ordersDay * tradingDays;
        const totalTurnoverMonth = totalOrdersMonth * turnoverPerOrder;

        let brokerage = 0;
        let stt = 0;
        let exchangeAndGst = 0;

        if (segment === "fno_options") {
            // Flat ₹20 per executed order
            brokerage = totalOrdersMonth * 20;
            // STT on sell turnover (0.1% on premium)
            stt = (totalTurnoverMonth * 0.5) * 0.001;
            // Exchange turnover fee (~0.05%) + 18% GST on brokerage & turnover
            const exchTurnover = totalTurnoverMonth * 0.0005;
            const gst = (brokerage + exchTurnover) * 0.18;
            exchangeAndGst = exchTurnover + gst;
        } else if (segment === "fno_futures") {
            brokerage = totalOrdersMonth * 20;
            stt = (totalTurnoverMonth * 0.5) * 0.0002;
            const exchTurnover = totalTurnoverMonth * 0.00019;
            const gst = (brokerage + exchTurnover) * 0.18;
            exchangeAndGst = exchTurnover + gst;
        } else if (segment === "crypto_futures") {
            // 0.05% taker fee
            brokerage = totalTurnoverMonth * 0.0005;
            stt = 0; // No Indian STT on offshore, but TDS
            exchangeAndGst = totalTurnoverMonth * 0.0001;
        } else {
            // Equity Intraday (lower of ₹20 or 0.03%)
            brokerage = Math.min(totalOrdersMonth * 20, totalTurnoverMonth * 0.0003);
            stt = (totalTurnoverMonth * 0.5) * 0.00025;
            const exchTurnover = totalTurnoverMonth * 0.000345;
            const gst = (brokerage + exchTurnover) * 0.18;
            exchangeAndGst = exchTurnover + gst;
        }

        const monthlyTotal = brokerage + stt + exchangeAndGst;
        const annualDrain = monthlyTotal * 12;
        // 10% fee discount on total brokerage costs + cash rebates
        const annualSavings = (brokerage * 12) * 0.10 + (monthlyTotal * 0.04 * 12);

        if (feeResMonthlyBrokerage) feeResMonthlyBrokerage.textContent = formatINR(brokerage);
        if (feeResMonthlyStt) feeResMonthlyStt.textContent = formatINR(stt);
        if (feeResMonthlyGst) feeResMonthlyGst.textContent = formatINR(exchangeAndGst);
        if (feeResMonthlyTotal) feeResMonthlyTotal.textContent = formatINR(monthlyTotal) + " / mo";
        if (feeResAnnualDrain) feeResAnnualDrain.textContent = formatINR(annualDrain) + " / year";
        if (feeResSavings) feeResSavings.textContent = `Save ${formatINR(annualSavings)} / year`;
    }

    [calcSegment, calcOrdersDay, calcTradingDays, calcTurnover].forEach(elem => {
        if (elem) elem.addEventListener("input", calculateFees);
    });

    calculateFees();

    // ── 8. Helper Functions ──
    function extractYouTubeId(url) {
        if (!url) return "dQw4w9WgXcQ";
        const match = url.match(/(?:v=|\/)([0-9A-Za-z_-]{11})/);
        return match ? match[1] : "dQw4w9WgXcQ";
    }

    function getFallbackPosts() {
        return [
            {
                slug: "nifty-market-analysis-live",
                title: "Nifty Today: Bears Tighten Grip as Nifty Cracks Critical Support | Full Analysis & Derivative Setup",
                date: "2026-10-19 12:48:53",
                excerpt: "Live market analysis: Benchmark Nifty 50 settles at 22,888.9 (-1.11%), Sensex at 73,852.9. FII/DII flow breakdown, options chain support levels, and tomorrow's positioning strategy.",
                categories: ["Market Live", "Nifty 50", "Derivatives Analysis"],
                tags: ["Nifty50", "StockMarketToday", "BankNifty"],
                youtubeUrl: "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                html: `
                    <p>Live market breakdown active. Benchmark Nifty 50 settled at 22,888.9 (-1.11%). Options chain open interest concentration outlines key technical inflexion zones heading into upcoming sessions.</p>
                    <h2>1. Benchmark Levels & Session Breath</h2>
                    <p>FII recorded net outflow of -₹1,842 Cr in cash markets, absorbed by DII mutual fund SIP inflows of +₹2,115 Cr.</p>
                    <h2>2. Key Derivative Support & Resistance</h2>
                    <p>Call writing was concentrated heavily at the 23,000 and 23,100 strike contracts, forming an overhead ceiling.</p>
                `
            }
        ];
    }

    // ── 9. Lenis Smooth Scroll Engine ──
    if (typeof Lenis !== "undefined") {
        try {
            const lenis = new Lenis({
                duration: 1.2,
                easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
                orientation: "vertical",
                gestureOrientation: "vertical",
                smoothWheel: true,
                wheelMultiplier: 1.0,
                touchMultiplier: 1.5,
            });
            function raf(time) {
                lenis.raf(time);
                requestAnimationFrame(raf);
            }
            requestAnimationFrame(raf);
        } catch (e) {
            console.debug("Lenis initialized with native scroll fallback");
        }
    }

    // ── 10. Web Audio Synthesizer Haptic Desk Click ──
    let audioEnabled = false;
    let audioCtx = null;
    const audioToggleBtn = document.getElementById("audio-toggle-btn");
    const audioIcon = document.getElementById("audio-icon");
    const audioLabel = document.getElementById("audio-label");

    function playDeskClick() {
        if (!audioEnabled) return;
        try {
            if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            const osc = audioCtx.createOscillator();
            const gain = audioCtx.createGain();
            osc.type = "sine";
            osc.frequency.setValueAtTime(880, audioCtx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(1400, audioCtx.currentTime + 0.035);
            gain.gain.setValueAtTime(0.04, audioCtx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.0001, audioCtx.currentTime + 0.035);
            osc.connect(gain);
            gain.connect(audioCtx.destination);
            osc.start();
            osc.stop(audioCtx.currentTime + 0.04);
        } catch (e) {}
    }

    if (audioToggleBtn) {
        audioToggleBtn.addEventListener("click", () => {
            audioEnabled = !audioEnabled;
            if (audioIcon) audioIcon.textContent = audioEnabled ? "🔊" : "🔈";
            if (audioLabel) audioLabel.textContent = audioEnabled ? "AUDIO: ON" : "AUDIO: OFF";
            if (audioEnabled) playDeskClick();
        });
    }

    document.querySelectorAll("button, a.btn-primary-glow, a.btn-claim-discount, .nav-roll-link").forEach(btn => {
        btn.addEventListener("click", playDeskClick);
    });

    // ── 11. Specular Reactive Border Lighting ──
    const specularCards = document.querySelectorAll(".arsenal-card, .signature-terminal-chassis, .t-stat-card");
    specularCards.forEach(card => {
        card.addEventListener("mousemove", (e) => {
            const rect = card.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            card.style.setProperty("--mouse-x", `${x}px`);
            card.style.setProperty("--mouse-y", `${y}px`);
        });
    });

    // ── 12. Signature Institutional Terminal Engine ──
    const footprintTbody = document.getElementById("footprint-tbody");
    const gexSlider = document.getElementById("gex-slider");
    const gexSimSpot = document.getElementById("gex-sim-spot");
    const gexBarsContainer = document.getElementById("gex-bars-container");
    const tapeStreamBox = document.getElementById("tape-stream-box");
    const termTabFootprint = document.getElementById("term-tab-footprint");
    const termTabGex = document.getElementById("term-tab-gex");
    const termPanelFootprint = document.getElementById("term-panel-footprint");
    const termPanelGex = document.getElementById("term-panel-gex");

    // Tab Switcher
    if (termTabFootprint && termTabGex && termPanelFootprint && termPanelGex) {
        termTabFootprint.addEventListener("click", () => {
            termTabFootprint.classList.add("active");
            termTabGex.classList.remove("active");
            termPanelFootprint.style.display = "block";
            termPanelGex.style.display = "none";
        });
        termTabGex.addEventListener("click", () => {
            termTabGex.classList.add("active");
            termTabFootprint.classList.remove("active");
            termPanelGex.style.display = "block";
            termPanelFootprint.style.display = "none";
            renderGexBars(Number(gexSlider ? gexSlider.value : 22900));
        });
    }

    // Footprint Initial Data
    const footprintStrikes = [
        { strike: 23100, bid: 14200, ask: 6500, tag: "CALL WALL RESISTANCE", type: "selloff" },
        { strike: 23050, bid: 18450, ask: 9200, tag: "HEAVY CALL WRITING", type: "selloff" },
        { strike: 23000, bid: 32100, ask: 14800, tag: "INSTITUTIONAL SUPPLY", type: "selloff" },
        { strike: 22950, bid: 19800, ask: 24500, tag: "TRAPPED SHORTS (BUY DELTA)", type: "absorb" },
        { strike: 22900, bid: 22400, ask: 26100, isSpot: true, tag: "ATM DELTA EQUILIBRIUM", type: "absorb" },
        { strike: 22850, bid: 15600, ask: 28900, tag: "AGGRESSIVE ASK SWEEPS", type: "absorb" },
        { strike: 22800, bid: 12100, ask: 38400, tag: "DII PUT ABSORPTION BED", type: "absorb" },
        { strike: 22750, bid: 8400, ask: 21500, tag: "ACCUMULATION BASE", type: "absorb" },
        { strike: 22700, bid: 5900, ask: 29800, tag: "MAJOR DEALER PUT BED", type: "absorb" }
    ];

    function renderFootprintTable() {
        if (!footprintTbody) return;
        footprintTbody.innerHTML = footprintStrikes.map(row => {
            const delta = row.ask - row.bid;
            const deltaClass = delta >= 0 ? "bull" : "bear";
            const deltaPrefix = delta >= 0 ? "+" : "";
            const rowClass = row.isSpot ? ' class="spot-strike"' : '';
            return `
                <tr${rowClass}>
                    <td class="fp-bid-vol">${row.bid.toLocaleString()}</td>
                    <td class="fp-strike">${row.strike} ${row.isSpot ? '<span style="color:var(--gold-bright); font-size:10px;">[SPOT]</span>' : ''}</td>
                    <td class="fp-ask-vol">${row.ask.toLocaleString()}</td>
                    <td class="fp-delta ${deltaClass}">${deltaPrefix}${delta.toLocaleString()}</td>
                    <td style="text-align:center;">
                        <span class="fp-imbalance-tag ${row.type}">${row.tag}</span>
                    </td>
                </tr>
            `;
        }).join("");
    }

    renderFootprintTable();

    // Footprint Micro Jitter (Simulate Real Tick Flow)
    setInterval(() => {
        const randIndex = Math.floor(Math.random() * footprintStrikes.length);
        const item = footprintStrikes[randIndex];
        const addedQty = Math.floor(Math.random() * 450) + 50;
        if (Math.random() > 0.45) {
            item.ask += addedQty;
        } else {
            item.bid += addedQty;
        }
        renderFootprintTable();
    }, 2800);

    // GEX Simulator
    const gexData = [
        { strike: 22600, callGex: 12, putGex: 88 },
        { strike: 22700, callGex: 20, putGex: 78 },
        { strike: 22800, callGex: 34, putGex: 68 },
        { strike: 22900, callGex: 52, putGex: 50 },
        { strike: 23000, callGex: 84, putGex: 24 },
        { strike: 23100, callGex: 92, putGex: 14 },
        { strike: 23200, callGex: 98, putGex: 8 }
    ];

    function renderGexBars(simSpot) {
        if (!gexBarsContainer) return;
        if (gexSimSpot) gexSimSpot.textContent = Number(simSpot).toLocaleString();

        gexBarsContainer.innerHTML = gexData.map(d => {
            const distance = Math.abs(d.strike - simSpot);
            const isNear = distance <= 50;
            const shiftImpact = (simSpot - 22900) * 0.04;
            const adjustedCall = Math.min(100, Math.max(5, d.callGex + shiftImpact));
            const adjustedPut = Math.min(100, Math.max(5, d.putGex - shiftImpact));

            return `
                <div class="gex-bar-row">
                    <span style="${isNear ? 'color:var(--gold-bright); font-weight:700;' : ''}">${d.strike} ${isNear ? '●' : ''}</span>
                    <div class="gex-bar-track">
                        <div class="gex-bar-fill call-gex" style="width: ${adjustedCall}%;"></div>
                    </div>
                    <span style="text-align:right; color:var(--cyan-accent);">${adjustedCall.toFixed(0)}% GEX</span>
                </div>
            `;
        }).join("");
    }

    if (gexSlider) {
        gexSlider.addEventListener("input", (e) => {
            renderGexBars(Number(e.target.value));
        });
    }

    // High Frequency Institutional Tape Stream
    const tapePool = [
        { contract: "NIFTY 22,900 PE", qty: "12,500 L", price: "₹54.20", type: "buy" },
        { contract: "NIFTY 23,050 CE", qty: "8,200 L", price: "₹31.80", type: "sell" },
        { contract: "BANKNIFTY 49,500 PE", qty: "15,000 L", price: "₹112.40", type: "buy" },
        { contract: "RELIANCE 2680 CE", qty: "6,400 L", price: "₹18.50", type: "buy" },
        { contract: "NIFTY 22,800 PE", qty: "24,000 L", price: "₹28.90", type: "buy" },
        { contract: "HDFCBANK 1640 PE", qty: "9,800 L", price: "₹14.20", type: "sell" },
        { contract: "NIFTY 23,000 CE", qty: "35,000 L", price: "₹44.10", type: "sell" },
        { contract: "BTC 68,500 CALL", qty: "45 BTC", price: "$1,420", type: "buy" },
        { contract: "TCS 4100 CE", qty: "4,200 L", price: "₹38.60", type: "buy" }
    ];

    function addTapePrint() {
        if (!tapeStreamBox) return;
        const print = tapePool[Math.floor(Math.random() * tapePool.length)];
        const now = new Date();
        const timeStr = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}:${String(now.getSeconds()).padStart(2, "0")}.${String(now.getMilliseconds()).padStart(3, "0").slice(0, 2)}`;

        const row = document.createElement("div");
        row.className = `tape-row ${print.type}`;
        row.innerHTML = `
            <span class="tape-time">${timeStr}</span>
            <span class="tape-contract">${print.contract}</span>
            <span class="tape-qty ${print.type}">${print.type === "buy" ? "▲" : "▼"} ${print.qty}</span>
        `;

        tapeStreamBox.insertBefore(row, tapeStreamBox.firstChild);
        if (tapeStreamBox.children.length > 8) {
            tapeStreamBox.removeChild(tapeStreamBox.lastChild);
        }
    }

    for (let i = 0; i < 5; i++) {
        addTapePrint();
    }
    setInterval(addTapePrint, 2200);

    // Initialize content
    loadContent();
});
