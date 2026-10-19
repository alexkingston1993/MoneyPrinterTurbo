// ==============================================================================
// DALAL STREET ALPHA — APPLICATION SCRIPT
// Dynamically renders live market updates, video embeds, and reader views
// ==============================================================================

document.addEventListener("DOMContentLoaded", () => {
    let allPosts = [];
    let activeCategory = "all";

    // DOM Elements
    const heroTitle = document.getElementById("hero-title");
    const heroExcerpt = document.getElementById("hero-excerpt");
    const heroDate = document.getElementById("hero-date");
    const heroTag = document.getElementById("hero-tag");
    const heroVideoBox = document.getElementById("hero-video-box");
    const heroGeoBox = document.getElementById("hero-geo-box");
    const heroReadBtn = document.getElementById("hero-read-full-btn");
    const articlesGrid = document.getElementById("articles-grid");
    const feedCountBadge = document.getElementById("feed-count-badge");
    const categoryBtns = document.querySelectorAll(".nav-btn");
    const modal = document.getElementById("article-modal");
    const modalBackdrop = document.getElementById("modal-backdrop");
    const modalCloseBtn = document.getElementById("modal-close-btn");
    const modalContentBody = document.getElementById("modal-content-body");
    const marketStatusPill = document.getElementById("market-status-pill");

    // Dynamic Indian Standard Time (IST) Market Hours Check
    function updateMarketStatus() {
        if (!marketStatusPill) return;
        const now = new Date();
        // Convert to IST (UTC + 5:30)
        const utcMs = now.getTime() + (now.getTimezoneOffset() * 60000);
        const istDate = new Date(utcMs + (5.5 * 3600000));
        
        const day = istDate.getDay(); // 0 = Sun, 6 = Sat
        const hours = istDate.getHours();
        const minutes = istDate.getMinutes();
        const totalMinutes = (hours * 60) + minutes;

        const isWeekday = day >= 1 && day <= 5;
        const isOpen = isWeekday && totalMinutes >= (9 * 60 + 15) && totalMinutes <= (15 * 60 + 30);
        const isPreOpen = isWeekday && totalMinutes >= (9 * 60) && totalMinutes < (9 * 60 + 15);

        if (isOpen) {
            marketStatusPill.className = "market-status-pill open";
            marketStatusPill.innerHTML = '<span class="pulse-dot"></span> LIVE TRADING';
        } else if (isPreOpen) {
            marketStatusPill.className = "market-status-pill open";
            marketStatusPill.style.color = "#f59e0b";
            marketStatusPill.style.borderColor = "rgba(245, 158, 11, 0.4)";
            marketStatusPill.innerHTML = '<span class="pulse-dot"></span> PRE-OPEN SESSION';
        } else {
            marketStatusPill.className = "market-status-pill closed";
            marketStatusPill.innerHTML = '<span class="pulse-dot"></span> MARKET CLOSED';
        }
    }

    // Fetch and load posts
    async function loadPosts() {
        updateMarketStatus();
        try {
            const resp = await fetch("content/posts.json");
            if (resp.ok) {
                allPosts = await resp.json();
            } else {
                console.warn("content/posts.json not found, using embedded post");
                allPosts = getFallbackPosts();
            }
        } catch (e) {
            console.warn("Failed to fetch posts.json, fallback:", e);
            allPosts = getFallbackPosts();
        }

        renderApp();
    }

    function renderApp() {
        if (!allPosts || allPosts.length === 0) return;

        // 1. Render Hero with Latest Post
        const latest = allPosts[0];
        heroTitle.textContent = latest.title;
        heroExcerpt.textContent = latest.excerpt;
        heroDate.textContent = `Published: ${latest.date} IST`;
        heroTag.textContent = (latest.categories && latest.categories[0]) ? latest.categories[0].toUpperCase() : "MARKET ANALYSIS";

        // Embed YouTube Video in Hero or render Algorithmic Radar Card
        const hasRealVideo = latest.youtubeUrl && !latest.youtubeUrl.includes("dQw4w9WgXcQ");
        if (hasRealVideo) {
            const videoId = extractYouTubeId(latest.youtubeUrl);
            heroVideoBox.innerHTML = `
                <div class="yt-embed-wrapper">
                    <iframe src="https://www.youtube.com/embed/${videoId}?rel=0" 
                            title="${latest.title}" 
                            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" 
                            allowfullscreen>
                    </iframe>
                </div>
            `;
            heroVideoBox.style.display = "block";
        } else {
            heroVideoBox.innerHTML = `
                <div class="market-chart-hero-placeholder">
                    <div class="radar-header">
                        <div class="radar-badge">
                            <span class="pulse-dot"></span>
                            <span>ALGORITHMIC RADAR • 5 DAILY CLOUD CYCLES ACTIVE</span>
                        </div>
                        <span style="font-family:var(--font-mono); font-size:12px; color:var(--text-muted);">
                            Google AI Studio (Gemini 3.8 Flash)
                        </span>
                    </div>
                    <div class="terminal-stats-grid">
                        <div class="t-stat-card">
                            <span class="t-label">NIFTY 50</span>
                            <span class="t-val bear">22,888.9 (-1.11%)</span>
                        </div>
                        <div class="t-stat-card">
                            <span class="t-label">SENSEX</span>
                            <span class="t-val bear">73,852.9 (-1.08%)</span>
                        </div>
                        <div class="t-stat-card">
                            <span class="t-label">BANK NIFTY</span>
                            <span class="t-val bear">49,425.2 (-0.95%)</span>
                        </div>
                        <div class="t-stat-card">
                            <span class="t-label">INDIA VIX</span>
                            <span class="t-val bull">15.42 (+4.2%)</span>
                        </div>
                    </div>
                </div>
            `;
            heroVideoBox.style.display = "block";
        }

        // Hero GEO Quick Takeaway Box
        heroGeoBox.innerHTML = `
            <h3>⚡ Executive Summary (AI Overview & Perplexity Direct Answer)</h3>
            <p>${latest.excerpt}</p>
        `;

        heroReadBtn.onclick = () => openReaderModal(latest);

        // 2. Render Feed Grid
        renderGrid();
    }

    function renderGrid() {
        articlesGrid.innerHTML = "";
        
        const filtered = activeCategory === "all" 
            ? allPosts 
            : allPosts.filter(p => (p.categories || []).some(c => c.toLowerCase().includes(activeCategory.toLowerCase())));

        feedCountBadge.textContent = `${filtered.length} Market Report${filtered.length === 1 ? '' : 's'}`;

        filtered.forEach((post) => {
            const card = document.createElement("article");
            card.className = "article-card";
            card.innerHTML = `
                <div>
                    <div class="card-top">
                        <span class="card-cat">${(post.categories && post.categories[0]) || "ANALYSIS"}</span>
                        <span class="card-date">${post.date.split(" ")[0]}</span>
                    </div>
                    <h3 class="card-title">${post.title}</h3>
                    <p class="card-excerpt">${post.excerpt}</p>
                </div>
                <div class="card-footer">
                    <span class="read-link">Read Analysis →</span>
                    <span style="font-size:12px; color:#64748b;">4 min read</span>
                </div>
            `;
            card.addEventListener("click", () => openReaderModal(post));
            articlesGrid.appendChild(card);
        });
    }

    // Modal Reader View
    function openReaderModal(post) {
        modalContentBody.innerHTML = `
            <div style="margin-bottom:20px;">
                <span style="font-size:11px; font-weight:700; color:#3b82f6; font-family:var(--font-mono); text-transform:uppercase;">
                    ${(post.categories || []).join(" • ")}
                </span>
                <h1 style="font-size:28px; line-height:1.3; margin:10px 0 14px 0; color:#ffffff;">${post.title}</h1>
                <div style="font-size:12px; color:#64748b; font-family:var(--font-mono);">
                    Published by Dalal Street Alpha Desk • ${post.date} IST
                </div>
            </div>
            ${post.html || post.excerpt}
        `;
        modal.classList.remove("hidden");
        document.body.style.overflow = "hidden";
    }

    function closeModal() {
        modal.classList.add("hidden");
        document.body.style.overflow = "";
    }

    modalCloseBtn.addEventListener("click", closeModal);
    modalBackdrop.addEventListener("click", closeModal);

    // Category Tabs
    categoryBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            categoryBtns.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            activeCategory = btn.getAttribute("data-category");
            renderGrid();
        });
    });

    // YouTube ID Helper
    function extractYouTubeId(url) {
        const match = url.match(/(?:v=|\/)([0-9A-Za-z_-]{11})/);
        return match ? match[1] : "dQw4w9WgXcQ";
    }

    // Fallback Initial Post
    function getFallbackPosts() {
        return [
            {
                slug: "nifty-market-analysis-live",
                title: "Nifty Today: Bears Tighten Grip as Nifty Cracks Critical Support | Full Analysis & Derivative Setup",
                date: "2026-10-19 12:07:51",
                excerpt: "Live market analysis: Nifty closes at 22,888.9 (-1.11%), Sensex at 73,852.9. FII/DII flow breakdown, options chain support levels, and tomorrow's strategy.",
                categories: ["Market Live", "Nifty 50", "Derivatives Analysis"],
                tags: ["Nifty50", "StockMarketToday", "BankNifty"],
                youtubeUrl: "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                html: "<p>Live market breakdown active. Benchmark Nifty 50 settled at 22,888.9 (-1.11%). Options chain open interest concentration outlines key technical inflexion zones heading into the upcoming sessions.</p>"
            }
        ];
    }

    // Initialize
    loadPosts();
});
