import { useAccount, useConnect, useDisconnect } from "wagmi";
import { short } from "../format";

export function ConnectButton() {
  const { address, isConnected } = useAccount();
  const { connect, connectors, isPending, error } = useConnect();
  const { disconnect } = useDisconnect();

  if (isConnected && address) {
    return (
      <div className="connect">
        <span className="pill">{short(address)}</span>
        <button className="btn ghost" onClick={() => disconnect()}>
          Disconnect
        </button>
      </div>
    );
  }

  // `injected` is the browser wallet (MetaMask, Rabby, Brave...). We only registered one connector.
  const injected = connectors[0];
  return (
    <div className="connect">
      <button className="btn" disabled={!injected || isPending} onClick={() => connect({ connector: injected })}>
        {isPending ? "Connecting…" : "Connect wallet"}
      </button>
      {error && <span className="error">{error.message}</span>}
    </div>
  );
}
