/**
 * PROXIMA X — PREDICTIVE MULTI-PAGE TERMINAL FRONTEND ENGINE
 * Handles SocketIO telemetry for Overview, Diagnostics, VPS Logs, Analytics, 2H Rolling Backtests, and Yesterday Summary
 */

document.addEventListener('DOMContentLoaded', () => {
    console.log("🚀 Proxima X Multi-Page Terminal Engine initialized...");

    const socket = io();

    // Universal Header Elements
    const liveClock = document.getElementById('liveClock');
    const serverStatusDot = document.getElementById('serverStatusDot');
    const serverStatusText = document.getElementById('serverStatusText');

    // Page 1: Overview Elements
    const imminentStrategyName = document.getElementById('imminentStrategyName');
    const imminentRegime = document.getElementById('imminentRegime');
    const imminentCountdown = document.getElementById('imminentCountdown');
    const imminentSymbol = document.getElementById('imminentSymbol');
    const imminentDirection = document.getElementById('imminentDirection');
    const imminentConfidenceFill = document.getElementById('imminentConfidenceFill');
    const imminentConfidenceVal = document.getElementById('imminentConfidenceVal');
    const imminentTargetWin = document.getElementById('imminentTargetWin');

    const radarTickVelocity = document.getElementById('radarTickVelocity');
    const radarVelocityDesc = document.getElementById('radarVelocityDesc');
    const radarDispersion = document.getElementById('radarDispersion');
    const radarAgreement = document.getElementById('radarAgreement');
    const radarRegime = document.getElementById('radarRegime');
    const radarRegimeDesc = document.getElementById('radarRegimeDesc');

    const radarSweepRegime = document.getElementById('radarSweepRegime');
    const radarSweepVelocity = document.getElementById('radarSweepVelocity');

    const accountProfileTitle = document.getElementById('accountProfileTitle');
    const accountProfileMeta = document.getElementById('accountProfileMeta');

    const equityCanvas = document.getElementById('equityCanvas');
    const equityChartNow = document.getElementById('equityChartNow');
    const equityChartStart = document.getElementById('equityChartStart');

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
    const auditTableBody = document.getElementById('auditTableBody');

    // Page 2: Diagnostics Elements
    const diagnosticsGrid = document.getElementById('diagnosticsGrid');

    // Page 3: VPS Log Console Elements
    const consoleLogBody = document.getElementById('consoleLogBody');

    // Page 4: Analytics Elements
    const exposureTableBody = document.getElementById('exposureTableBody');

    // Page 5: 2H Rolling Backtest Elements
    const todayLiveWinRate = document.getElementById('todayLiveWinRate');
    const todayLivePnl = document.getElementById('todayLivePnl');
    const rbWinRate = document.getElementById('rbWinRate');
    const rbTradeCounts = document.getElementById('rbTradeCounts');
    const rbProfitFactor = document.getElementById('rbProfitFactor');
    const rbNextRun = document.getElementById('rbNextRun');
    const rbLastRunTime = document.getElementById('rbLastRunTime');
    const vpsLiveTradesTableBody = document.getElementById('vpsLiveTradesTableBody');
    const rollingBacktestTableBody = document.getElementById('rollingBacktestTableBody');

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
        if (strategyCardsContainer) updateStrategyCards(data.predictions);
        if (auditTableBody) updateAuditTable(data.mt5_telemetry);
        if (vpsLiveTradesTableBody) updateVPSLiveTable(data.mt5_telemetry);
        if (diagnosticsGrid) updateDiagnostics(data.diagnostics);
        if (consoleLogBody) updateVPSLogs(data.vps_logs);
        if (exposureTableBody) updateExposureTable(data.exposure);
        if (rollingBacktestTableBody) updateRollingBacktest(data.rolling_backtest);
        if (gamePlayerLevel) updateGameState(data.game);
        if (tickerTrack) updateTicker(data.ticker);
        if (accountProfileTitle) updateAccountProfile(data.config, data.health);
        if (radarSweepRegime) updateRadarSweep(data.radar);
        if (equityCanvas) updateEquityChart(data.rolling_backtest, data.mt5_telemetry);
        checkForNewCloses(data.mt5_telemetry);
    });

    function updatePredictiveHero(imm) {
        if (!imm) return;
        imminentStrategyName.textContent = imm.name;
        imminentRegime.textContent = imm.regime || "Compression Breakout";
        imminentCountdown.textContent = imm.countdown_formatted || "00m 00s";
        imminentSymbol.textContent = imm.next_symbol || "EURAUD";
        
        imminentDirection.textContent = imm.direction || "BUY";
        imminentDirection.className = `dir-badge ${(imm.direction || 'BUY').toLowerCase()}`;

        const conf = imm.confidence !== null && imm.confidence !== undefined ? imm.confidence : null;
        if (conf !== null) {
            imminentConfidenceFill.style.width = `${conf}%`;
            imminentConfidenceVal.textContent = `${conf}%`;
        } else {
            imminentConfidenceFill.style.width = '0%';
            imminentConfidenceVal.textContent = '—';
        }

        imminentTargetWin.textContent = `+$${(imm.target_win_usd || 195.04).toFixed(2)}`;
    }

    function updateMarketRadar(radar) {
        if (!radar) return;
        radarTickVelocity.textContent = radar.tick_velocity_per_sec;
        radarVelocityDesc.textContent = radar.tick_velocity_per_sec > 15 ? "High Market Activity" : "Moderate Liquidity Quoting";
        radarDispersion.textContent = `${radar.network_dispersion_pct}%`;
        radarAgreement.textContent = `${radar.directional_agreement_pct}%`;
        radarRegime.textContent = radar.volatility_regime;
        radarRegimeDesc.textContent = radar.regime_description;
    }

    function updateRadarSweep(radar) {
        if (!radar) return;
        if (radarSweepRegime) radarSweepRegime.textContent = (radar.volatility_regime || 'COMPRESSION').replace(/[^\x00-\x7F]/g, '').trim() || 'COMPRESSION';
        if (radarSweepVelocity) radarSweepVelocity.textContent = `${radar.tick_velocity_per_sec} t/s`;
        const blade = document.querySelector('.radar-sweep-blade');
        if (blade) {
            // Velocity drives sweep speed (min 2s, max 0.5s per revolution)
            const v = Math.max(0.5, Math.min(2.0, 60 / Math.max(radar.tick_velocity_per_sec, 1)));
            blade.style.animationDuration = `${v}s`;
        }
    }

    function updateAccountProfile(config, health) {
        if (!config) return;
        const eq = config.account_size || 0;
        accountProfileTitle.textContent = `$${eq.toLocaleString('en-US', {maximumFractionDigits: 0})} Capital Profile`;
        const live = health && health.connected ? 'LIVE' : 'SIM';
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
    function updateEquityChart(rbData, mt5Data) {
        if (!rbData || !equityCanvas) return;
        const series = rbData.equity_series || [];
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

            const dirClass = (st.direction || 'BUY').toLowerCase();
            const lot = (st.effective_lot || 0.15).toFixed(2);
            const targetWin = (st.target_win_usd || 25.0).toFixed(2);
            const targetLoss = (st.target_loss_usd || 10.0).toFixed(2);

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
                        <span class="label">Target Win</span>
                        <span class="val text-emerald">+$${targetWin}</span>
                    </div>
                    <div class="st-m-item">
                        <span class="label">Max Risk</span>
                        <span class="val text-rose">-$${targetLoss}</span>
                    </div>
                </div>

                <div class="st-card-bottom">
                    <div>
                        <span class="meta-label">NEXT SIGNAL TARGET</span>
                        <strong>${st.next_symbol || 'EURAUD'} <span class="dir-badge ${dirClass}">${st.direction || 'BUY'}</span></strong>
                    </div>
                    <div style="text-align: right;">
                        <span class="meta-label">HISTORICAL WR</span>
                        <strong class="text-emerald">${st.win_rate !== null && st.win_rate !== undefined ? st.win_rate + '% (PF ' + st.profit_factor + ')' : 'NO LIVE DATA'}</strong>
                    </div>
                </div>
            `;
            strategyCardsContainer.appendChild(card);
        });
    }

    function updateDiagnostics(diagnostics) {
        if (!diagnostics || !diagnostics.length) return;
        diagnosticsGrid.innerHTML = '';

        diagnostics.forEach((d) => {
            const card = document.createElement('div');
            card.className = 'diag-card';
            const isGateOpen = d.status.includes("OPEN");
            const badgeClass = isGateOpen ? "diag-status-badge open" : "diag-status-badge waiting";

            card.innerHTML = `
                <div class="diag-header">
                    <span class="diag-name">${d.name}</span>
                    <span class="${badgeClass}">${d.status}</span>
                </div>

                <div class="confidence-bar-wrap" style="height: 10px;">
                    <div class="confidence-bar-fill" style="width: ${d.progress_pct}%; background: ${isGateOpen ? 'var(--accent-emerald)' : 'var(--accent-amber)'};"></div>
                </div>

                <div class="diag-thresholds">
                    <div>
                        <span class="meta-label">PRIMARY ENTRY GATE</span>
                        <strong style="font-size: 0.85rem;">${d.primary_gate}</strong>
                    </div>
                    <div>
                        <span class="meta-label">THRESHOLD vs CURRENT</span>
                        <strong style="font-size: 0.85rem;" class="font-mono">${d.required_threshold} | ${d.current_value}</strong>
                    </div>
                </div>

                <div class="diag-blockage-box">
                    <i class="fa-solid fa-triangle-exclamation"></i> <strong>BLOCKAGE REASON:</strong> ${d.blockage_reason}
                </div>
            `;
            diagnosticsGrid.appendChild(card);
        });
    }

    function updateVPSLogs(vpsLogs) {
        if (!vpsLogs || !vpsLogs.length) return;
        consoleLogBody.innerHTML = '';

        vpsLogs.forEach((l) => {
            const line = document.createElement('div');
            line.className = `log-line ${l.severity.toLowerCase()}`;
            line.innerHTML = `
                <span style="color: var(--text-muted); font-size: 0.75rem;">[${l.timestamp}]</span>
                <span style="font-weight: 700; width: 90px;">[${l.severity}]</span>
                <span>${l.raw}</span>
            `;
            consoleLogBody.appendChild(line);
        });
    }

    function updateExposureTable(exposure) {
        if (!exposure || !exposure.length) return;
        exposureTableBody.innerHTML = '';

        exposure.forEach((exp) => {
            const tr = document.createElement('tr');
            const isLong = exp.direction.includes("LONG");
            const dirBadge = isLong ? '<span class="dir-badge buy">NET LONG</span>' : '<span class="dir-badge sell">NET SHORT</span>';

            tr.innerHTML = `
                <td><strong>${exp.currency}</strong></td>
                <td>${dirBadge}</td>
                <td><span class="font-mono">${exp.net_exposure_lots.toFixed(2)} Lots</span></td>
                <td><span class="font-mono">$${exp.exposure_usd.toLocaleString('en-US', {minimumFractionDigits: 2})}</span></td>
                <td><span class="font-mono text-emerald">${exp.risk_pct}%</span></td>
            `;
            exposureTableBody.appendChild(tr);
        });
    }

    function updateRollingBacktest(rbData) {
        if (!rbData) return;
        const m = rbData.rolling_2hr_metrics;
        const liveM = rbData.today_live_metrics;

        if (todayLiveWinRate && liveM) {
            todayLiveWinRate.textContent = `${liveM.live_win_rate_percent.toFixed(1)}%`;
            if (todayLivePnl) {
                const sign = liveM.live_net_pnl_usd >= 0 ? '+' : '';
                todayLivePnl.textContent = `MT5 Today PnL: ${sign}$${liveM.live_net_pnl_usd.toFixed(2)} (${liveM.total_live_trades} Trades)`;
            }
        }

        if (rbWinRate && m) {
            rbWinRate.textContent = `${m.win_rate_percent.toFixed(1)}%`;
            if (rbTradeCounts) {
                const pySign = m.net_pnl_usd >= 0 ? '+' : '';
                rbTradeCounts.textContent = `Python Today PnL: ${pySign}$${m.net_pnl_usd.toFixed(2)} (${m.total_trades} Trades)`;
            }
        }

        if (rbProfitFactor && m) rbProfitFactor.textContent = m.profit_factor.toFixed(2);
        if (rbNextRun) rbNextRun.textContent = rbData.next_run_formatted || '05m 00s';
        if (rbLastRunTime) rbLastRunTime.textContent = `Last Cycle #${rbData.run_counter} at ${rbData.last_run_time}`;

        if (rollingBacktestTableBody && rbData.trades) {
            rollingBacktestTableBody.innerHTML = '';
            rbData.trades.forEach((t) => {
                const tr = document.createElement('tr');
                if (t.is_live) {
                    tr.style.background = 'rgba(16, 185, 129, 0.08)';
                    tr.style.borderLeft = '3px solid var(--accent-emerald)';
                }

                const simPnlClass = t.sim_pnl >= 0 ? 'text-emerald' : 'text-rose';
                const simSign = t.sim_pnl >= 0 ? '+' : '';
                const badge = t.is_win ? '🟢 WIN' : '🔴 LOSS';
                const timestampText = t.iso_timestamp || t.timestamp;

                let liveBadgeHtml = '<span class="log-filter-btn">PYTHON SIM</span>';
                // Only show gate badge if engine confirmed this was actually spread-gated
                // (cross-checked against real live MT5 trades). Everything else shows '—'.
                let liveClosePnlHtml;
                if (t.gate_reason === 'spread_gate') {
                    liveClosePnlHtml = '<span title="Confirmed: live EA blocked — spread exceeded 6pip gate at this session hour" style="font-size: 0.72rem; font-weight: 700; font-family: var(--font-mono); color: var(--accent-amber); background: rgba(245,158,11,0.12); border: 1px solid rgba(245,158,11,0.35); border-radius: 4px; padding: 2px 6px; white-space: nowrap;">🔒 &lt;6p gate</span>';
                } else {
                    liveClosePnlHtml = '<span style="color: var(--text-muted);">—</span>';
                }

                if (t.is_live) {
                    liveBadgeHtml = '<span class="log-filter-btn active" style="background: var(--accent-emerald); color: #000; font-weight: 800;"><i class="fa-solid fa-bolt"></i> LIVE VPS</span>';
                    const livePnlVal = t.live_close_pnl !== null ? t.live_close_pnl : t.sim_pnl;
                    const livePnlClass = livePnlVal >= 0 ? 'text-emerald' : 'text-rose';
                    const liveSign = livePnlVal >= 0 ? '+' : '';
                    liveClosePnlHtml = `<strong class="${livePnlClass} font-mono" style="font-size: 0.95rem;">${liveSign}$${livePnlVal.toFixed(2)}</strong>`;
                }

                const bugReasonStr = t.bug_reason || "🟢 CLEAN EXECUTION";
                let bugColor = "var(--accent-emerald)";
                if (bugReasonStr.includes("BUG") || bugReasonStr.includes("🛑") || bugReasonStr.includes("⚠️")) {
                    bugColor = "var(--accent-rose)";
                } else if (bugReasonStr.includes("TEST") || bugReasonStr.includes("SLIPPAGE")) {
                    bugColor = "var(--accent-amber)";
                }

                // Parse UTC timestamp and compute IST (UTC+5:30) — show full date+time
                const utcStr = (t.iso_timestamp || t.timestamp || '').replace(' UTC', '');
                let istHtml = '';
                try {
                    const utcDate = new Date(utcStr.replace(' ', 'T') + 'Z');
                    const istOffsetMs = (5 * 60 + 30) * 60 * 1000;
                    const istDate = new Date(utcDate.getTime() + istOffsetMs);
                    const pad = n => String(n).padStart(2, '0');
                    const istFormatted = `${istDate.getUTCFullYear()}-${pad(istDate.getUTCMonth()+1)}-${pad(istDate.getUTCDate())} ${pad(istDate.getUTCHours())}:${pad(istDate.getUTCMinutes())}:${pad(istDate.getUTCSeconds())}`;
                    istHtml = `<div style="font-size: 0.7rem; color: var(--text-muted); margin-top: 2px; font-family: var(--font-mono);">${istFormatted} IST</div>`;
                } catch(e) {}

                tr.innerHTML = `
                    <td><span style="font-family: var(--font-mono); font-size: 0.8rem;">${timestampText}</span>${istHtml}</td>
                    <td>${liveBadgeHtml}</td>
                    <td><strong style="font-family: var(--font-mono);">#${t.ticket}</strong></td>
                    <td><strong>${t.strategy}</strong></td>
                    <td><strong>${t.pair}</strong></td>
                    <td><span class="dir-badge ${t.side.toLowerCase()}">${t.side}</span></td>
                    <td><span class="font-mono">${t.lot.toFixed(2)}L</span></td>
                    <td><span class="font-mono">${t.pips >= 0 ? '+' : ''}${t.pips}p</span></td>
                    <td><span class="${simPnlClass} font-mono">${simSign}$${t.sim_pnl.toFixed(2)}</span></td>
                    <td>${liveClosePnlHtml}</td>
                    <td><span style="font-size: 0.75rem; font-weight: 700; font-family: var(--font-mono); color: ${bugColor};">${bugReasonStr}</span></td>
                    <td><span style="font-size: 0.75rem; font-weight: 700;">${badge}</span></td>
                `;
                rollingBacktestTableBody.appendChild(tr);
            });
        }
    }

    function updateAuditTable(mt5Data) {
        if (!mt5Data || !mt5Data.trades || !mt5Data.trades.length) return;

        auditTableBody.innerHTML = '';
        mt5Data.trades.slice(-10).reverse().forEach((t) => {
            const tr = document.createElement('tr');
            const isWin = t.net_pnl >= 0;
            const pnlClass = isWin ? 'text-emerald' : 'text-rose';
            const sign = isWin ? '+' : '';
            const statusBadge = isWin ? '🟢 RECONCILED WIN' : '🔴 RECONCILED LOSS';

            tr.innerHTML = `
                <td>
                    <div style="font-weight: 700; font-family: var(--font-mono);">#${t.ticket}</div>
                    <div style="font-size: 0.75rem; color: var(--text-muted);">${t.entry_time}</div>
                </td>
                <td><strong>${t.strategy}</strong></td>
                <td><strong>${t.symbol}</strong></td>
                <td><span class="dir-badge ${t.type.toLowerCase()}">${t.type}</span></td>
                <td><span class="font-mono">${t.lot.toFixed(2)}L</span></td>
                <td><span class="font-mono">${t.entry_price} → ${t.exit_price}</span></td>
                <td><span class="font-mono">${t.pips >= 0 ? '+' : ''}${t.pips}p</span></td>
                <td><strong class="${pnlClass} font-mono">${sign}$${t.net_pnl.toFixed(2)}</strong></td>
                <td><span class="font-mono">${t.hold_min}m</span></td>
                <td><span style="font-size: 0.75rem; font-weight: 700;">${statusBadge}</span></td>
            `;
            auditTableBody.appendChild(tr);
        });
    }
});
