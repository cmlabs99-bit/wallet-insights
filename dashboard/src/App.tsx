import { useAccount, useChainId, useSwitchChain } from "wagmi";
import { ConnectButton } from "./components/ConnectButton";
import { WalletOverview } from "./components/WalletOverview";
import { InsightPanel } from "./components/InsightPanel";
import { SavedReports } from "./components/SavedReports";
import { registryAddress } from "./contract";
import { hardhat } from "wagmi/chains";
// ...inside App():

export default function App() {
    const { address, isConnected, chainId: walletChainId } = useAccount();
    const chainId = useChainId();
    const wrongChain = isConnected && walletChainId !== chainId;

    const registry = registryAddress(chainId);
    const { switchChain, isPending: isSwitching } = useSwitchChain();

    return (
        <div className="shell">
            <header className="topbar">
                <div>
                    <h1 className="brand">Wallet Insights</h1>
                    <p className="tagline">
                        AI-written read of your wallet, anchored on-chain.
                    </p>
                </div>
                <ConnectButton />
            </header>

            {!isConnected || !address ? (
                <section className="empty">
                    <h2>Connect a wallet to begin</h2>
                    <p>
                        Use MetaMask or any injected wallet on Sepolia (or a
                        local Hardhat chain). The app only reads your public
                        activity and asks you to sign one transaction if you
                        choose to save a report.
                    </p>
                </section>
            ) : (
                <main className="grid">
                    <WalletOverview address={address} />
                    <InsightPanel address={address} registry={registry} />
                    <SavedReports address={address} registry={registry} />
                </main>
            )}

            {/* <footer className="foot">
        <span>Chain {chainId}</span>
        <span>
          Registry:{" "}
          {registry ? (
            <code>{registry}</code>
          ) : (
            <em>not deployed on this chain — run the deploy script</em>
          )}
        </span>
      </footer> */}

            <footer className="foot">
                <span>
                    Chain {chainId}
                    {(wrongChain || !registry) && (
                        <>
                            {" · "}
                            <button
                                className="btn ghost"
                                onClick={() => switchChain({ chainId })}
                                // onClick={() =>
                                //     switchChain({ chainId: hardhat.id })
                                // }
                                disabled={isSwitching}
                            >
                                {isSwitching
                                    ? "Switching…"
                                    : "Switch to Hardhat (31337)"}
                            </button>
                        </>
                    )}
                </span>
                <span>
                    Registry:{" "}
                    {registry ? (
                        <code>{registry}</code>
                    ) : (
                        <em>
                            not deployed on this chain — run the deploy script
                        </em>
                    )}
                </span>
            </footer>
        </div>
    );
}
