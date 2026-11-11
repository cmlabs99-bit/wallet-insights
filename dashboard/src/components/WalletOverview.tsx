import { useQuery } from "@tanstack/react-query";
import { fetchSnapshot } from "../api";
import { eth, short, when } from "../format";

export function WalletOverview({ address }: { address: `0x${string}` }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["snapshot", address],
    queryFn: () => fetchSnapshot(address),
  });

  return (
    <section className="card span2">
      <h2>Overview</h2>
      {isLoading && <p className="muted">Reading the chain…</p>}
      {error && <p className="error">{(error as Error).message}</p>}
      {data && (
        <>
          <div className="stats">
            <div>
              <span className="stat-label">Balance</span>
              <span className="stat">{eth(data.balance_eth)}</span>
            </div>
            <div>
              <span className="stat-label">Lifetime transactions</span>
              <span className="stat">{data.tx_count}</span>
            </div>
            <div>
              <span className="stat-label">Chain</span>
              <span className="stat">{data.chain_id}</span>
            </div>
          </div>

          {data.note && <p className="muted">{data.note}</p>}

          {data.transactions.length > 0 && (
            <table className="txs">
              <thead>
                <tr>
                  <th>When</th>
                  <th>Direction</th>
                  <th>Counterparty</th>
                  <th>Value</th>
                  <th>Method</th>
                </tr>
              </thead>
              <tbody>
                {data.transactions.slice(0, 10).map((t) => {
                  const out = t.from_address.toLowerCase() === address.toLowerCase();
                  const other = out ? t.to_address : t.from_address;
                  return (
                    <tr key={t.hash} className={t.failed ? "failed" : ""}>
                      <td>{when(t.timestamp)}</td>
                      <td>{out ? "out" : "in"}</td>
                      <td>
                        <code>{other ? short(other) : "contract creation"}</code>
                      </td>
                      <td>{t.value_eth > 0 ? eth(t.value_eth) : "—"}</td>
                      <td>
                        {t.method ?? (t.is_contract_interaction ? "call" : "transfer")}
                        {t.failed && " (failed)"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </>
      )}
    </section>
  );
}
