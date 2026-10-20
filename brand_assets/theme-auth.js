// The Bull Print - Global Theme Switcher & Google Auth / Watchlist Controller
// Theme default: LIGHT MODE (as specified by user requirement)

(function() {
    // 1. Immediate Theme Application (prevents flash of dark/light theme)
    const savedTheme = localStorage.getItem('dsa_theme') || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);

    // 2. Auth State Management
    window.DSA_AUTH = {
        getUser: function() {
            try {
                return JSON.parse(localStorage.getItem('dsa_user')) || null;
            } catch (e) {
                return null;
            }
        },
        setUser: function(userData) {
            localStorage.setItem('dsa_user', JSON.stringify(userData));
            window.dispatchEvent(new CustomEvent('dsa-auth-changed', { detail: userData }));
        },
        logout: function() {
            localStorage.removeItem('dsa_user');
            window.dispatchEvent(new CustomEvent('dsa-auth-changed', { detail: null }));
        },
        getShortlist: function() {
            try {
                return JSON.parse(localStorage.getItem('dsa_shortlist')) || ["ITC", "PCJEWELLER", "TCS"];
            } catch (e) {
                return ["ITC", "PCJEWELLER", "TCS"];
            }
        },
        toggleShortlist: function(symbol) {
            const clean = symbol.trim().toUpperCase().replace(/\s+/g, '');
            let list = this.getShortlist();
            const index = list.indexOf(clean);
            let added = false;
            if (index > -1) {
                list.splice(index, 1);
            } else {
                list.push(clean);
                added = true;
            }
            localStorage.setItem('dsa_shortlist', JSON.stringify(list));
            window.dispatchEvent(new CustomEvent('dsa-shortlist-changed', { detail: { symbol: clean, added, list } }));
            return { added, list };
        },
        isShortlisted: function(symbol) {
            const clean = symbol.trim().toUpperCase().replace(/\s+/g, '');
            return this.getShortlist().includes(clean);
        }
    };

    // 3. Theme Toggle Function
    window.toggleDSATheme = function() {
        const current = document.documentElement.getAttribute('data-theme') || 'light';
        const next = current === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', next);
        localStorage.setItem('dsa_theme', next);
        updateThemeToggleIcons(next);
    };

    function updateThemeToggleIcons(theme) {
        const btns = document.querySelectorAll('.theme-toggle-btn');
        btns.forEach(b => {
            if (theme === 'dark') {
                b.innerHTML = '☀️ <span class="theme-text">Light</span>';
                b.setAttribute('title', 'Switch to Light Mode');
            } else {
                b.innerHTML = '🌙 <span class="theme-text">Dark</span>';
                b.setAttribute('title', 'Switch to Dark Mode');
            }
        });
    }

    // 4. Google Auth Modal Injection
    window.openGoogleAuthModal = function(callback) {
        let modal = document.getElementById('google-auth-modal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'google-auth-modal';
            modal.innerHTML = `
                <div class="g-modal-backdrop" onclick="closeGoogleAuthModal()"></div>
                <div class="g-modal-content">
                    <button class="g-modal-close" onclick="closeGoogleAuthModal()">✕</button>
                    <div class="g-modal-header">
                        <svg class="google-logo" viewBox="0 0 24 24" width="24" height="24">
                            <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                            <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                            <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"/>
                            <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"/>
                        </svg>
                        <h3>Sign in with Google</h3>
                        <p>Sign in with your Gmail to save shortlists, connect multiple broker portfolios, and run institutional AI portfolio health audits.</p>
                    </div>
                    <div class="g-account-list">
                        <div class="g-account-item" onclick="selectDemoAccount('arjun.dalal@gmail.com', 'Arjun Sharma', 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=100&auto=format&fit=crop&q=80')">
                            <img src="https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=100&auto=format&fit=crop&q=80" alt="Arjun Avatar" class="g-account-avatar">
                            <div>
                                <div class="g-account-name">Arjun Sharma</div>
                                <div class="g-account-email">arjun.dalal@gmail.com</div>
                            </div>
                        </div>
                        <div class="g-account-item" onclick="selectDemoAccount('vikram.equity@gmail.com', 'Vikram Mehta', 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=100&auto=format&fit=crop&q=80')">
                            <img src="https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=100&auto=format&fit=crop&q=80" alt="Vikram Avatar" class="g-account-avatar">
                            <div>
                                <div class="g-account-name">Vikram Mehta</div>
                                <div class="g-account-email">vikram.equity@gmail.com</div>
                            </div>
                        </div>
                    </div>
                    <div style="margin: 16px 0; text-align: center; font-size: 12px; color: var(--text-muted);">OR SIGN IN WITH CUSTOM GMAIL</div>
                    <form onsubmit="handleCustomEmailLogin(event)" style="display:flex; flex-direction:column; gap:10px;">
                        <input type="email" id="custom-gmail-input" placeholder="Enter your Gmail address..." required class="g-email-input">
                        <button type="submit" class="g-submit-btn">Continue with Gmail</button>
                    </form>
                    <div class="g-modal-disclaimer">
                        By continuing, you agree to The Bull Print's Educational Terms & Privacy Policy.
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
        }
        modal.style.display = 'flex';
        window._authCallback = callback;
    };

    window.closeGoogleAuthModal = function() {
        const modal = document.getElementById('google-auth-modal');
        if (modal) modal.style.display = 'none';
    };

    window.selectDemoAccount = function(email, name, picture) {
        const user = { email, name, picture, loggedInAt: new Date().toISOString() };
        DSA_AUTH.setUser(user);
        closeGoogleAuthModal();
        if (typeof window._authCallback === 'function') {
            window._authCallback(user);
        }
        showToast(`Signed in as ${name} (${email})`);
    };

    window.handleCustomEmailLogin = function(e) {
        e.preventDefault();
        const input = document.getElementById('custom-gmail-input');
        const email = input.value.trim();
        if (email) {
            const name = email.split('@')[0].replace(/[._]/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
            const picture = 'https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?w=100&auto=format&fit=crop&q=80';
            selectDemoAccount(email, name, picture);
        }
    };

    window.showToast = function(msg) {
        let toast = document.getElementById('dsa-toast');
        if (!toast) {
            toast = document.createElement('div');
            toast.id = 'dsa-toast';
            document.body.appendChild(toast);
        }
        toast.textContent = msg;
        toast.className = 'dsa-toast show';
        setTimeout(() => {
            toast.className = 'dsa-toast';
        }, 3000);
    };

    // 5. Setup Watchlist Drawer
    window.toggleWatchlistDrawer = function() {
        let drawer = document.getElementById('watchlist-drawer');
        if (!drawer) {
            drawer = document.createElement('div');
            drawer.id = 'watchlist-drawer';
            drawer.innerHTML = `
                <div class="drawer-backdrop" onclick="toggleWatchlistDrawer()"></div>
                <div class="drawer-content">
                    <div class="drawer-header">
                        <h3>⭐ My Shortlisted Stocks</h3>
                        <button onclick="toggleWatchlistDrawer()" class="drawer-close">✕</button>
                    </div>
                    <div id="drawer-shortlist-items" class="drawer-list"></div>
                    <div class="drawer-footer">
                        <a href="/portfolio.html" class="drawer-portfolio-btn">📊 View Multi-Broker Portfolio & AI Health</a>
                    </div>
                </div>
            `;
            document.body.appendChild(drawer);
        }
        const isOpen = drawer.classList.contains('open');
        if (isOpen) {
            drawer.classList.remove('open');
        } else {
            renderDrawerShortlist();
            drawer.classList.add('open');
        }
    };

    function renderDrawerShortlist() {
        const container = document.getElementById('drawer-shortlist-items');
        if (!container) return;
        const list = DSA_AUTH.getShortlist();
        if (list.length === 0) {
            container.innerHTML = `<div style="text-align:center; padding:30px; color:var(--text-muted); font-size:13px;">No stocks shortlisted yet.<br>Click "⭐ Shortlist" on any stock page to save it here.</div>`;
            return;
        }
        container.innerHTML = list.map(sym => `
            <div class="drawer-item" onclick="window.location.href='/stock.html?symbol=${sym}'">
                <div>
                    <strong>${sym}</strong>
                    <div style="font-size:11px; color:var(--text-muted);">NSE Equity</div>
                </div>
                <div style="display:flex; align-items:center; gap:10px;">
                    <button onclick="event.stopPropagation(); DSA_AUTH.toggleShortlist('${sym}'); renderDrawerShortlist();" class="remove-btn" title="Remove">✕</button>
                    <span style="color:var(--groww-mint); font-weight:700;">→</span>
                </div>
            </div>
        `).join('');
    }

    // ==============================================================================
    // 6. PORTFOLIO STOCK EVENTS ALERT NOTIFICATION ENGINE
    // Rule: Alert once 7 days before event. Once per day during the final 3 days.
    // ==============================================================================
    const UPCOMING_STOCK_EVENTS = [
        {
            id: "ev-itc-q2",
            symbol: "ITC",
            company: "ITC Ltd",
            type: "earnings",
            title: "Q2 FY25 Financial Results & Board Meeting",
            date: "2026-10-24", // 4 days away
            details: "Board of Directors to consider unaudited standalone and consolidated Q2 financial results and interim dividend."
        },
        {
            id: "ev-reliance-div",
            symbol: "RELIANCE",
            company: "Reliance Industries",
            type: "dividend",
            title: "Interim Dividend Ex-Date (₹10.00 / share)",
            date: "2026-10-23", // 3 days away (Triggers final 3 days rule!)
            details: "Ex-dividend date for interim dividend of ₹10.00 per equity share. Record date Oct 24."
        },
        {
            id: "ev-tcs-board",
            symbol: "TCS",
            company: "Tata Consultancy Services",
            type: "board",
            title: "Board Strategy & AI Investment Meet",
            date: "2026-10-27", // Exact 7 days away! (Triggers 7-day rule!)
            details: "Strategic review of generative AI enterprise deployments and North American deal pipeline."
        },
        {
            id: "ev-hdfc-q2",
            symbol: "HDFCBANK",
            company: "HDFC Bank Ltd",
            type: "earnings",
            title: "Q2 Earnings & Net Interest Margin Review",
            date: "2026-10-28",
            details: "Consolidated Q2 earnings announcement and investor conference call."
        },
        {
            id: "ev-pcjeweller-split",
            symbol: "PCJEWELLER",
            company: "PC Jeweller Ltd",
            type: "split",
            title: "Sub-Division of Equity Shares (1:10 Split)",
            date: "2026-10-31",
            details: "Record date for 1:10 stock split sub-division from face value ₹10 to ₹1."
        },
        {
            id: "ev-trent-q2",
            symbol: "TRENT",
            company: "Trent Ltd",
            type: "earnings",
            title: "Q2 Retail Financial Results Announcement",
            date: "2026-11-04",
            details: "Zudio & Westside standalone revenue metrics and festive store expansion update."
        }
    ];

    function getMonitoredSymbols() {
        const symbols = new Set();
        try {
            const holdings = JSON.parse(localStorage.getItem('dsa_portfolio_holdings'));
            if (Array.isArray(holdings) && holdings.length > 0) {
                holdings.forEach(h => { if (h.symbol) symbols.add(h.symbol.toUpperCase()); });
            }
        } catch (e) {}

        const shortlist = DSA_AUTH.getShortlist();
        shortlist.forEach(s => symbols.add(s.toUpperCase()));

        // Default fallback to ensure user always sees the institutional experience
        if (symbols.size === 0) {
            ["ITC", "RELIANCE", "TCS", "HDFCBANK", "PCJEWELLER"].forEach(s => symbols.add(s));
        }
        return Array.from(symbols);
    }

    function getActivePortfolioEvents() {
        const monitored = getMonitoredSymbols();
        const today = new Date("2026-10-20T00:00:00");

        return UPCOMING_STOCK_EVENTS.filter(ev => {
            if (!monitored.includes(ev.symbol)) return false;
            const evDate = new Date(ev.date + "T00:00:00");
            const diffDays = Math.ceil((evDate - today) / (1000 * 60 * 60 * 24));
            return diffDays >= 0 && diffDays <= 30; // Upcoming within 30 days
        }).map(ev => {
            const evDate = new Date(ev.date + "T00:00:00");
            const diffDays = Math.ceil((evDate - today) / (1000 * 60 * 60 * 24));
            return { ...ev, diffDays };
        }).sort((a, b) => a.diffDays - b.diffDays);
    }

    function checkPortfolioStockEvents() {
        const events = getActivePortfolioEvents();
        const todayStr = "2026-10-20";
        let sentLog = {};
        try {
            sentLog = JSON.parse(localStorage.getItem('dsa_event_notifications_sent')) || {};
        } catch (e) {
            sentLog = {};
        }

        // Check 7-day rule and final 3-day rule
        for (const ev of events) {
            let shouldAlert = false;
            let reason = "";

            if (ev.diffDays === 7) {
                // Exact 7 days rule: Once only
                const key = `${ev.id}_7d`;
                if (!sentLog[key]) {
                    shouldAlert = true;
                    reason = "Upcoming in 7 Days";
                    sentLog[key] = todayStr;
                }
            } else if (ev.diffDays <= 3 && ev.diffDays >= 0) {
                // Final 3 days rule: Once every day
                const key = `${ev.id}_day_${todayStr}`;
                if (!sentLog[key]) {
                    shouldAlert = true;
                    reason = ev.diffDays === 0 ? "Event is Today!" : (ev.diffDays === 1 ? "Tomorrow!" : `${ev.diffDays} Days Remaining`);
                    sentLog[key] = todayStr;
                }
            }

            if (shouldAlert) {
                localStorage.setItem('dsa_event_notifications_sent', JSON.stringify(sentLog));
                setTimeout(() => {
                    showEventNotificationPopup(ev, ev.diffDays, reason);
                }, 1200);
                break; // Show top priority alert first to prevent spamming
            }
        }
    }

    function showEventNotificationPopup(event, diffDays, reason) {
        let popup = document.getElementById('dsa-event-alert-popup');
        if (!popup) {
            popup = document.createElement('div');
            popup.id = 'dsa-event-alert-popup';
            popup.className = 'dsa-event-alert-popup';
            document.body.appendChild(popup);
        }

        const calDate = event.date.replace(/-/g, '');
        const calUrl = `https://calendar.google.com/calendar/render?action=TEMPLATE&text=${encodeURIComponent(event.company + ' - ' + event.title)}&dates=${calDate}T090000Z/${calDate}T170000Z&details=${encodeURIComponent(event.details + '\n\nTracked via The Bull Print')}`;

        popup.innerHTML = `
            <div class="dsa-alert-pop-header">
                <span class="dsa-alert-badge-tag ${event.type}">${event.symbol} • ${event.type.toUpperCase()}</span>
                <span class="dsa-alert-days-pill">⏰ ${reason}</span>
            </div>
            <div class="dsa-alert-pop-title">${event.title}</div>
            <div class="dsa-alert-pop-desc">${event.details}</div>
            <div class="dsa-alert-pop-actions">
                <button class="dsa-alert-btn-dismiss" onclick="dismissEventNotificationPopup()">Dismiss</button>
                <a href="${calUrl}" target="_blank" rel="noopener" class="dsa-alert-btn-cal">📅 Google Cal</a>
                <a href="/events.html" class="dsa-alert-btn-view">View Details →</a>
            </div>
        `;

        popup.classList.add('show');

        // Auto dismiss after 10 seconds if not clicked
        setTimeout(() => {
            if (popup.classList.contains('show')) {
                popup.classList.remove('show');
            }
        }, 12000);
    }

    window.dismissEventNotificationPopup = function() {
        const popup = document.getElementById('dsa-event-alert-popup');
        if (popup) popup.classList.remove('show');
    };

    window.toggleAlertDropdown = function() {
        const panel = document.getElementById('alert-dropdown-panel');
        if (!panel) return;
        panel.classList.toggle('show');
    };

    // 7. Update Navbar Profile & Theme icons on load
    document.addEventListener('DOMContentLoaded', function() {
        updateThemeToggleIcons(document.documentElement.getAttribute('data-theme') || 'light');
        renderNavAuthSection();
        checkPortfolioStockEvents();

        window.addEventListener('dsa-auth-changed', () => {
            renderNavAuthSection();
            checkPortfolioStockEvents();
        });
        window.addEventListener('dsa-shortlist-changed', () => {
            renderNavAuthSection();
            checkPortfolioStockEvents();
        });
    });

    function renderNavAuthSection() {
        const authWrappers = document.querySelectorAll('.nav-auth-wrapper');
        const user = DSA_AUTH.getUser();
        const shortlist = DSA_AUTH.getShortlist();
        const activeEvents = getActivePortfolioEvents();

        authWrappers.forEach(w => {
            const alertBellHtml = `
                <div class="nav-alert-wrapper">
                    <button class="nav-alert-btn" onclick="toggleAlertDropdown()" title="Portfolio Stock Events (${activeEvents.length})">
                        🔔
                        ${activeEvents.length > 0 ? `<span class="nav-alert-badge">${activeEvents.length}</span>` : ''}
                    </button>
                    <div class="alert-dropdown-panel" id="alert-dropdown-panel">
                        <div class="alert-panel-header">
                            <span class="alert-panel-title">🔔 Portfolio Event Alerts</span>
                            <span style="font-size:11px; font-family:'JetBrains Mono'; color:var(--groww-mint); font-weight:700;">${activeEvents.length} UPCOMING</span>
                        </div>
                        <div class="alert-panel-list">
                            ${activeEvents.length === 0 ? `
                                <div style="text-align:center; padding:24px; color:var(--text-muted); font-size:12px;">No events in next 30 days for linked stocks.</div>
                            ` : activeEvents.map(ev => `
                                <a href="/events.html" class="alert-item">
                                    <div class="alert-icon-box ${ev.type}">
                                        ${ev.type === 'earnings' ? '📊' : (ev.type === 'dividend' ? '💰' : (ev.type === 'split' ? '✂️' : '🏛️'))}
                                    </div>
                                    <div style="flex:1;">
                                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:2px;">
                                            <strong style="font-size:13px; color:var(--text-primary);">${ev.symbol}</strong>
                                            <span style="font-size:10.5px; font-weight:700; color:${ev.diffDays <= 3 ? 'var(--market-red)' : 'var(--groww-mint)'}; font-family:'JetBrains Mono';">
                                                ${ev.diffDays === 0 ? 'TODAY' : `${ev.diffDays}d away`}
                                            </span>
                                        </div>
                                        <div style="font-size:12px; color:var(--text-secondary); line-height:1.4;">${ev.title}</div>
                                        <div style="font-size:10.5px; color:var(--text-muted); margin-top:2px;">${ev.date}</div>
                                    </div>
                                </a>
                            `).join('')}
                        </div>
                        <div style="padding:10px; background:var(--bg-card-subtle); border-top:1px solid var(--border-subtle); text-align:center;">
                            <a href="/events.html" style="font-size:11.5px; font-weight:700; color:var(--groww-mint); text-decoration:none;">View All Corporate Actions Calendar →</a>
                        </div>
                    </div>
                </div>
            `;

            if (user) {
                w.innerHTML = `
                    ${alertBellHtml}
                    <button class="nav-shortlist-btn" onclick="toggleWatchlistDrawer()" title="View Shortlist">
                        ⭐ <span class="shortlist-count">${shortlist.length}</span>
                    </button>
                    <div class="user-pill-dropdown">
                        <div class="user-pill" onclick="toggleUserDropdown(this)">
                            <img src="${user.picture}" alt="Avatar" class="user-avatar-mini">
                            <span class="user-name-short">${user.name.split(' ')[0]}</span>
                            <span style="font-size:10px; opacity:0.6;">▼</span>
                        </div>
                        <div class="user-menu-dropdown">
                            <div class="user-menu-header">
                                <div style="font-weight:700;">${user.name}</div>
                                <div style="font-size:11px; color:var(--text-muted);">${user.email}</div>
                            </div>
                            <a href="/portfolio.html" class="user-menu-item">💼 Multi-Broker Portfolio</a>
                            <div class="user-menu-item" onclick="toggleWatchlistDrawer()">⭐ Shortlist (${shortlist.length})</div>
                            <a href="/events.html" class="user-menu-item">📅 Stock Events Radar</a>
                            <div class="user-menu-item" onclick="DSA_AUTH.logout(); showToast('Signed out successfully');">🚪 Sign Out</div>
                        </div>
                    </div>
                `;
            } else {
                w.innerHTML = `
                    ${alertBellHtml}
                    <button class="nav-login-btn" onclick="openGoogleAuthModal()">
                        <svg viewBox="0 0 24 24" width="14" height="14" style="vertical-align:middle; margin-right:4px;">
                            <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                            <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                            <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"/>
                            <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"/>
                        </svg>
                        Sign in
                    </button>
                `;
            }
        });
    }

    window.toggleUserDropdown = function(el) {
        const menu = el.nextElementSibling;
        if (menu) {
            menu.classList.toggle('show');
        }
    };

    document.addEventListener('click', function(e) {
        if (!e.target.closest('.user-pill-dropdown')) {
            document.querySelectorAll('.user-menu-dropdown.show').forEach(m => m.classList.remove('show'));
        }
        if (!e.target.closest('.nav-alert-wrapper')) {
            const panel = document.getElementById('alert-dropdown-panel');
            if (panel) panel.classList.remove('show');
        }
    });

})();
