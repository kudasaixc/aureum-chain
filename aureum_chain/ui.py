from __future__ import annotations

from textwrap import dedent


def render_ui() -> str:
    return dedent(
        """
        <!DOCTYPE html>
        <html lang="en">
          <head>
            <meta charset="utf-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1" />
            <title>Aureum Chain Core UI</title>
            <style>
              :root {
                color-scheme: dark;
                --bg: #0d1117;
                --panel: #161b22;
                --muted: #8b949e;
                --text: #e6edf3;
                --accent: #f2a900;
                --border: #30363d;
                --success: #3fb950;
                --danger: #f85149;
              }

              * {
                box-sizing: border-box;
              }

              body {
                margin: 0;
                font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
                background: var(--bg);
                color: var(--text);
              }

              header {
                padding: 24px 32px;
                border-bottom: 1px solid var(--border);
                background: linear-gradient(120deg, #1f232b, #0d1117 70%);
              }

              h1 {
                margin: 0 0 8px 0;
                font-size: 28px;
                font-weight: 600;
              }

              p {
                margin: 0;
                color: var(--muted);
              }

              main {
                padding: 24px 32px 48px;
                display: grid;
                gap: 20px;
                grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
              }

              section {
                background: var(--panel);
                border: 1px solid var(--border);
                border-radius: 12px;
                padding: 20px;
                box-shadow: 0 12px 30px rgba(0, 0, 0, 0.2);
              }

              section h2 {
                margin-top: 0;
                font-size: 18px;
                font-weight: 600;
              }

              label {
                display: block;
                margin: 12px 0 6px;
                color: var(--muted);
                font-size: 13px;
              }

              input,
              textarea,
              button {
                width: 100%;
                border-radius: 8px;
                border: 1px solid var(--border);
                background: #0d1117;
                color: var(--text);
                padding: 10px 12px;
                font-size: 14px;
              }

              textarea {
                min-height: 120px;
                resize: vertical;
                font-family: "JetBrains Mono", "Fira Code", monospace;
              }

              button {
                cursor: pointer;
                background: linear-gradient(135deg, #f2a900, #d18400);
                color: #111;
                font-weight: 600;
                border: none;
                margin-top: 12px;
              }

              button.secondary {
                background: transparent;
                border: 1px solid var(--accent);
                color: var(--accent);
              }

              .stat-grid {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 12px;
                margin-top: 12px;
              }

              .stat {
                padding: 12px;
                border-radius: 10px;
                border: 1px solid var(--border);
                background: #0b0f14;
              }

              .stat span {
                display: block;
                font-size: 12px;
                color: var(--muted);
              }

              .stat strong {
                font-size: 15px;
                word-break: break-all;
              }

              .output {
                margin-top: 12px;
                padding: 12px;
                border-radius: 8px;
                border: 1px solid var(--border);
                background: #0b0f14;
                font-size: 12px;
                white-space: pre-wrap;
                min-height: 48px;
              }

              .status-pill {
                display: inline-flex;
                align-items: center;
                gap: 6px;
                font-size: 12px;
                margin-top: 12px;
                color: var(--success);
              }

              .status-pill.offline {
                color: var(--danger);
              }

              .muted {
                color: var(--muted);
              }

              .row {
                display: flex;
                gap: 12px;
                flex-wrap: wrap;
                margin-top: 12px;
              }

              .row button {
                flex: 1;
              }
            </style>
          </head>
          <body>
            <header>
              <h1>Aureum Chain Core UI</h1>
              <p>Manage mining, wallets, peers, and transactions without CLI commands.</p>
              <div class="status-pill" id="node-status">● Connecting…</div>
            </header>
            <main>
              <section>
                <h2>Node Status</h2>
                <div class="stat-grid">
                  <div class="stat"><span>Height</span><strong id="stat-height">-</strong></div>
                  <div class="stat"><span>Mempool</span><strong id="stat-mempool">-</strong></div>
                  <div class="stat"><span>Last Hash</span><strong id="stat-hash">-</strong></div>
                  <div class="stat"><span>Peers</span><strong id="stat-peers">-</strong></div>
                </div>
                <div class="row">
                  <button class="secondary" id="refresh-status">Refresh</button>
                  <button class="secondary" id="sync-chain">Sync Now</button>
                </div>
                <div class="output" id="sync-output">Sync status will appear here.</div>
              </section>

              <section>
                <h2>Mine a Block</h2>
                <label for="mine-address">Miner Address</label>
                <input id="mine-address" placeholder="Aureum address" />
                <button id="mine-btn">Start Mining</button>
                <div class="output" id="mine-output">Mining output will appear here.</div>
              </section>

              <section>
                <h2>Wallet Check</h2>
                <label for="wallet-address">Wallet Address</label>
                <input id="wallet-address" placeholder="Aureum address" />
                <button id="wallet-btn">Load UTXOs</button>
                <div class="output" id="wallet-output">Wallet UTXOs will appear here.</div>
              </section>

              <section>
                <h2>Peers</h2>
                <label for="peers-input">Add Peers (comma-separated URLs)</label>
                <input id="peers-input" placeholder="http://127.0.0.1:8333" />
                <button id="peers-btn">Save Peers</button>
                <div class="output" id="peers-output">Current peers will appear here.</div>
              </section>

              <section>
                <h2>Submit Transaction</h2>
                <p class="muted">Paste a full transaction JSON payload to send it to the node.</p>
                <label for="tx-input">Transaction JSON</label>
                <textarea id="tx-input" placeholder='{"inputs": [], "outputs": [], "locktime": 0}'></textarea>
                <button id="tx-btn">Broadcast Transaction</button>
                <div class="output" id="tx-output">Transaction response will appear here.</div>
              </section>
            </main>

            <script>
              const statusEl = document.getElementById("node-status");
              const heightEl = document.getElementById("stat-height");
              const mempoolEl = document.getElementById("stat-mempool");
              const hashEl = document.getElementById("stat-hash");
              const peersEl = document.getElementById("stat-peers");
              const syncOutput = document.getElementById("sync-output");
              const mineOutput = document.getElementById("mine-output");
              const walletOutput = document.getElementById("wallet-output");
              const peersOutput = document.getElementById("peers-output");
              const txOutput = document.getElementById("tx-output");

              async function loadStatus() {
                try {
                  const response = await fetch("/status");
                  if (!response.ok) {
                    throw new Error("Status request failed");
                  }
                  const data = await response.json();
                  heightEl.textContent = data.height;
                  mempoolEl.textContent = data.mempool;
                  hashEl.textContent = data.last_hash;
                  peersEl.textContent = data.peers.length;
                  statusEl.textContent = "● Online";
                  statusEl.classList.remove("offline");
                } catch (err) {
                  statusEl.textContent = "● Offline";
                  statusEl.classList.add("offline");
                }
              }

              async function syncChain() {
                syncOutput.textContent = "Syncing...";
                try {
                  const response = await fetch("/sync", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({}),
                  });
                  const data = await response.json();
                  syncOutput.textContent = JSON.stringify(data, null, 2);
                  loadStatus();
                } catch (err) {
                  syncOutput.textContent = "Sync failed: " + err.message;
                }
              }

              async function mineBlock() {
                const address = document.getElementById("mine-address").value.trim();
                if (!address) {
                  mineOutput.textContent = "Please enter a miner address.";
                  return;
                }
                mineOutput.textContent = "Mining...";
                try {
                  const response = await fetch("/mine", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ address }),
                  });
                  const data = await response.json();
                  mineOutput.textContent = JSON.stringify(data, null, 2);
                  loadStatus();
                } catch (err) {
                  mineOutput.textContent = "Mining failed: " + err.message;
                }
              }

              async function loadWallet() {
                const address = document.getElementById("wallet-address").value.trim();
                if (!address) {
                  walletOutput.textContent = "Please enter a wallet address.";
                  return;
                }
                walletOutput.textContent = "Loading...";
                try {
                  const response = await fetch(`/utxos/${encodeURIComponent(address)}`);
                  const data = await response.json();
                  walletOutput.textContent = JSON.stringify(data, null, 2);
                } catch (err) {
                  walletOutput.textContent = "Wallet lookup failed: " + err.message;
                }
              }

              async function savePeers() {
                const peersRaw = document.getElementById("peers-input").value;
                const peers = peersRaw
                  .split(",")
                  .map((peer) => peer.trim())
                  .filter(Boolean);
                if (peers.length === 0) {
                  peersOutput.textContent = "Please enter at least one peer URL.";
                  return;
                }
                peersOutput.textContent = "Saving peers...";
                try {
                  const response = await fetch("/peers/add", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ peers }),
                  });
                  const data = await response.json();
                  peersOutput.textContent = JSON.stringify(data, null, 2);
                  loadStatus();
                } catch (err) {
                  peersOutput.textContent = "Peer update failed: " + err.message;
                }
              }

              async function submitTransaction() {
                const txText = document.getElementById("tx-input").value;
                if (!txText.trim()) {
                  txOutput.textContent = "Please paste a transaction JSON payload.";
                  return;
                }
                try {
                  const payload = JSON.parse(txText);
                  txOutput.textContent = "Broadcasting...";
                  const response = await fetch("/transactions/new", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload),
                  });
                  const data = await response.json();
                  txOutput.textContent = JSON.stringify(data, null, 2);
                  loadStatus();
                } catch (err) {
                  txOutput.textContent = "Transaction failed: " + err.message;
                }
              }

              document.getElementById("refresh-status").addEventListener("click", loadStatus);
              document.getElementById("sync-chain").addEventListener("click", syncChain);
              document.getElementById("mine-btn").addEventListener("click", mineBlock);
              document.getElementById("wallet-btn").addEventListener("click", loadWallet);
              document.getElementById("peers-btn").addEventListener("click", savePeers);
              document.getElementById("tx-btn").addEventListener("click", submitTransaction);

              loadStatus();
              setInterval(loadStatus, 10000);
            </script>
          </body>
        </html>
        """
    ).strip()
