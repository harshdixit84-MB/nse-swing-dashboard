import { useEffect, useMemo, useState } from "react";

// ---- Replace these two lines with your own GitHub username/repo ----
const GITHUB_USER = "YOUR_GITHUB_USERNAME";
const GITHUB_REPO = "YOUR_REPO_NAME";
// ----------------------------------------------------------------------

const CANDIDATES_URL = `https://raw.githubusercontent.com/${GITHUB_USER}/${GITHUB_REPO}/main/data/candidates.json`;
const HISTORY_URL = `https://raw.githubusercontent.com/${GITHUB_USER}/${GITHUB_REPO}/main/data/history.json`;

const SORT_OPTIONS = [
  { key: "rr", label: "Reward : Risk" },
  { key: "pullback", label: "Pullback %" },
  { key: "symbol", label: "Symbol (A-Z)" },
];

function useMarketStatus() {
  const [status, setStatus] = useState({ open: false, label: "Checking..." });

  useEffect(() => {
    const check = () => {
      const now = new Date();
      const ist = new Date(now.toLocaleString("en-US", { timeZone: "Asia/Kolkata" }));
      const day = ist.getDay();
      const minutes = ist.getHours() * 60 + ist.getMinutes();
      const isWeekday = day >= 1 && day <= 5;
      const isMarketHours = minutes >= 9 * 60 + 15 && minutes <= 15 * 60 + 30;
      const open = isWeekday && isMarketHours;
      setStatus({ open, label: open ? "Market Open" : "Market Closed" });
    };
    check();
    const id = setInterval(check, 60000);
    return () => clearInterval(id);
  }, []);

  return status;
}

function RiskBar({ stop, entry, target }) {
  const total = target - stop;
  if (total <= 0) return null;
  const lossPct = ((entry - stop) / total) * 100;
  const gainPct = ((target - entry) / total) * 100;

  return (
    <div className="riskbar-cell">
      <div className="riskbar">
        <div className="riskbar-loss" style={{ width: `${lossPct}%` }} />
        <div className="riskbar-gain" style={{ width: `${gainPct}%` }} />
        <div className="riskbar-marker" style={{ left: `${lossPct}%` }} />
      </div>
      <div className="riskbar-caption">
        ₹{stop.toFixed(1)} &rarr; ₹{entry.toFixed(1)} &rarr; ₹{target.toFixed(1)}
      </div>
    </div>
  );
}

function ChartLink({ symbol }) {
  return (
    <a
      className="chart-link"
      href={`https://www.tradingview.com/chart/?symbol=NSE:${symbol}`}
      target="_blank"
      rel="noopener noreferrer"
      title={`Open ${symbol} on TradingView`}
    >
      Chart
      <svg width="11" height="11" viewBox="0 0 24 24" fill="none">
        <path
          d="M7 17L17 7M17 7H9M17 7V15"
          stroke="currentColor"
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </a>
  );
}

export default function Home() {
  const [data, setData] = useState(null);
  const [historyCount, setHistoryCount] = useState(null);
  const [error, setError] = useState(null);
  const [sortKey, setSortKey] = useState("rr");
  const market = useMarketStatus();

  useEffect(() => {
    fetch(CANDIDATES_URL, { cache: "no-store" })
      .then((res) => res.json())
      .then(setData)
      .catch(() => setError(true));

    fetch(HISTORY_URL, { cache: "no-store" })
      .then((res) => res.json())
      .then((json) => setHistoryCount(json.entries?.length ?? 0))
      .catch(() => {});
  }, []);

  const candidates = data?.candidates ?? [];

  const sorted = useMemo(() => {
    const copy = [...candidates];
    if (sortKey === "rr") copy.sort((a, b) => b.reward_risk_ratio - a.reward_risk_ratio);
    if (sortKey === "pullback") copy.sort((a, b) => b.pullback_pct - a.pullback_pct);
    if (sortKey === "symbol") copy.sort((a, b) => a.symbol.localeCompare(b.symbol));
    return copy;
  }, [candidates, sortKey]);

  const avgRR =
    candidates.length > 0
      ? (
          candidates.reduce((sum, c) => sum + c.reward_risk_ratio, 0) /
          candidates.length
        ).toFixed(2)
      : "--";

  const bestRR =
    candidates.length > 0
      ? Math.max(...candidates.map((c) => c.reward_risk_ratio)).toFixed(2)
      : "--";

  return (
    <div className="page">
      <div className="accent-bar" />

      <div className="masthead">
        <div className="masthead-top">
          <div>
            <h1>NSE Swing Board</h1>
            <p>EMA Pullback setups, scanned daily after market close</p>
          </div>
          <div className={`market-badge ${market.open ? "is-open" : "is-closed"}`}>
            <span className="dot" />
            {market.label}
          </div>
        </div>
      </div>

      <div className="ticker-strip">
        <div className="ticker-item">
          <div className="ticker-label">Last Scan</div>
          <div className="ticker-value">{data?.scan_date ?? "--"}</div>
        </div>
        <div className="ticker-item">
          <div className="ticker-label">Setups Today</div>
          <div className="ticker-value">{candidates.length}</div>
        </div>
        <div className="ticker-item">
          <div className="ticker-label">Avg Reward:Risk</div>
          <div className="ticker-value">{avgRR}</div>
        </div>
        <div className="ticker-item">
          <div className="ticker-label">Best Reward:Risk</div>
          <div className="ticker-value accent">{bestRR}</div>
        </div>
        <div className="ticker-item">
          <div className="ticker-label">All-Time Setups</div>
          <div className="ticker-value">{historyCount ?? "--"}</div>
        </div>
      </div>

      <div className="table-wrap">
        {candidates.length > 0 && (
          <div className="controls">
            <span className="controls-label">Sort by</span>
            {SORT_OPTIONS.map((opt) => (
              <button
                key={opt.key}
                className={`sort-btn ${sortKey === opt.key ? "active" : ""}`}
                onClick={() => setSortKey(opt.key)}
              >
                {opt.label}
              </button>
            ))}
          </div>
        )}

        {error && (
          <div className="empty-state">
            <h2>Data not reachable</h2>
            <p>
              Couldn&apos;t load candidates.json from GitHub. Check that
              GITHUB_USER / GITHUB_REPO in pages/index.js match your repo,
              and that it&apos;s public.
            </p>
          </div>
        )}

        {!error && data && candidates.length === 0 && (
          <div className="empty-state">
            <h2>No setups found yet</h2>
            <p>
              The scanner runs daily after market close. Check back after
              4:00 PM IST, or trigger the workflow manually from the
              GitHub Actions tab.
            </p>
          </div>
        )}

        {sorted.length > 0 && (
          <>
            <div className="col-headers">
              <div>Symbol</div>
              <div>Entry</div>
              <div>Stop</div>
              <div>Target</div>
              <div>Risk / Reward</div>
              <div>Pullback</div>
              <div></div>
            </div>
            {sorted.map((c) => (
              <div className="row" key={c.symbol}>
                <div>
                  <div className="symbol">{c.symbol}</div>
                  <div className="pattern">{c.pattern}</div>
                </div>
                <div className="num entry" data-label="Entry">
                  ₹{c.entry_price}
                </div>
                <div className="num stop" data-label="Stop">
                  ₹{c.stop_loss}
                </div>
                <div className="num target" data-label="Target">
                  ₹{c.target}
                </div>
                <RiskBar stop={c.stop_loss} entry={c.entry_price} target={c.target} />
                <div className="num" data-label="Pullback">
                  {c.pullback_pct}%
                </div>
                <ChartLink symbol={c.symbol} />
              </div>
            ))}
          </>
        )}
      </div>

      <div className="footer">
        <p>
          Educational tool only — not investment advice. Verify every setup
          yourself before trading. Past performance of a strategy does not
          guarantee future results.
        </p>
      </div>
    </div>
  );
}
