import { useReadContract } from "wagmi";
import { insightRegistryAbi } from "../contract";
import { when } from "../format";

type Props = { address: `0x${string}`; registry?: `0x${string}` };

type Insight = { reportHash: `0x${string}`; uri: string; savedAt: bigint; riskScore: number };

export function SavedReports({ address, registry }: Props) {
  const { data, isLoading, error } = useReadContract({
    abi: insightRegistryAbi,
    address: registry,
    functionName: "latestInsights",
    args: [address, 10n],
    query: { enabled: Boolean(registry) },
  });

  const items = (data as Insight[] | undefined) ?? [];

  return (
    <section className="card span2">
      <h2>Saved on-chain</h2>
      {!registry && <p className="muted">Deploy InsightRegistry on this chain to enable saving.</p>}
      {isLoading && <p className="muted">Reading contract…</p>}
      {error && <p className="error">{error.message.split("\n")[0]}</p>}
      {registry && !isLoading && items.length === 0 && (
        <p className="muted">Nothing saved yet. Run an analysis and save its hash.</p>
      )}
      {items.length > 0 && (
        <table className="txs">
          <thead>
            <tr>
              <th>Saved</th>
              <th>Risk</th>
              <th>Report hash</th>
              <th>URI</th>
            </tr>
          </thead>
          <tbody>
            {items.map((it) => (
              <tr key={it.reportHash + it.savedAt.toString()}>
                <td>{when(it.savedAt)}</td>
                <td>{it.riskScore}</td>
                <td>
                  <code>{it.reportHash.slice(0, 12)}…</code>
                </td>
                <td>{it.uri || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
