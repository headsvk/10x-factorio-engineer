/**
 * Factorio Factory Co-Pilot — Dashboard Component
 *
 * Usage as a Claude React artifact (type: application/vnd.ant.react):
 *
 *   1. Paste the FACTORY_STATE constant first:
 *        const FACTORY_STATE = { /* state JSON from Claude *\/ };
 *   2. Paste this entire file after it.
 *
 * FACTORY_STATE schema:
 * {
 *   save_name:    string,
 *   dataset:      "vanilla" | "space-age",
 *   assembler:    1 | 2 | 3,
 *   furnace:      "stone" | "steel" | "electric",
 *   prod_module:  0 | 1 | 2 | 3,
 *   targets:      { [item_id]: number },          // /min
 *   lines:        Line[],
 *   bottlenecks:  string[],
 *   next_steps:   string[],
 *   chat_log:     { from: "player"|"claude", text: string }[],
 * }
 *
 * Line schema:
 * {
 *   item:            string,
 *   target_rate:     number,
 *   effective_rate?: number,   // actual throughput based on placed machines
 *   cli_result?:     object,   // full JSON from python cli.py
 *   actual_machines?: { [machine_key]: number },
 *   player_notes?:   string,
 * }
 */

const { useState, useMemo } = React;

// ── Utilities ────────────────────────────────────────────────────────────────

function clamp(v, lo, hi) {
  return Math.max(lo, Math.min(hi, v));
}

function pct(actual, target) {
  if (!target) return 100;
  return clamp(Math.round((actual / target) * 100), 0, 100);
}

/** Tailored gradient colours for science pack bar fills. */
function scienceGradient(name) {
  const map = {
    // Vanilla
    "automation-science-pack":      ["#a86638", "#c8964a"],
    "logistic-science-pack":        ["#4a8a4a", "#6ab06a"],
    "military-science-pack":        ["#8a3a3a", "#b05050"],
    "chemical-science-pack":        ["#4a5a9a", "#6878c8"],
    "production-science-pack":      ["#8a8a3a", "#b0b050"],
    "utility-science-pack":         ["#3a8a8a", "#50b0b0"],
    "space-science-pack":           ["#7a3a9a", "#a058c8"],
    // Space Age
    "metallurgic-science-pack":     ["#8a3a1a", "#c05830"],  // Vulcanus — volcanic orange
    "agricultural-science-pack":    ["#3a7a18", "#5ab028"],  // Gleba — lime green
    "electromagnetic-science-pack": ["#3a28a0", "#5848d8"],  // Fulgora — electric blue
    "cryogenic-science-pack":       ["#186888", "#28a8c8"],  // Aquilo — ice cyan
    "promethium-science-pack":      ["#4a1070", "#7820b0"],  // Space Platform — void purple
  };
  return map[name] || ["#555", "#888"];
}

/**
 * Canonical research-tree order for sorting science pack bars.
 * Vanilla packs first, then Space Age packs in unlock order.
 */
const SCIENCE_ORDER = [
  "automation-science-pack",
  "logistic-science-pack",
  "military-science-pack",
  "chemical-science-pack",
  "production-science-pack",
  "utility-science-pack",
  "space-science-pack",
  "metallurgic-science-pack",
  "agricultural-science-pack",
  "electromagnetic-science-pack",
  "cryogenic-science-pack",
  "promethium-science-pack",
];

function sortedScienceKeys(keys) {
  return [...keys].sort((a, b) => {
    const ia = SCIENCE_ORDER.indexOf(a);
    const ib = SCIENCE_ORDER.indexOf(b);
    if (ia === -1 && ib === -1) return a.localeCompare(b);
    if (ia === -1) return 1;
    if (ib === -1) return -1;
    return ia - ib;
  });
}

/** Convert kebab-case item ID to human-readable label. */
function label(id) {
  return id
    .replace(/-science-pack$/, " Science")
    .replace(/-/g, " ")
    .replace(/\b\w/g, c => c.toUpperCase());
}

/** Friendly display names for machine IDs. */
const MACHINE_NAMES = {
  "assembling-machine-1":    "Assembler 1",
  "assembling-machine-2":    "Assembler 2",
  "assembling-machine-3":    "Assembler 3",
  "stone-furnace":           "Stone Furnace",
  "steel-furnace":           "Steel Furnace",
  "electric-furnace":        "Electric Furnace",
  "chemical-plant":          "Chemical Plant",
  "oil-refinery":            "Oil Refinery",
  "centrifuge":              "Centrifuge",
  "rocket-silo":             "Rocket Silo",
  "electric-mining-drill":   "Mining Drill",
  "big-mining-drill":        "Big Mining Drill",
  "pumpjack":                "Pumpjack",
  "offshore-pump":           "Offshore Pump",
  // Shorthands Claude may emit in free-text strings
  "AM1": "Assembler 1",
  "AM2": "Assembler 2",
  "AM3": "Assembler 3",
  // Space Age
  "foundry":                 "Foundry",
  "electromagnetic-plant":   "Electromagnetic Plant",
  "electronics-assembly":    "Electronics Assembly",
  "cryogenic-plant":         "Cryogenic Plant",
  "biochamber":              "Biochamber",
  "crusher":                 "Crusher",
  "agricultural-tower":      "Agricultural Tower",
  "captive-spawner":         "Captive Spawner",
};

/**
 * Replace any machine ID tokens inside an arbitrary string with friendly names.
 * Works on both bare IDs and free-text sentences from Claude.
 */
function humanizeText(text) {
  if (!text) return text;
  return String(text).replace(
    /\bAM[123]\b|assembling-machine-[123]|[a-z]+(?:-[a-z0-9]+)+/g,
    token => MACHINE_NAMES[token] || label(token),
  );
}

// ── Science Pack Progress Bar ────────────────────────────────────────────────

function ScienceBar({ name, actual, target }) {
  const p = pct(actual, target);
  const [dark, light] = scienceGradient(name);
  const statusColor = p >= 100 ? "#4eca4e" : p >= 75 ? "#caa040" : "#ca4040";

  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{
        display: "flex", justifyContent: "space-between",
        fontSize: 13, marginBottom: 4, alignItems: "baseline",
      }}>
        <span style={{ fontWeight: 600 }}>{label(name)}</span>
        <span style={{ color: statusColor, fontVariantNumeric: "tabular-nums" }}>
          {actual != null ? actual : "?"}&thinsp;/&thinsp;{target}&thinsp;/min &nbsp;({p}%)
        </span>
      </div>
      <div style={{ background: "#2a2a2a", borderRadius: 4, height: 10, overflow: "hidden" }}>
        <div style={{
          width: `${p}%`, height: "100%",
          background: `linear-gradient(90deg, ${dark}, ${light})`,
          transition: "width 0.4s ease",
        }} />
      </div>
    </div>
  );
}

// ── Machine Table Row ────────────────────────────────────────────────────────

function MachineRow({ step, actualMachines }) {
  const placed = (actualMachines && actualMachines[step.machine] != null) ? actualMachines[step.machine] : null;
  const needed = step.machine_count_ceil;
  const statusColor =
    placed === null ? "#666"
    : placed >= needed ? "#4eca4e"
    : "#ca4040";

  return (
    <tr style={{ borderBottom: "1px solid #222" }}>
      <td style={{ padding: "5px 8px", fontFamily: "monospace", fontSize: 12, color: "#bbb" }}>
        {step.recipe}
      </td>
      <td style={{ padding: "5px 8px", fontSize: 12, color: "#777" }}>
        {humanizeText(step.machine)}
      </td>
      <td style={{ padding: "5px 8px", textAlign: "right", fontSize: 12 }}>
        {placed !== null && (
          <span style={{ color: statusColor, fontWeight: 700 }}>{placed}</span>
        )}
        <span style={{ color: "#555", marginLeft: placed !== null ? 4 : 0 }}>
          {placed !== null ? "/ " : ""}{needed}
        </span>
      </td>
      <td style={{ padding: "5px 8px", textAlign: "right", fontSize: 12, color: "#666" }}>
        {step.rate_per_min != null ? `${(+step.rate_per_min).toFixed(1)}/m` : ""}
      </td>
    </tr>
  );
}

// ── Production Line Card ─────────────────────────────────────────────────────

function LineCard({ line }) {
  const [open, setOpen] = useState(false);

  const steps  = (line.cli_result && line.cli_result.production_steps) || [];
  const belts  = (line.cli_result && line.cli_result.belts_for_output) || {};
  const raw    = (line.cli_result && line.cli_result.raw_resources)    || {};
  const miners = (line.cli_result && line.cli_result.miners_needed)    || {};
  const p      = pct(line.effective_rate != null ? line.effective_rate : (line.target_rate || 0), line.target_rate || 0);

  const headerBg =
    p >= 100 ? "#182818" :
    p >= 75  ? "#28280e" :
               "#28100e";

  const barColor =
    p >= 100 ? "#4eca4e" :
    p >= 75  ? "#caa040" :
               "#ca4040";

  const beltColors = {
    yellow: "#d4a817", red: "#c84040", blue: "#4060c8", turbo: "#40c8b8",
  };

  return (
    <div style={{
      background: "#1a1a1a", border: "1px solid #2e2e2e", borderRadius: 8,
      marginBottom: 10, overflow: "hidden",
    }}>
      {/* Header */}
      <div
        onClick={() => setOpen(o => !o)}
        style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "9px 14px", cursor: "pointer", background: headerBg,
          userSelect: "none",
        }}
      >
        <span style={{ fontWeight: 700, fontSize: 14 }}>{label(line.item)}</span>
        <div style={{ display: "flex", gap: 14, alignItems: "center" }}>
          <span style={{ fontSize: 13, color: "#999" }}>
            {line.effective_rate != null
              ? `${line.effective_rate}`
              : `${line.target_rate}`}/min
          </span>
          <span style={{ fontSize: 13, fontWeight: 700, color: barColor }}>{p}%</span>
          <span style={{ color: "#444", fontSize: 11 }}>{open ? "▲" : "▼"}</span>
        </div>
      </div>

      {/* Thin progress bar */}
      <div style={{ height: 3, background: "#111" }}>
        <div style={{
          width: `${p}%`, height: "100%", background: barColor,
          transition: "width 0.4s ease",
        }} />
      </div>

      {/* Expandable detail */}
      {open && (
        <div style={{ padding: "12px 14px" }}>
          {/* Machines */}
          {steps.length > 0 && (
            <>
              <SectionHeader>Machines</SectionHeader>
              <table style={{ width: "100%", borderCollapse: "collapse", marginBottom: 10 }}>
                <thead>
                  <tr style={{ color: "#444", fontSize: 11 }}>
                    <th style={{ textAlign: "left",  padding: "2px 8px" }}>Recipe</th>
                    <th style={{ textAlign: "left",  padding: "2px 8px" }}>Machine</th>
                    <th style={{ textAlign: "right", padding: "2px 8px" }}>Placed/Need</th>
                    <th style={{ textAlign: "right", padding: "2px 8px" }}>Rate</th>
                  </tr>
                </thead>
                <tbody>
                  {steps.map(s => (
                    <MachineRow key={s.recipe} step={s} actualMachines={line.actual_machines} />
                  ))}
                </tbody>
              </table>
            </>
          )}

          {/* Raw resources */}
          {Object.keys(raw).length > 0 && (
            <>
              <SectionHeader>Raw Resources</SectionHeader>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 10 }}>
                {Object.entries(raw).map(([res, rate]) => (
                  <div key={res} style={{
                    background: "#111", borderRadius: 4, padding: "3px 10px",
                    fontSize: 12, fontFamily: "monospace", color: "#aaa",
                  }}>
                    {res}: <span style={{ color: "#ddd" }}>{(+rate).toFixed(2)}/min</span>
                  </div>
                ))}
              </div>
            </>
          )}

          {/* Belts */}
          {Object.keys(belts).length > 0 && (
            <>
              <SectionHeader>Belts for Output</SectionHeader>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 10 }}>
                {Object.entries(belts).map(([color, info]) => (
                  <div key={color} style={{
                    background: "#111", borderRadius: 4, padding: "3px 10px", fontSize: 12,
                  }}>
                    <span style={{ color: beltColors[color] || "#aaa", fontWeight: 700 }}>{color}</span>
                    {": "}
                    <span style={{ color: "#ccc" }}>{info.belts_needed?.toFixed(3)} lanes</span>
                  </div>
                ))}
              </div>
            </>
          )}

          {/* Miners / extractors */}
          {Object.keys(miners).length > 0 && (
            <>
              <SectionHeader>Miners / Extractors</SectionHeader>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 10 }}>
                {Object.entries(miners).map(([res, info]) => {
                  const isYield   = info.required_yield_pct != null;
                  const countText = isYield
                    ? `${info.required_yield_pct.toFixed(1)}% yield`
                    : `${info.machine_count_ceil}×`;
                  const machineLabel = humanizeText(info.machine);
                  return (
                    <div key={res} style={{
                      background: "#111", borderRadius: 4, padding: "3px 10px",
                      fontSize: 12, fontFamily: "monospace", color: "#aaa",
                    }}>
                      {res}:{" "}
                      <span style={{ color: isYield ? "#c8a040" : "#ddd", fontWeight: 600 }}>
                        {countText}
                      </span>
                      <span style={{ color: "#555" }}> {machineLabel}</span>
                      <span style={{ color: "#666" }}> ({(+info.rate_per_min).toFixed(1)}/min)</span>
                    </div>
                  );
                })}
              </div>
            </>
          )}

          {/* Notes */}
          {line.player_notes && (
            <div style={{ fontSize: 12, color: "#555", fontStyle: "italic" }}>
              {line.player_notes}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Chat Log ─────────────────────────────────────────────────────────────────

function ChatLog({ log }) {
  if (!log || log.length === 0) {
    return (
      <div style={{ color: "#444", fontSize: 13, textAlign: "center", padding: 24 }}>
        No conversation logged yet.
      </div>
    );
  }
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {log.map((entry, i) => {
        const isPlayer = entry.from === "player";
        return (
          <div key={i} style={{
            alignSelf: isPlayer ? "flex-end" : "flex-start",
            maxWidth: "82%",
            background: isPlayer ? "#182838" : "#1e1e30",
            border: `1px solid ${isPlayer ? "#2a4a6a" : "#2a2a5a"}`,
            borderRadius: 8,
            padding: "7px 12px",
          }}>
            <div style={{ fontSize: 11, color: "#555", marginBottom: 3 }}>
              {isPlayer ? "You" : "Claude"}
            </div>
            <div style={{ fontSize: 13, color: "#ccc", lineHeight: 1.5 }}>
              {entry.text}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Shared ───────────────────────────────────────────────────────────────────

function SectionHeader({ children }) {
  return (
    <div style={{
      fontSize: 11, color: "#555", textTransform: "uppercase",
      letterSpacing: 1, marginBottom: 6,
    }}>
      {children}
    </div>
  );
}

function Tab({ id, label: text, active, badge, onClick }) {
  return (
    <button
      onClick={() => onClick(id)}
      style={{
        background: active ? "#222240" : "#1a1a1a",
        border: `1px solid ${active ? "#40408a" : "#2e2e2e"}`,
        color: active ? "#aaaaf0" : "#666",
        borderRadius: 6, padding: "5px 14px",
        cursor: "pointer", fontSize: 13,
        fontWeight: active ? 700 : 400,
        transition: "all 0.15s",
      }}
    >
      {text}{badge ? ` (${badge})` : ""}
    </button>
  );
}

// ── Dashboard Root ────────────────────────────────────────────────────────────

export default function FactoryDashboard() {
  /* FACTORY_STATE must be defined in the outer scope before this component. */
  const state = typeof FACTORY_STATE !== "undefined" ? FACTORY_STATE : {};

  const {
    save_name   = "My Factory",
    dataset     = "vanilla",
    assembler   = 3,
    furnace     = "electric",
    prod_module = 0,
    targets     = {},
    lines       = [],
    bottlenecks = [],
    next_steps  = [],
    chat_log    = [],
  } = state;

  /* Derive actual science-pack rates from lines (effective_rate if available). */
  const scienceRates = useMemo(() => {
    const rates = {};
    for (const line of lines) {
      if (line.item in targets) {
        rates[line.item] = line.effective_rate != null ? line.effective_rate : (line.target_rate || 0);
      }
    }
    return rates;
  }, [lines, targets]);

  const scienceItems = sortedScienceKeys(Object.keys(targets));
  const [tab, setTab] = useState("overview");

  return (
    <div style={{
      fontFamily: "'Segoe UI', system-ui, sans-serif",
      background: "#111", color: "#e0e0e0",
      minHeight: "100vh", padding: "16px 20px",
      boxSizing: "border-box",
    }}>

      {/* ── Header ── */}
      <div style={{ marginBottom: 18 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 5 }}>
          {/* Brand */}
          <span style={{ fontSize: 13, fontWeight: 700, color: "#888", letterSpacing: 0.3 }}>
            10x Factorio Engineer
          </span>
          {/* Config pills */}
          <div style={{ display: "flex", gap: 5, flexWrap: "wrap", justifyContent: "flex-end" }}>
            {dataset === "space-age" && (
              <span style={{
                background: "#1a1020", border: "1px solid #6030a0",
                borderRadius: 4, padding: "2px 8px",
                fontSize: 11, fontWeight: 700, color: "#a060e0",
              }}>Space Age</span>
            )}
            <span style={{ background: "#1a1a1a", border: "1px solid #2e2e2e", borderRadius: 4, padding: "2px 8px", fontSize: 11, color: "#666" }}>
              Assembler {assembler}
            </span>
            <span style={{ background: "#1a1a1a", border: "1px solid #2e2e2e", borderRadius: 4, padding: "2px 8px", fontSize: 11, color: "#666" }}>
              {furnace.charAt(0).toUpperCase() + furnace.slice(1)} Furnace
            </span>
            {prod_module > 0 && (
              <span style={{ background: "#1a1a1a", border: "1px solid #2e2e2e", borderRadius: 4, padding: "2px 8px", fontSize: 11, color: "#666" }}>
                Productivity {prod_module}
              </span>
            )}
          </div>
        </div>
        {/* Save name */}
        <div style={{ fontSize: 11, color: "#3a3a3a" }}>{save_name}</div>
      </div>

      {/* ── Science packs ── */}
      {scienceItems.length > 0 && (
        <div style={{
          background: "#181818", border: "1px solid #242424", borderRadius: 8,
          padding: "14px 16px", marginBottom: 14,
        }}>
          <SectionHeader>Science Packs</SectionHeader>
          {scienceItems.map(name => (
            <ScienceBar
              key={name}
              name={name}
              actual={scienceRates[name]}
              target={targets[name]}
            />
          ))}
        </div>
      )}

      {/* ── Bottleneck banner ── */}
      {bottlenecks.length > 0 && (
        <div style={{
          background: "#2a1010", border: "1px solid #5a2020", borderRadius: 8,
          padding: "10px 14px", marginBottom: 14,
        }}>
          <div style={{ fontSize: 12, color: "#ca4040", fontWeight: 700, marginBottom: 6 }}>
            ⚠ BOTTLENECKS — {bottlenecks.length} issue{bottlenecks.length !== 1 ? "s" : ""}
          </div>
          {bottlenecks.map((b, i) => (
            <div key={i} style={{ fontSize: 13, color: "#d08080", marginBottom: 3 }}>
              • {humanizeText(b)}
            </div>
          ))}
        </div>
      )}

      {/* ── Tabs ── */}
      <div style={{ display: "flex", gap: 6, marginBottom: 14, flexWrap: "wrap" }}>
        <Tab id="overview" label="Overview"    active={tab === "overview"}    onClick={setTab} />
        <Tab id="lines"    label="Lines"       active={tab === "lines"}       badge={lines.length} onClick={setTab} />
        <Tab id="issues"   label="Issues"      active={tab === "issues"}      badge={bottlenecks.length || undefined} onClick={setTab} />
        <Tab id="chat"     label="Chat Log"    active={tab === "chat"}        badge={chat_log.length || undefined} onClick={setTab} />
      </div>

      {/* ── Tab: Overview ── */}
      {tab === "overview" && (
        <div>
          {lines.length === 0 ? (
            <div style={{ color: "#444", fontSize: 14, textAlign: "center", padding: "32px 0" }}>
              No production lines tracked yet.<br />
              <span style={{ fontSize: 12, color: "#333" }}>
                Describe what you're building to Claude and it will log lines here.
              </span>
            </div>
          ) : (
            lines.map(line => {
              const p = pct(line.effective_rate != null ? line.effective_rate : (line.target_rate || 0), line.target_rate || 0);
              const barColor = p >= 100 ? "#4eca4e" : p >= 75 ? "#caa040" : "#ca4040";
              return (
                <div key={line.item} style={{
                  display: "flex", justifyContent: "space-between", alignItems: "center",
                  padding: "8px 14px", background: "#181818",
                  border: `1px solid ${p >= 100 ? "#1a361a" : p >= 75 ? "#36360a" : "#36100a"}`,
                  borderRadius: 6, marginBottom: 6,
                }}>
                  <span style={{ fontSize: 14, fontWeight: 600 }}>{label(line.item)}</span>
                  <div style={{ display: "flex", gap: 14, alignItems: "center" }}>
                    <span style={{ fontSize: 13, color: "#666" }}>target {line.target_rate}/min</span>
                    <span style={{ fontSize: 14, fontWeight: 700, color: barColor }}>{p}%</span>
                  </div>
                </div>
              );
            })
          )}

          {next_steps.length > 0 && (
            <div style={{ marginTop: 16 }}>
              <SectionHeader>Next Steps</SectionHeader>
              {next_steps.map((s, i) => (
                <div key={i} style={{
                  padding: "8px 14px", background: "#142014",
                  border: "1px solid #244024", borderRadius: 6,
                  marginBottom: 6, fontSize: 13, color: "#80c080",
                }}>
                  →&ensp;{humanizeText(s)}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Tab: Lines ── */}
      {tab === "lines" && (
        <div>
          {lines.length === 0 ? (
            <div style={{ color: "#444", fontSize: 14, textAlign: "center", padding: "32px 0" }}>
              No lines yet. Ask Claude to plan a production line.
            </div>
          ) : (
            lines.map(line => <LineCard key={line.item} line={line} />)
          )}
        </div>
      )}

      {/* ── Tab: Issues ── */}
      {tab === "issues" && (
        <div>
          {bottlenecks.length === 0 && next_steps.length === 0 ? (
            <div style={{ color: "#4eca4e", fontSize: 14, textAlign: "center", padding: "32px 0" }}>
              ✓ No bottlenecks detected.
            </div>
          ) : (
            <>
              {bottlenecks.map((b, i) => (
                <div key={i} style={{
                  padding: "8px 14px", background: "#2a1010",
                  border: "1px solid #5a2020", borderRadius: 6,
                  marginBottom: 6, fontSize: 13, color: "#d08080",
                }}>
                  ⚠&ensp;{humanizeText(b)}
                </div>
              ))}
              {next_steps.map((s, i) => (
                <div key={`ns${i}`} style={{
                  padding: "8px 14px", background: "#142014",
                  border: "1px solid #244024", borderRadius: 6,
                  marginBottom: 6, fontSize: 13, color: "#80c080",
                }}>
                  →&ensp;{humanizeText(s)}
                </div>
              ))}
            </>
          )}
        </div>
      )}

      {/* ── Tab: Chat Log ── */}
      {tab === "chat" && (
        <div style={{ maxHeight: 480, overflowY: "auto" }}>
          <ChatLog log={chat_log} />
        </div>
      )}
    </div>
  );
}
