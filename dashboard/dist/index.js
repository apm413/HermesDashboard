/* Hermes Dashboard — Steampunk Neomechanicum 2099
   Vanilla React, без сборки. Контракт: window.__HERMES_PLUGINS__.register(name, App)
*/
(function () {
  "use strict";

  const SDK = window.__HERMES_PLUGIN_SDK__;
  if (!SDK) { console.warn("hermes-dashboard: SDK not ready"); return; }
  const { React: h, hooks, components, fetchJSON } = SDK;

  const { useState, useEffect, useRef, useMemo, useCallback, createElement: ce } =
    (h && h.__esModule ? h.default : h) || {};

  // ===========================================================================
  // SVG primitives (BrassGear, SteamPipe, ValveLamp, Manometer, BrassCorner)
  // ===========================================================================

  const BrassGear = ({ size = 18, reverse = false, teeth = 8, style }) => {
    const c = size / 2;
    const r = size * 0.32;
    const innerR = size * 0.12;
    const points = [];
    for (let i = 0; i < teeth * 2; i++) {
      const a = (i / (teeth * 2)) * Math.PI * 2;
      const rad = i % 2 === 0 ? r : r * 0.78;
      points.push([c + Math.cos(a) * rad, c + Math.sin(a) * rad].join(","));
    }
    return ce("svg", {
      width: size, height: size, viewBox: `0 0 ${size} ${size}`,
      style: { display: "inline-block", verticalAlign: "middle", ...style },
      className: `gear ${reverse ? "reverse" : ""}`,
    },
      ce("polygon", { points: points.join(" "), fill: "currentColor", opacity: 0.85 }),
      ce("circle", { cx: c, cy: c, r: innerR, fill: "var(--bg-base)" }),
      ce("circle", { cx: c, cy: c, r: innerR * 0.5, fill: "currentColor" })
    );
  };

  const ValveLamp = ({ status = "grey", pulse = false }) => {
    return ce("span", { className: `lamp ${status} ${pulse ? "pulse" : ""}` });
  };

  const SteamPipe = ({ label }) => {
    return ce("div", { className: "steam-pipe", title: label || "" });
  };

  const BrassCorner = ({ pos }) => {
    // pos: tl | tr | bl | br
    return ce("svg", {
      className: `frame-corner ${pos}`, viewBox: "0 0 28 28",
      width: 28, height: 28,
    },
      ce("path", {
        d: "M0 0 L28 0 L28 4 L4 4 L4 28 L0 28 Z",
        fill: "currentColor", opacity: 0.6,
      }),
      ce("circle", { cx: 12, cy: 12, r: 2, fill: "currentColor" })
    );
  };

  // Manometer (стрелочный индикатор)
  const Manometer = ({ value = 0, max = 100, label = "", warn = 70, danger = 90, fmt = (v) => `${v.toFixed(0)}%` }) => {
    const pct = Math.max(0, Math.min(100, (value / max) * 100));
    const angle = -135 + (pct / 100) * 270; // -135°..+135°
    const color = pct >= danger ? "var(--neon-pink)" : pct >= warn ? "var(--neon-amber)" : "var(--neon-cyan)";
    const rad = (angle * Math.PI) / 180;
    const cx = 60, cy = 60, len = 40;
    const x2 = cx + Math.cos(rad) * len;
    const y2 = cy + Math.sin(rad) * len;

    return ce("div", null,
      ce("svg", { className: "meter-svg", viewBox: "0 0 120 100" },
        // Арка
        ce("path", {
          d: "M15 75 A50 50 0 1 1 105 75",
          fill: "none", stroke: "var(--brass-dim)", strokeWidth: 6, strokeLinecap: "round",
        }),
        // tick marks
        ...[-135, -90, -45, 0, 45, 90, 135].map((a, i) => {
          const r = 50;
          const r2 = 42;
          const rr = (a * Math.PI) / 180;
          return ce("line", {
            key: i,
            x1: cx + Math.cos(rr) * r2, y1: cy + Math.sin(rr) * r2,
            x2: cx + Math.cos(rr) * r, y2: cy + Math.sin(rr) * r,
            stroke: "var(--brass)", strokeWidth: 1.5,
          });
        }),
        // стрелка
        ce("line", {
          x1: cx, y1: cy, x2, y2,
          stroke: color, strokeWidth: 2.5, strokeLinecap: "round",
          style: { filter: `drop-shadow(0 0 4px ${color})` },
        }),
        ce("circle", { cx, cy: cy, r: 5, fill: "var(--brass)", stroke: "var(--bg-base)", strokeWidth: 1 }),
      ),
      ce("div", { className: "meter-label" }, label),
      ce("div", { className: "meter-val", style: { color } }, fmt(value))
    );
  };

  // ===========================================================================
  // DAG (ручной SVG, без xyflow — он через npm и не входит в Hermes runtime-shim)
  // ===========================================================================

  // Узлы DAG для HermeSvideo / tier1
  const DAG_DEFS = {
    hermesvideo: {
      title: "HermeSvideo Pipeline",
      nodes: [
        { id: "infra", label: "infra-agent", sub: "RunPod pod", x: 60, y: 40 },
        { id: "character", label: "character-agent", sub: "LoRA / persona", x: 60, y: 160 },
        { id: "video", label: "video-agent", sub: "txt2img → Wan 2.2 I2V", x: 240, y: 100 },
        { id: "postprod", label: "post-prod", sub: "voice + music + mix", x: 420, y: 100 },
        { id: "publish", label: "publish-agent", sub: "Fanvue/X/Reddit/TG", x: 600, y: 100 },
      ],
      edges: [
        ["infra", "video"], ["character", "video"],
        ["video", "postprod"], ["postprod", "publish"],
      ],
    },
    tier1: {
      title: "tier1 Marketing",
      nodes: [
        { id: "schedule", label: "schedule", sub: "cron 9/10/13/17/19/22/01/03", x: 60, y: 100 },
        { id: "seo", label: "seo-curator", sub: "blog article", x: 240, y: 40 },
        { id: "reddit", label: "reddit-poster", sub: "r/AIgirls, aivideo", x: 240, y: 160 },
        { id: "twitter", label: "twitter-poster", sub: "@MiaAIcreator", x: 420, y: 100 },
        { id: "analytics", label: "analytics", sub: "daily report", x: 600, y: 100 },
      ],
      edges: [
        ["schedule", "seo"], ["schedule", "reddit"], ["schedule", "twitter"], ["schedule", "analytics"],
        ["seo", "analytics"], ["reddit", "analytics"], ["twitter", "analytics"],
      ],
    },
  };

  // Утилита: детерминированный случайный offset для staggered анимаций
const _seedRef = { v: 0 };
const nextSeed = () => ++_seedRef.v;

// Хелпер: создать SVG path для ребра (используется animateMotion)
const makeEdgePath = (x1, y1, x2, y2) => {
  const dx = x2 - x1, dy = y2 - y1;
  // Лёгкая кривизна для красивости
  const cx = x1 + dx * 0.5, cy = y1 + dy * 0.5 - Math.min(40, Math.abs(dx) * 0.15);
  return `M ${x1} ${y1} Q ${cx} ${cy} ${x2} ${y2}`;
};

const DAG = ({ project, runs, events }) => {
    const def = DAG_DEFS[project] || DAG_DEFS.hermesvideo;

    const nodeStatus = useMemo(() => {
      const out = {};
      for (const n of def.nodes) out[n.id] = "idle";
      const lastByAgent = {};
      for (const e of events) {
        const agent = String(e.agent || "").toLowerCase();
        const lvl = String(e.level || "INFO");
        const msg = String(e.message || "");
        lastByAgent[agent] = { level: lvl, msg, ts: e.ts };
      }
      const agentMap = {
        orchestrator: ["infra", "character", "video", "postprod", "publish"],
        video: ["video"], "post-prod": ["postprod"], postprod: ["postprod"],
        publish: ["publish"], infra: ["infra"], character: ["character"],
        seo_curator: ["seo"], "seo": ["seo"],
        reddit_poster: ["reddit"], "reddit": ["reddit"],
        twitter_poster: ["twitter"], "twitter": ["twitter"],
        analytics: ["analytics"],
      };
      for (const [agent, ids] of Object.entries(agentMap)) {
        const last = lastByAgent[agent];
        if (!last) continue;
        const status = last.level === "ERROR" ? "failed" :
                       /WAITING|waiting|approve/i.test(last.msg) ? "waiting" :
                       /done|completed|published|mock clips ready|final mixed|final MP4|publish-approve/i.test(last.msg) ? "done" :
                       "running";
        for (const id of ids) {
          if (out[id] === "idle" || status === "failed") out[id] = status;
          if (status === "running") out[id] = "running";
        }
      }
      return out;
    }, [events, project]);

    // Активные рёбра = где хотя бы один узел running
    const activeEdges = useMemo(() => {
      const out = new Set();
      for (const [a, b] of def.edges) {
        if (nodeStatus[a] === "running" || nodeStatus[b] === "running") {
          out.add(`${a}->${b}`);
        }
      }
      return out;
    }, [nodeStatus, project]);

    // Последнее значимое событие (для баннера)
    const lastEvent = useMemo(() => {
      for (let i = events.length - 1; i >= 0; i--) {
        const e = events[i];
        if (!e) continue;
        const msg = String(e.message || "");
        if (/waiting|approve/i.test(msg)) return { ...e, banner: "waiting" };
        if (e.level === "ERROR") return { ...e, banner: "failed" };
        if (/pipeline start|started|mock-render|mock clip|generating|publishing|reviewing|rendering|writing|video|published|final|done/i.test(msg)) {
          return { ...e, banner: e.level === "ERROR" ? "failed" : "active" };
        }
      }
      return null;
    }, [events]);

    const w = 720, max = 260;

    return ce("div", { className: "dag-wrap" },
      ce("svg", {
        className: "dag-svg", viewBox: `0 0 ${w} ${max}`,
        preserveAspectRatio: "xMidYMid meet",
      },
        // Определения: filter, paths для animateMotion, particle gradient
        ce("defs", null,
          ce("filter", { id: "neon-glow" },
            ce("feGaussianBlur", { stdDeviation: "2", result: "b" }),
            ce("feMerge", null,
              ce("feMergeNode", { in: "b" }),
              ce("feMergeNode", { in: "SourceGraphic" }),
            ),
          ),
          ce("radialGradient", { id: "particle-grad" },
            ce("stop", { offset: "0%", "stop-color": "var(--neon-cyan)", "stop-opacity": 1 }),
            ce("stop", { offset: "100%", "stop-color": "var(--neon-cyan)", "stop-opacity": 0 }),
          ),
          ce("radialGradient", { id: "particle-grad-failed" },
            ce("stop", { offset: "0%", "stop-color": "var(--neon-pink)", "stop-opacity": 1 }),
            ce("stop", { offset: "100%", "stop-color": "var(--neon-pink)", "stop-opacity": 0 }),
          ),
          // Скрытые path'ы для animateMotion — по одному на активное ребро
          ...def.edges.map(([a, b], i) => {
            const na = def.nodes.find(n => n.id === a);
            const nb = def.nodes.find(n => n.id === b);
            if (!na || !nb) return null;
            const x1 = na.x + 180, y1 = na.y + 28;
            const x2 = nb.x, y2 = nb.y + 28;
            return ce("path", {
              key: `path-${i}`, id: `edge-path-${a}-${b}`,
              d: makeEdgePath(x1, y1, x2, y2),
              fill: "none", stroke: "none",
            });
          }),
        ),

        // === Рёбра (визуальные линии) ===
        ...def.edges.map(([a, b], i) => {
          const na = def.nodes.find(n => n.id === a);
          const nb = def.nodes.find(n => n.id === b);
          if (!na || !nb) return null;
          const isActive = activeEdges.has(`${a}->${b}`);
          const x1 = na.x + 180, y1 = na.y + 28;
          const x2 = nb.x, y2 = nb.y + 28;
          return ce("g", { key: `e-${i}` },
            ce("line", {
              x1, y1, x2, y2,
              className: `dag-edge ${isActive ? "active" : ""}`,
            }),
          );
        }),

        // === Анимированные частицы (только на активных рёбрах) ===
        ...def.edges.flatMap(([a, b], i) => {
          const isActive = activeEdges.has(`${a}->${b}`);
          if (!isActive) return [];
          const failed = nodeStatus[a] === "failed" || nodeStatus[b] === "failed";
          const color = failed ? "var(--neon-pink)" : "var(--neon-cyan)";
          // 2-3 частицы с разной скоростью и задержкой
          return [0, 1, 2].map((k) => {
            const dur = 2 + (k * 0.7);  // 2.0, 2.7, 3.4 сек
            const begin = -(k * 0.8);    // смещение для staggered
            return ce("g", { key: `p-${a}-${b}-${k}` },
              ce("circle", {
                r: 4, className: failed ? "particle failed" : "particle",
                filter: "url(#neon-glow)",
              },
                ce("animateMotion", {
                  dur: `${dur}s`, repeatCount: "indefinite", begin: `${begin}s`,
                  path: `M 0 0 L ${700} 0`,  // dummy — заменится через mpath
                }),
              ),
              ce("animateMotion", {
                dur: `${dur}s`, repeatCount: "indefinite", begin: `${begin}s`,
              },
                ce("mpath", { href: `#edge-path-${a}-${b}` }),
              ),
            );
          });
        }),

        // === Узлы DAG ===
        ...def.nodes.map((n) => {
          const status = nodeStatus[n.id] || "idle";
          const isRunning = status === "running";
          const isFailed = status === "failed";
          const progressWidth =
            status === "done" ? 164 :
            status === "running" ? 100 :
            status === "failed" ? 60 : 0;
          return ce("g", {
            key: n.id, className: "dag-node", transform: `translate(${n.x}, ${n.y})`,
          },
            // V2: Phase chip (только если статус отличается от idle)
            status !== "idle" && ce("foreignObject", { x: 150, y: -10, width: 32, height: 16 },
              ce(PhaseChip, { status })
            ),
            // Radar-скан (только для running)
            isRunning && ce("circle", {
              className: "node-scan",
              cx: 90, cy: 28, r: 30,
            }),
            // Корпус узла
            ce("rect", {
              className: `node-rect ${status}`,
              x: 0, y: 0, width: 180, height: 56, rx: 6,
            }),
            // Внутреннее ядро (только running)
            isRunning && ce("circle", {
              className: "node-core",
              cx: 90, cy: 28, r: 12,
            }),
            // Текст
            ce("text", { className: "node-text", x: 12, y: 22 }, n.label),
            ce("text", { className: "node-text-sub", x: 12, y: 38 }, n.sub),
            // Лампа статуса
            ce("foreignObject", { x: 152, y: 8, width: 24, height: 24 },
              ce(ValveLamp, {
                status: status === "running" ? "yellow" :
                        status === "done" ? "green" :
                        status === "failed" ? "red" :
                        status === "waiting" ? "yellow" : "grey",
                pulse: status === "running" || status === "waiting",
              }),
            ),
            // Прогресс-бар
            ce("rect", { className: "node-progress-bg", x: 8, y: 46, width: 164, height: 4, rx: 2 }),
            ce("rect", {
              className: "node-progress-fill",
              x: 8, y: 46, width: progressWidth, height: 4, rx: 2,
            }),
          );
        }),
      ),

      // === Баннер последнего события (поверх DAG) ===
      lastEvent && ce("div", {
        className: `dag-banner ${lastEvent.banner === "failed" ? "failed" : ""}`,
      },
        ce("span", { className: "pulse-dot" }),
        ce("strong", null, `[${lastEvent.agent}]`),
        ce("span", { style: { opacity: .7 } }, lastEvent.message?.substring(0, 140) || ""),
      ),
    );
  };

  // ===========================================================================
  // V2: FilterBar — search + level chips + counter
  // ===========================================================================
  const FilterBar = ({ query, setQuery, level, setLevel, count, total }) => {
    return ce("div", { className: "filter-bar" },
      ce("input", {
        type: "search",
        placeholder: "Поиск по сообщениям/агенту…",
        value: query,
        onChange: (e) => setQuery(e.target.value),
      }),
      ce("div", { className: "chips" },
        ...["ALL", "INFO", "WARNING", "ERROR", "DEBUG"].map(lv =>
          ce("span", {
            key: lv,
            className: `chip ${lv === "ALL" ? "" : lv.toLowerCase()} ${level === lv ? "active" : ""}`,
            onClick: () => setLevel(lv),
          }, lv)
        ),
      ),
      ce("span", { style: { marginLeft: "auto", color: "var(--text-dim)" } },
        `${count} / ${total}`),
    );
  };

  // ===========================================================================
  // V2: SystemMetricsRow — CPU / RAM / Disk bars
  // ===========================================================================
  const SystemMetricsRow = ({ metrics }) => {
    if (!metrics) {
      return ce("div", { className: "metrics-row" },
        ce("div", { className: "metric" }, ce("span", { className: "label" }, "CPU"), ce("span", { className: "value" }, "—")),
        ce("div", { className: "metric" }, ce("span", { className: "label" }, "RAM"), ce("span", { className: "value" }, "—")),
        ce("div", { className: "metric" }, ce("span", { className: "label" }, "DISK"), ce("span", { className: "value" }, "—")),
      );
    }
    const cpu = metrics.cpu_pct || 0;
    const ram = metrics.ram_pct || 0;
    const disks = metrics.disks || [];
    const mainDisk = disks[0] || { pct: 0, used_gb: 0, total_gb: 0 };
    const fmt = (n) => (typeof n === "number" ? (n < 10 ? n.toFixed(1) : Math.round(n)) : n);

    return ce("div", { className: "metrics-row" },
      ce("div", { className: `metric ${cpu > 80 ? "danger" : cpu > 50 ? "warn" : ""}` },
        ce("span", { className: "label" }, "CPU"),
        ce("div", { className: "bar" }, ce("span", { style: { width: Math.min(cpu, 100) + "%" } })),
        ce("span", { className: "value" }, fmt(cpu) + "%"),
      ),
      ce("div", { className: `metric ${ram > 85 ? "danger" : ram > 65 ? "warn" : ""}` },
        ce("span", { className: "label" }, "RAM"),
        ce("div", { className: "bar" }, ce("span", { style: { width: Math.min(ram, 100) + "%" } })),
        ce("span", { className: "value" }, fmt(ram) + "%"),
        ce("span", { style: { color: "var(--text-dim)", marginLeft: 4 } },
          `(${metrics.ram_used_gb}/${metrics.ram_total_gb}G)`),
      ),
      ce("div", { className: `metric ${mainDisk.pct > 90 ? "danger" : mainDisk.pct > 75 ? "warn" : ""}` },
        ce("span", { className: "label" }, "DISK"),
        ce("div", { className: "bar" }, ce("span", { style: { width: Math.min(mainDisk.pct, 100) + "%" } })),
        ce("span", { className: "value" }, fmt(mainDisk.pct) + "%"),
        ce("span", { style: { color: "var(--text-dim)", marginLeft: 4 } },
          `(${mainDisk.used_gb}/${mainDisk.total_gb}G)`),
      ),
      ce("div", { className: "metric" },
        ce("span", { className: "label" }, "CORES"),
        ce("span", { className: "value" }, metrics.cpu_count_logical || "—"),
      ),
    );
  };

  // ===========================================================================
  // V2: PhaseChip — pill поверх running-узла
  // ===========================================================================
  const PhaseChip = ({ status }) => {
    const cls = status === "running" ? "processing" :
                status === "done"    ? "done" :
                status === "failed"  ? "failed" :
                status === "waiting" ? "awaiting" : "awaiting";
    const label = status === "running" ? "PROC" :
                  status === "done"    ? "DONE" :
                  status === "failed"  ? "ERR"  :
                  status === "waiting" ? "WAIT" : "IDLE";
    return ce("div", { className: `phase-chip ${cls}` }, label);
  };

  // ===========================================================================
  // LogStream
  // ===========================================================================

  const LogStream = ({ events }) => {
    const ref = useRef(null);
    useEffect(() => {
      if (ref.current && events.length) ref.current.scrollTop = 0;
    }, [events.length]);
    const fmtTime = (ts) => {
      const d = new Date(ts * 1000);
      return d.toLocaleTimeString("ru-RU", { hour12: false });
    };
    return ce("div", { ref, className: "log-stream" },
      events.length === 0 && ce("div", { style: { color: "var(--text-dim)", textAlign: "center", padding: 20 } },
        "Нет событий — запустите агентов в фоне"),
      events.map((e, i) => {
        const cls = e.level === "ERROR" ? "failed" :
                    /done|completed|published|final|mock clips ready/i.test(e.message) ? "done" :
                    /WAITING|waiting|approve/i.test(e.message) ? "waiting" : "";
        return ce("div", { key: i, className: `log-line ${cls}` },
          ce("span", { className: "ts" }, `[${fmtTime(e.ts)}] `),
          ce("span", { className: "lvl " + e.level }, e.level.padEnd(7)),
          ce("span", { className: "agent" }, `[${e.agent}]`),
          ce("span", { className: "msg" }, " " + e.message),
        );
      })
    );
  };

  // ===========================================================================
  // V2: TokenPanel — token/cost counter с mini-bar-chart по дням
  // ===========================================================================
  const TokenPanel = ({ stats }) => {
    if (!stats || !stats.total || stats.total.calls === 0) {
      return ce("div", { style: { padding: 8, color: "var(--text-dim)", fontSize: 11 } },
        "TOKEN USAGE · no usage data yet");
    }
    const t = stats.total;
    const fmt = (n) => n >= 1000 ? (n / 1000).toFixed(1) + "k" : String(n);
    const max = Math.max(1, ...(stats.daily.input || []), ...(stats.daily.output || []));
    return ce("div", null,
      ce("div", { style: { display: "flex", justifyContent: "space-between", fontSize: 11, fontFamily: "var(--font-mono)" } },
        ce("span", { style: { color: "var(--text-dim)" } }, "TOKEN USAGE"),
        ce("span", { style: { color: "var(--neon-cyan)" } }, t.calls + " calls"),
      ),
      ce("div", { style: { display: "flex", gap: 12, fontFamily: "var(--font-mono)", fontSize: 11, marginTop: 4 } },
        ce("div", null,
          ce("span", { style: { color: "var(--text-dim)", marginRight: 4 } }, "in:"),
          ce("span", { style: { color: "var(--neon-cyan)" } }, fmt(t.in)),
        ),
        ce("div", null,
          ce("span", { style: { color: "var(--text-dim)", marginRight: 4 } }, "out:"),
          ce("span", { style: { color: "var(--neon-amber)" } }, fmt(t.out)),
        ),
      ),
      stats.daily.labels.length > 0 && ce("div", { style: { display: "flex", alignItems: "flex-end", gap: 2, height: 28, marginTop: 6 } },
        ...stats.daily.labels.map((day, i) => {
          const total = (stats.daily.input[i] || 0) + (stats.daily.output[i] || 0);
          const h = (total / max) * 26;
          return ce("div", { key: day, title: day + ": " + total, style: { flex: 1, display: "flex", flexDirection: "column-reverse" } },
            ce("div", { style: {
              height: (h * 0.3) + "px",
              background: "var(--neon-amber)",
              opacity: 0.7,
            } }),
            ce("div", { style: {
              height: (h * 0.7) + "px",
              background: "var(--neon-cyan)",
              boxShadow: "0 0 4px var(--glow-color)",
            } }),
          );
        }),
      ),
    );
  };

  // ===========================================================================
  // ConnectedPanel
  // ===========================================================================

  const ConnectedPanel = ({ connections, onRefresh }) => {
    return ce("div", null,
      ce("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 } },
        ce("div", { style: { fontFamily: "var(--font-display)", fontSize: 12, color: "var(--brass)", letterSpacing: 1 } }, "ПОДКЛЮЧЕНИЯ"),
        ce("button", { className: "action-btn", onClick: onRefresh, title: "Обновить" }, "↻"),
      ),
      ...connections.map((c, i) => ce("div", { key: i, className: "conn-row" },
        ce(ValveLamp, { status: c.status }),
        ce("div", null,
          ce("div", { className: "conn-name" }, c.name || "?"),
          ce("div", { className: "conn-detail" }, c.detail || ""),
        ),
        ce("div", { className: "conn-mask" }, c.masked || ""),
      )),
    );
  };

  // ===========================================================================
  // BudgetPanel
  // ===========================================================================

  const BudgetPanel = ({ budget, onRefresh }) => {
    const hv = budget && budget.hermesvideo || {};
    const t1 = budget && budget.tier1 || {};
    return ce("div", { className: "manometer-wrap" },
      ce("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center" } },
        ce("div", { style: { fontFamily: "var(--font-display)", fontSize: 12, color: "var(--brass)", letterSpacing: 1 } }, "БЮДЖЕТ"),
        ce("button", { className: "action-btn", onClick: onRefresh, title: "Обновить" }, "↻"),
      ),
      ce("div", { className: "manometer" },
        ce(Manometer, {
          value: hv.spent_today || 0, max: hv.daily_limit || 3,
          label: "HermesV2 / день",
          warn: 70, danger: 90,
          fmt: (v) => `$${v.toFixed(2)} / $${(hv.daily_limit || 3).toFixed(0)}`,
        }),
        ce(Manometer, {
          value: hv.spent_month || 0, max: hv.monthly_limit || 45,
          label: "HermesV2 / мес",
          warn: 70, danger: 90,
          fmt: (v) => `$${v.toFixed(2)} / $${(hv.monthly_limit || 45).toFixed(0)}`,
        }),
      ),
      ce("div", { className: "steam-pipe" }),
      ce("div", { className: "budget-row ok" },
        ce("span", null, "tier1 (Ollama)"),
        ce("span", null, t1.note || "$0 — Ollama локально"),
      ),
      hv.exceeded_daily && ce("div", { className: "budget-row danger" },
        ce("span", null, "⚠ DAILY BUDGET EXCEEDED"), ce("span", null, "")),
      hv.exceeded_monthly && ce("div", { className: "budget-row danger" },
        ce("span", null, "⚠ MONTHLY BUDGET EXCEEDED"), ce("span", null, "")),
    );
  };

  // ===========================================================================
  // RunsList
  // ===========================================================================

  const RunsList = ({ runs }) => {
    return ce("div", { className: "runs-list" },
      runs.length === 0 && ce("div", { style: { color: "var(--text-dim)", fontSize: 12, textAlign: "center", padding: 8 } },
        "Нет завершённых прогонов"),
      runs.slice(0, 12).map((r, i) => {
        const ago = Math.floor(Date.now() / 1000 - r.ts);
        const agoStr = ago < 60 ? `${ago}s` : ago < 3600 ? `${Math.floor(ago / 60)}m` : `${Math.floor(ago / 3600)}h`;
        return ce("div", { key: i, className: `run-item ${r.status}` },
          ce(ValveLamp, { status: r.status === "done" ? "green" : r.status === "failed" ? "red" : r.status === "waiting" ? "yellow" : "grey" }),
          ce("span", { className: "run-scenario" }, r.scenario_id || `${r.agent} #${r.id}`),
          ce("span", { style: { color: "var(--text-dim)" } }, r.agent),
          ce("span", { className: "run-when" }, `${agoStr}${r.duration_ms ? ` · ${r.duration_ms}ms` : ""}`),
        );
      })
    );
  };

  // ===========================================================================
  // Root App
  // ===========================================================================

  const TAB_DEFS = [
    { id: "all", label: "Все", projects: ["hermesvideo", "tier1"] },
    { id: "hermesvideo", label: "HermesV2", projects: ["hermesvideo"] },
    { id: "tier1", label: "tier1", projects: ["tier1"] },
  ];

  const App = () => {
    const [activeTab, setActiveTab] = useState("all");
    const [snapshot, setSnapshot] = useState({ active_runs: [], recent_runs: [], connections: [], budget: null });
    const [events, setEvents] = useState([]);
    const [statusFilter, setStatusFilter] = useState("all");
    const [wsConnected, setWsConnected] = useState(false);
    // V2 additions
    const [theme, setTheme] = useState(() => {
      try { return localStorage.getItem("hd.theme") || "cyan"; } catch (e) { return "cyan"; }
    });
    const [logQuery, setLogQuery] = useState("");
    const [logLevel, setLogLevel] = useState("ALL");
    const [systemMetrics, setSystemMetrics] = useState(null);
    const [tokenStats, setTokenStats] = useState(null);
    const [lastAction, setLastAction] = useState(null);
    const wsRef = useRef(null);

    useEffect(() => {
      document.documentElement.setAttribute("data-theme", theme);
      try { localStorage.setItem("hd.theme", theme); } catch (e) {}
    }, [theme]);

    const fetchSnapshot = useCallback(async () => {
      try {
        const data = await fetchJSON("/snapshot");
        setSnapshot(data || {});
      } catch (e) {
        console.warn("snapshot failed:", e);
      }
    }, []);

    const fetchLogs = useCallback(async () => {
      try {
        const data = await fetchJSON("/logs?limit=200");
        setEvents(((data && data.events) || []).slice().reverse());
      } catch (e) {
        console.warn("logs failed:", e);
      }
    }, []);

    const fetchSystem = useCallback(async () => {
      try {
        const m = await fetchJSON("/system");
        setSystemMetrics(m);
      } catch (e) { /* silently */ }
    }, []);

    const fetchTokens = useCallback(async () => {
      try {
        const t = await fetchJSON("/tokens");
        setTokenStats(t);
      } catch (e) { /* silently */ }
    }, []);

    useEffect(() => {
      fetchSnapshot();
      fetchLogs();
      fetchSystem();
      fetchTokens();
      const i1 = setInterval(fetchSnapshot, 5000);
      const i2 = setInterval(fetchLogs, 3000);
      const i3 = setInterval(fetchSystem, 5000);
      const i4 = setInterval(fetchTokens, 15000);
      return () => { clearInterval(i1); clearInterval(i2); clearInterval(i3); clearInterval(i4); };
    }, [fetchSnapshot, fetchLogs, fetchSystem, fetchTokens]);

    // WebSocket
    useEffect(() => {
      let closed = false;
      const connect = () => {
        if (closed) return;
        const proto = location.protocol === "https:" ? "wss" : "ws";
        const ws = new WebSocket(`${proto}://${location.host}/ws`);
        wsRef.current = ws;
        ws.onopen = () => setWsConnected(true);
        ws.onclose = () => {
          setWsConnected(false);
          if (!closed) setTimeout(connect, 3000);
        };
        ws.onerror = () => { try { ws.close(); } catch (e) {} };
        ws.onmessage = (msg) => {
          try {
            const data = JSON.parse(msg.data);
            if (data.type === "event" || data.type === "history") {
              setEvents((prev) => [data, ...prev].slice(0, 200));
              if (data.type === "event") {
                // refetch snapshot occasionally
                if (Math.random() < 0.15) fetchSnapshot();
              }
            }
          } catch (e) {}
        };
      };
      connect();
      return () => { closed = true; if (wsRef.current) try { wsRef.current.close(); } catch (e) {} };
    }, [fetchSnapshot]);

    const tab = TAB_DEFS.find(t => t.id === activeTab) || TAB_DEFS[0];

    // Filtered events by project + level + text search
    const filteredEvents = useMemo(() => {
      let evs = events;
      if (activeTab !== "all") {
        evs = evs.filter(e => e.project === activeTab);
      }
      if (statusFilter !== "all") {
        evs = evs.filter(e => {
          if (statusFilter === "errors") return e.level === "ERROR";
          if (statusFilter === "done") return /done|published|final|mock clips ready/i.test(e.message);
          if (statusFilter === "waiting") return /WAITING|waiting|approve/i.test(e.message);
          return true;
        });
      }
      if (logLevel !== "ALL") {
        evs = evs.filter(e => (e.level || "INFO") === logLevel);
      }
      if (logQuery.trim()) {
        const q = logQuery.toLowerCase();
        evs = evs.filter(e =>
          (e.message || "").toLowerCase().includes(q) ||
          (e.agent   || "").toLowerCase().includes(q)
        );
      }
      return evs;
    }, [events, activeTab, statusFilter, logLevel, logQuery]);

    // Run action
    const runAction = async (action, payload) => {
      try {
        await fetchJSON("/action", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ kind: action, ...payload }),
        });
      } catch (e) { console.warn("action failed:", e); }
      setTimeout(fetchSnapshot, 1000);
    };

    // Run now buttons (tier1)
    const tier1Agents = ["seo", "reddit", "twitter", "analytics"];

    return ce("div", { className: "app" },
      ce("canvas", { className: "steam-canvas", id: "steam-canvas", ref: (el) => {
        if (!el) return;
        // Init once
        if (el.dataset.inited) return;
        el.dataset.inited = "1";
        const ctx = el.getContext("2d");
        const resize = () => { el.width = el.clientWidth; el.height = el.clientHeight; };
        resize();
        window.addEventListener("resize", resize);
        const puffs = Array.from({ length: 24 }, () => ({
          x: Math.random() * el.width,
          y: el.height + Math.random() * 20,
          r: 4 + Math.random() * 12,
          vy: 0.2 + Math.random() * 0.5,
          vx: -0.2 + Math.random() * 0.4,
          a: 0.05 + Math.random() * 0.15,
        }));
        const loop = () => {
          ctx.clearRect(0, 0, el.width, el.height);
          for (const p of puffs) {
            p.x += p.vx; p.y -= p.vy; p.r += 0.05;
            if (p.y < -20 || p.x < -20 || p.x > el.width + 20) {
              p.x = Math.random() * el.width;
              p.y = el.height + 10;
              p.r = 4 + Math.random() * 12;
            }
            ctx.fillStyle = `rgba(232,226,208,${p.a})`;
            ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2); ctx.fill();
          }
          requestAnimationFrame(loop);
        };
        loop();
      }}),

      // Header
      ce("header", { className: "header" },
        ce(BrassGear, { size: 28 }),
        ce("div", null,
          ce("h1", { className: "title" }, "HERMES DASHBOARD"),
          ce("div", { className: "subtitle" }, "Steampunk Neomechanicum · v2.0"),
        ),
        ce("div", { style: { marginLeft: 12 } },
          ce(ValveLamp, { status: wsConnected ? "green" : "grey", pulse: wsConnected }),
          ce("span", { style: { marginLeft: 6, fontSize: 11, color: "var(--text-dim)" } },
            wsConnected ? "LIVE" : "offline"),
        ),
        // Theme switcher (3 пресета, v2)
        ce("div", { className: "theme-switcher", style: { marginLeft: 12 } },
          ...["cyan", "amber", "fuchsia"].map(t =>
            ce("button", {
              key: t,
              className: theme === t ? "active" : "",
              onClick: () => setTheme(t),
              title: `Тема: ${t}`,
            },
              ce("span", { className: `swatch ${t}` })
            ),
          ),
        ),
        ce("div", { className: "tabs" },
          ...TAB_DEFS.map(t =>
            ce("button", {
              key: t.id,
              className: `tab-btn ${activeTab === t.id ? "active" : ""}`,
              onClick: () => setActiveTab(t.id),
            },
              ce("span", { className: "rivet tl" }), ce("span", { className: "rivet tr" }),
              ce("span", { className: "rivet bl" }), ce("span", { className: "rivet br" }),
              t.label,
            ),
          ),
        ),
        ce(BrassGear, { size: 22, reverse: true }),
      ),

      // Toolbar
      ce("div", { className: "toolbar" },
        ce("div", { className: "group" },
          ce("span", { className: "label" }, "Фильтр:"),
          ["all", "errors", "done", "waiting"].map(s =>
            ce("button", {
              key: s,
              className: `action-btn ${statusFilter === s ? "active" : ""}`,
              onClick: () => setStatusFilter(s),
              style: statusFilter === s ? { borderColor: "var(--neon-cyan)", color: "var(--neon-cyan)" } : null,
            }, s === "all" ? "все" : s === "errors" ? "ошибки" : s === "done" ? "готово" : "ожидание"),
          ),
        ),
        ce("div", { className: "group", style: { marginLeft: 12 } },
          ce("span", { className: "label" }, "tier1 Run-now:"),
          ...tier1Agents.map(a =>
            ce("button", {
              key: a, className: "action-btn",
              onClick: () => runAction("run-now", { agent: a }),
              title: `Запустить ${a} в mock-режиме`,
            }, a),
          ),
        ),
        ce("div", { style: { flex: 1 } }),
        ce("div", { className: "group" },
          ce("span", { className: "label" }, "HermesV2:"),
          ce("button", {
            className: "action-btn danger",
            onClick: () => {
              const pid = prompt("pod_id для terminate:");
              if (pid) runAction("terminate-pod", { pod_id: pid });
            },
          }, "Terminate pod"),
        ),
      ),

      // Main grid
      ce("div", { className: "main" },
        // DAG
        ce("div", { className: "cell cell-dag" },
          ce(BrassCorner, { pos: "tl" }), ce(BrassCorner, { pos: "tr" }),
          ce(BrassCorner, { pos: "bl" }), ce(BrassCorner, { pos: "br" }),
          ce("div", { className: "cell-head" },
            ce(BrassGear, { size: 14 }), "DAG WORKFLOW"),
          ce("div", { className: "cell-body" },
            activeTab === "all"
              ? ce("div", { style: { display: "grid", gridTemplateRows: "1fr 1fr", height: "100%", gap: 8 } },
                  ce(DAG, { project: "hermesvideo", runs: snapshot.active_runs, events: filteredEvents }),
                  ce(DAG, { project: "tier1", runs: snapshot.active_runs, events: filteredEvents }),
                )
              : ce(DAG, { project: activeTab, runs: snapshot.active_runs, events: filteredEvents }),
          ),
        ),

        // LogStream
        ce("div", { className: "cell cell-logs" },
          ce(BrassCorner, { pos: "tl" }), ce(BrassCorner, { pos: "tr" }),
          ce(BrassCorner, { pos: "bl" }), ce(BrassCorner, { pos: "br" }),
          ce("div", { className: "cell-head" },
            ce(BrassGear, { size: 14, reverse: true }), "LOG STREAM"),
          // System metrics row (v2)
          ce(SystemMetricsRow, { metrics: systemMetrics }),
          // Filter bar (v2)
          ce(FilterBar, {
            query: logQuery, setQuery: setLogQuery,
            level: logLevel, setLevel: setLogLevel,
            count: filteredEvents.length, total: events.length,
          }),
          ce("div", { className: "cell-body" },
            ce(LogStream, { events: filteredEvents }),
          ),
        ),

        // Budget
        ce("div", { className: "cell cell-budget" },
          ce(BrassCorner, { pos: "tl" }), ce(BrassCorner, { pos: "tr" }),
          ce(BrassCorner, { pos: "bl" }), ce(BrassCorner, { pos: "br" }),
          ce("div", { className: "cell-head" },
            ce(BrassGear, { size: 14 }), "BUDGET + CONNECTED"),
          ce("div", { className: "cell-body", style: { display: "grid", gridTemplateRows: "auto auto auto 1fr", gap: 10 } },
            ce(BudgetPanel, { budget: snapshot.budget, onRefresh: fetchSnapshot }),
            ce(TokenPanel, { stats: tokenStats }),
            ce("div", { className: "steam-pipe" }),
            ce(ConnectedPanel, { connections: snapshot.connections || [], onRefresh: fetchSnapshot }),
          ),
        ),
      ),
    );
  };

  // Register — single contract for web host
  if (window.__HERMES_PLUGINS__ && window.__HERMES_PLUGINS__.register) {
    window.__HERMES_PLUGINS__.register("hermes-dashboard", App);
  } else {
    // Retry once SDK ready
    setTimeout(() => {
      if (window.__HERMES_PLUGINS__ && window.__HERMES_PLUGINS__.register) {
        window.__HERMES_PLUGINS__.register("hermes-dashboard", App);
      }
    }, 200);
  }
})();