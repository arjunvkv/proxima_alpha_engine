/**
 * PROXIMA ALPHA ENGINE — Overview Terminal Frontend
 * Handles SocketIO telemetry for the Overview page only. Every value rendered
 * comes from live telemetry (or SQLite-derived aggregates). No synthetic data.
 */

document.addEventListener('DOMContentLoaded', () => {
    const socket = io();

    // Header Elements
    const liveClock = document.getElementById('liveClock');
    const serverStatusDot = document.getElementById('serverStatusDot');
    const serverStatusText = document.getElementById('serverStatusText');

    // Hero Banner
    const imminentStrategyName = document.getElementById('imminentStrategyName');
    const imminentRegime = document.getElementById('imminentRegime');
    const imminentCountdown = document.getElementById('imminentCountdown');
    const imminentSymbol = document.getElementById('imminentSymbol');
    const imminentDirection = document.getElementById('imminentDirection');
    const imminentConfidenceFill = document.getElementById('imminentConfidenceFill');
    const imminentConfidenceVal = document.getElementById('imminentConfidenceVal');
    const imminentTargetWin = document.getElementById('imminentTargetWin');

    // Market Radar Cards
    const radarTickVelocity = document.getElementById('radarTickVelocity');
    const radarVelocityDesc = document.getElementById('radarVelocityDesc');
    const radarDispersion = document.getElementById('radarDispersion');
    const radarAgreement = document.getElementById('radarAgreement');
    const radarRegime = document.getElementById('radarRegime');
    const radarRegimeDesc = document.getElementById('radarRegimeDesc');

    // Radar Sweep + Equity
    const radarSweep = document.getElementById('radarSweep');
    const radarSweepBlips = document.getElementById('radarSweepBlips');
    const equityCanvas = document.getElementById('equityCanvas');
    const equityChartNow = document.getElementById('equityChartNow');
    const equityChartStart = document.getElementById('equityChartStart');

    // Header + Game HUD
    const accountProfileTitle = document.getElementById('accountProfileTitle');
    const accountProfileMeta = document.getElementById('accountProfileMeta');
    const tickerTrack = document.getElementById('tickerTrack');
    const toastStack = document.getElementById('toastStack');
    const gamePlayerLevel = document.getElementById('gamePlayerLevel');
    const gameXpFill = document.getElementById('gameXpFill');
    const gameXpText = document.getElementById('gameXpText');
    const gameStreakOverall = document.getElementById('gameStreakOverall');
    const gameBadges = document.getElementById('gameBadges');
    const gameTopStrategy = document.getElementById('gameTopStrategy');
    const badgeStrip = document.getElementById('badgeStrip');

    const strategyCardsContainer = document.getElementById('strategyCardsContainer');

    // Real-Time UTC Clock
    setInterval(() => {
        const now = new Date();
        if (liveClock) liveClock.textContent = now.toISOString().substring(11, 19) + ' UTC';
    }, 1000);

    socket.on('connect', () => {
        if (serverStatusDot) serverStatusDot.className = 'status-indicator online';
        if (serverStatusText) serverStatusText.textContent = 'LIVE STREAMING';
    });

    socket.on('disconnect', () => {
        if (serverStatusDot) serverStatusDot.className = 'status-indicator offline';
        if (serverStatusText) serverStatusText.textContent = 'DISCONNECTED';
    });

    socket.on('radar_update', (data) => {
        if (imminentStrategyName) updatePredictiveHero(data.imminent);
        if (radarTickVelocity) updateMarketRadar(data.radar);
        if (radarSweep) updateRadarSweep(data.radar);
        if (strategyCardsContainer) updateStrategyCards(data.predictions);
        if (gamePlayerLevel) updateGameState(data.game);
        if (tickerTrack) updateTicker(data.ticker);
        if (accountProfileTitle) updateAccountProfile(data.config, data.health);
        if (equityCanvas) updateEquityChart(data.performance);
        checkForNewCloses(data.mt5_telemetry);
    });

    function updatePredictiveHero(imm) {
        if (!imm) return;
        imminentStrategyName.textContent = imm.name || '—';
        imminentRegime.textContent = imm.regime || '—';
        imminentCountdown.textContent = imm.countdown_formatted || '—';
        imminentSymbol.textContent = imm.next_symbol || '—';

        imminentDirection.textContent = imm.direction || '—';
        imminentDirection.className = `dir-badge ${(imm.direction || 'x').toLowerCase()}`;

        const conf = imm.confidence !== null && imm.confidence !== undefined ? imm.confidence : null;
        if (conf !== null) {
            imminentConfidenceFill.style.width = `${Math.min(conf, 100)}%`;
            imminentConfidenceVal.textContent = `${conf}%`;
        } else {
            imminentConfidenceFill.style.width = '0%';
            imminentConfidenceVal.textContent = '—';
        }

        if (imm.target_win_usd !== null && imm.target_win_usd !== undefined) {
            const sign = imm.target_win_usd >= 0 ? '+' : '';
            imminentTargetWin.textContent = `${sign}$${imm.target_win_usd.toFixed(2)}`;
        } else {
            imminentTargetWin.textContent = '—';
        }
    }

    function fmtPct(v) {
        return (v !== null && v !== undefined) ? `${v}%` : '—';
    }

    function updateMarketRadar(radar) {
        if (!radar) return;
        const v = radar.tick_velocity_per_sec;
        radarTickVelocity.textContent = (v !== null && v !== undefined) ? v : '—';
        radarVelocityDesc.textContent = radar.regime_description || (v !== null && v !== undefined ? (v > 15 ? 'High Market Activity' : 'Moderate Liquidity Quoting') : 'No live data');
        radarDispersion.textContent = fmtPct(radar.network_dispersion_pct);
        radarAgreement.textContent = fmtPct(radar.directional_agreement_pct);
        radarRegime.textContent = radar.volatility_regime || '—';
        radarRegimeDesc.textContent = radar.real ? radar.regime_description : radar.regime_description || 'Waiting for live MT5 data';
    }

    function updateRadarSweep(radar) {
        if (!radar) return;

        // Remove old blips, keep rings/blade/center
        const blade = radarSweep.querySelector('.radar-sweep-blade');
        radarSweep.querySelectorAll('.radar-blip, .radar-blip-label').forEach((el) => el.remove());

        const blips = radar.blips || [];
        if (blips.length) {
            blips.forEach((b) => {
                const dot = document.createElement('div');
                dot.className = `radar-blip ${b.dir === 'up' ? 'blip-up' : 'blip-down'}`;
                dot.style.left = `${b.x}%`;
                dot.style.top = `${b.y}%`;
                const label = document.createElement('span');
                label.className = 'radar-blip-label';
                label.textContent = b.symbol;
                dot.appendChild(label);
                radarSweep.appendChild(dot);
            });
            radarSweepBlips.textContent = `${blips.length} live symbols tracked`;
        } else {
            radarSweepBlips.textContent = 'No live data';
        }

        if (blade) {
            const v = radar.tick_velocity_per_sec;
            const speed = (v !== null && v !== undefined) ? Math.max(0.5, Math.min(2.0, 60 / Math.max(v, 1))) : 2.0;
            blade.style.animationDuration = `${speed}s`;
        }
    }

    function updateAccountProfile(config, health) {
        if (!config) return;
        const eq = config.account_size || 0;
        accountProfileTitle.textContent = eq ? `$${eq.toLocaleString('en-US', {maximumFractionDigits: 0})} Capital Profile` : 'Capital Profile — waiting';
        const connected = health && health.connected;
        const live = connected ? 'LIVE' : 'OFFLINE';
        const sha = health && health.git_sha && health.git_sha !== 'unknown' ? ` · ${health.git_sha}` : '';
        accountProfileMeta.textContent = `DD Shield: 4.5% Max · ${live}${sha}`;
    }

    function updateGameState(game) {
        if (!game) return;
        gamePlayerLevel.textContent = `LVL ${game.level}`;
        gameXpFill.style.width = `${game.level_progress_pct}%`;
        gameXpText.textContent = `${game.xp} XP · ${game.xp_to_next} to next`;
        gameStreakOverall.textContent = game.streak_overall;
        gameBadges.textContent = `${game.badges_unlocked}/${game.badges_total}`;

        const streaks = game.streaks || {};
        let top = null;
        for (const [name, val] of Object.entries(streaks)) {
            if (!top || val > top.val) top = { name, val };
        }
        gameTopStrategy.textContent = top && top.val > 0 ? `${top.name} ${top.val}🔥` : '—';

        if (badgeStrip && game.badges) {
            badgeStrip.innerHTML = '';
            game.badges.forEach((b) => {
                const chip = document.createElement('div');
                chip.className = `badge-chip ${b.unlocked ? 'unlocked' : 'locked'}`;
                chip.title = `${b.name} — ${b.desc}`;
                chip.innerHTML = `<i class="fa-solid ${b.icon}"></i><span class="badge-tip">${b.name} — ${b.desc}</span>`;
                badgeStrip.appendChild(chip);
            });
        }
    }

    let lastTickerHtml = '';
    function updateTicker(items) {
        if (!items || !items.length) return;
        const html = items.map((it) => {
            if (it.kind === 'TRADE') {
                const cls = it.pnl >= 0 ? 'tick-pnl-pos' : 'tick-pnl-neg';
                const sign = it.pnl >= 0 ? '+' : '';
                return `<span class="ticker-item">${it.side === 'BUY' ? '▲' : '▼'} <span class="tick-sym">${it.symbol}</span> ${it.side} <span class="${cls}">${sign}$${it.pnl.toFixed(2)}</span></span>`;
            }
            if (it.kind === 'SIGNAL') {
                return `<span class="ticker-item">⚡ SIGNAL <span class="tick-sym">${it.symbol}</span> ${it.side} · ${it.strategy || ''}</span>`;
            }
            return `<span class="ticker-item">🛰 ${it.symbol} ${it.strategy || ''}</span>`;
        }).join('');
        const doubled = html + html; // seamless loop (track scrolls -50%)
        if (tickerTrack.innerHTML !== doubled) tickerTrack.innerHTML = doubled;
    }

    let lastClosedTickets = new Set();
    function checkForNewCloses(mt5Data) {
        if (!mt5Data || !mt5Data.trades) return;
        const closed = mt5Data.trades.filter((t) => t.exit_price && t.net_pnl !== undefined && t.net_pnl !== 0);
        if (!closed.length) return;
        const known = new Set(closed.map((t) => `${t.ticket}:${t.net_pnl}`));
        // First payload: seed the set, don't toast
        if (lastClosedTickets.size === 0) {
            lastClosedTickets = known;
            return;
        }
        closed.forEach((t) => {
            const sig = `${t.ticket}:${t.net_pnl}`;
            if (!lastClosedTickets.has(sig)) {
                showToast(t);
            }
        });
        lastClosedTickets = known;
    }

    function showToast(t) {
        if (!toastStack) return;
        const win = t.net_pnl >= 0;
        const toast = document.createElement('div');
        toast.className = `toast ${win ? 'win' : 'loss'}`;
        toast.innerHTML = `
            <div class="toast-title"><i class="fa-solid ${win ? 'fa-trophy' : 'fa-skull'}"></i> ${win ? 'TRADE CLOSED · WIN' : 'TRADE CLOSED · LOSS'}</div>
            <div class="toast-body"><strong>${t.strategy}</strong> ${t.symbol} ${t.type} · <strong class="${win ? 'text-emerald' : 'text-rose'} font-mono">${win ? '+' : ''}$${t.net_pnl.toFixed(2)}</strong> <span class="font-mono">${t.pips >= 0 ? '+' : ''}${t.pips}p</span></div>
        `;
        toastStack.appendChild(toast);
        setTimeout(() => {
            toast.style.animation = 'toastOut 0.3s forwards';
            setTimeout(() => toast.remove(), 350);
        }, 5000);
    }

    let eqChart = null;
    function updateEquityChart(perf) {
        if (!perf || !equityCanvas) return;
        const series = perf.equity_series || [];
        if (series.length < 2) return;

        const now = series[series.length - 1];
        if (equityChartNow) equityChartNow.textContent = `$${now.equity.toLocaleString('en-US', {maximumFractionDigits: 2})}`;
        if (equityChartStart) equityChartStart.textContent = `$${series[0].equity.toLocaleString('en-US', {maximumFractionDigits: 2})}`;

        const dpr = window.devicePixelRatio || 1;
        const rect = equityCanvas.getBoundingClientRect();
        const w = Math.max(rect.width || 600, 300);
        const h = 220;
        if (equityCanvas.width !== w * dpr) { equityCanvas.width = w * dpr; equityCanvas.height = h * dpr; }
        const ctx = equityCanvas.getContext('2d');
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.clearRect(0, 0, w, h);

        const vals = series.map((s) => s.equity);
        const min = Math.min(...vals);
        const max = Math.max(...vals);
        const pad = 10;
        const span = (max - min) || 1;

        const px = (i) => pad + (i / (vals.length - 1)) * (w - pad * 2);
        const py = (v) => pad + (1 - (v - min) / span) * (h - pad * 2);

        // Grid lines
        ctx.strokeStyle = 'rgba(255,255,255,0.05)';
        ctx.lineWidth = 1;
        for (let i = 0; i <= 4; i++) {
            const y = pad + (i / 4) * (h - pad * 2);
            ctx.beginPath(); ctx.moveTo(pad, y); ctx.lineTo(w - pad, y); ctx.stroke();
        }

        // Gradient fill
        const grad = ctx.createLinearGradient(0, 0, 0, h);
        grad.addColorStop(0, 'rgba(16,185,129,0.25)');
        grad.addColorStop(1, 'rgba(16,185,129,0)');

        ctx.beginPath();
        ctx.moveTo(pad, h - pad);
        vals.forEach((v, i) => ctx.lineTo(px(i), py(v)));
        ctx.lineTo(w - pad, h - pad);
        ctx.closePath();
        ctx.fillStyle = grad;
        ctx.fill();

        // Line
        ctx.beginPath();
        vals.forEach((v, i) => { if (i === 0) ctx.moveTo(px(i), py(v)); else ctx.lineTo(px(i), py(v)); });
        ctx.strokeStyle = '#10b981';
        ctx.lineWidth = 2;
        ctx.shadowColor = 'rgba(16,185,129,0.5)';
        ctx.shadowBlur = 8;
        ctx.stroke();
        ctx.shadowBlur = 0;
    }

    function updateStrategyCards(predictions) {
        if (!predictions || !predictions.length) return;

        strategyCardsContainer.innerHTML = '';
        predictions.forEach((st) => {
            const card = document.createElement('div');
            card.className = 'strategy-card';

            const dirClass = (st.direction || 'x').toLowerCase();
            const lot = (st.effective_lot || 0).toFixed(2);
            const targetWin = st.target_win_usd !== null && st.target_win_usd !== undefined ? `+$${st.target_win_usd.toFixed(2)}` : '—';
            const targetLoss = st.target_loss_usd !== null && st.target_loss_usd !== undefined ? `-$${st.target_loss_usd.toFixed(2)}` : '—';
            const perfText = (st.win_rate !== null && st.win_rate !== undefined)
                ? `${st.win_rate}% (PF ${st.profit_factor})`
                : 'NO LIVE CLOSES';

            card.innerHTML = `
                <div class="st-card-top">
                    <div>
                        <div class="st-name">${st.name}</div>
                        <div class="st-type">${st.type}</div>
                    </div>
                    <div class="st-countdown-badge">
                        <i class="fa-solid fa-stopwatch"></i> ${st.countdown_formatted}
                    </div>
                </div>

                <div class="st-card-metrics">
                    <div class="st-m-item">
                        <span class="label">Sizing</span>
                        <span class="val text-emerald">${lot} Lots</span>
                    </div>
                    <div class="st-m-item">
                        <span class="label">Avg Win</span>
                        <span class="val text-emerald">${targetWin}</span>
                    </div>
                    <div class="st-m-item">
                        <span class="label">Avg Loss</span>
                        <span class="val text-rose">${targetLoss}</span>
                    </div>
                </div>

                <div class="st-card-bottom">
                    <div>
                        <span class="meta-label">NEXT SIGNAL TARGET</span>
                        <strong>${st.next_symbol || '—'} <span class="dir-badge ${dirClass}">${st.direction || '—'}</span></strong>
                    </div>
                    <div style="text-align: right;">
                        <span class="meta-label">REAL CLOSED WR</span>
                        <strong class="text-emerald">${perfText}</strong>
                    </div>
                </div>
            `;
            strategyCardsContainer.appendChild(card);
        });
    }
});
