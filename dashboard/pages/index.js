import { useEffect, useState } from "react";

// ---- Replace these two lines with your own GitHub username/repo ----
const GITHUB_USER = "YOUR_GITHUB_USERNAME";
const GITHUB_REPO = "YOUR_REPO_NAME";
// ----------------------------------------------------------------------

const CANDIDATES_URL = `https://raw.githubusercontent.com/${GITHUB_USER}/${GITHUB_REPO}/main/data/candidates.json`;
const HISTORY_URL = `https://raw.githubusercontent.com/${GITHUB_USER}/${GITHUB_REPO}/main/data/history.json`;

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
        {stop.toFixed(1)} &rarr; {entry.toFixed(1)} &rarr; {target.toFixed(1)}
      </div>
    </div>
  );
}

export default function Home() {
  const [data, setData] = useState(null);
  const [historyCount, setHistoryCount] = useState(null);
  const [error, setError] = useState(null);

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
  const avgRR =
    candidates.length > 0
      ? (
          candidates.reduce((sum, c) => sum + c.reward_risk_ratio, 0) /
          candidates.length
        ).toFixed(2)
      : "--";

  return (
    <div className="page">
      <div className="masthead">
        <h1>NSE Swing Board</h1>
        <p>EMA Pullback setups, scanned daily after market close</p>
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
          <div className="ticker-label">All-Time Setups</div>
          <div className="ticker-value">{historyCount ?? "--"}</div>
        </div>
      </div>

      <div className="table-wrap">
        {error && (
          <div className="empty-state">
            <h2>Data not reachable</h2>
            <p>
              Couldn&apos;t load candidates.json from GitHub. Check that
              GITHUB_USER / GITHUB_REPO in pages/index.js match your repo,
              and that it&apos;s public (or add a fetch token for private repos).
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

        {candidates.length > 0 && (
          <>
            <div className="col-headers">
              <div>Symbol</div>
              <div>Entry</div>
              <div>Stop</div>
              <div>Target</div>
              <div>Risk / Reward</div>
              <div>Pullback</div>
            </div>
            {candidates
              .slice()
              .sort((a, b) => b.reward_risk_ratio - a.reward_risk_ratio)
              .map((c) => (
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
                  <RiskBar
                    stop={c.stop_loss}
                    entry={c.entry_price}
                    target={c.target}
                  />
                  <div className="num" data-label="Pullback">
                    {c.pullback_pct}%
                  </div>
                </div>
              ))}
          </>
        )}
      </div>
    </div>
  );
}
