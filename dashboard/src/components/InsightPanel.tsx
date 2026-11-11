import { useEffect } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
    useAccount,
    useChainId,
    useSwitchChain,
    useWaitForTransactionReceipt,
    useWriteContract,
} from "wagmi";

import { analyzeWallet, type AnalyzeResponse } from "../api";
import { insightRegistryAbi } from "../contract";

type Props = { address: `0x${string}`; registry?: `0x${string}` };

export function InsightPanel({ address, registry }: Props) {
    const queryClient = useQueryClient();
    const chainId = useChainId();
    const { chainId: walletChainId } = useAccount();
    const { switchChainAsync } = useSwitchChain();

    // 1) Ask the AI service for a report
    const analysis = useMutation({ mutationFn: () => analyzeWallet(address) });

    // 2) Optionally anchor the report hash on-chain
    const {
        writeContract,
        data: txHash,
        isPending: isSigning,
        error: writeError,
        reset,
    } = useWriteContract();
    const receipt = useWaitForTransactionReceipt({
        hash: txHash,
        query: {
            enabled: Boolean(txHash),
        },
    });

    // Once the tx is mined, refresh the "Saved on-chain" list (wagmi keys reads under "readContract")
    useEffect(() => {
        if (receipt.isSuccess)
            queryClient.invalidateQueries({ queryKey: ["readContract"] });
    }, [receipt.isSuccess, queryClient]);

    // const save = (r: AnalyzeResponse) => {
    //     if (!registry) return;
    //     // in save():
    //     writeContract({
    //         abi: insightRegistryAbi,
    //         address: registry,
    //         chainId,
    //         functionName: "saveInsight",
    //         args: [r.report_hash, r.insight.risk_score, ""],
    //     });
    // };

    // replace the save function:
    const save = async (r: AnalyzeResponse) => {
        if (!registry) return;
        if (walletChainId !== chainId) {
            await switchChainAsync({ chainId }); // MetaMask prompts "Switch network"
        }
        writeContract({
            abi: insightRegistryAbi,
            address: registry,
            chainId,
            functionName: "saveInsight",
            args: [r.report_hash, r.insight.risk_score, ""],
        });
    };

    const r = analysis.data;

    return (
        <section className="card span2">
            <div className="row">
                <h2>AI insight</h2>
                <button
                    className="btn"
                    disabled={analysis.isPending}
                    onClick={() => {
                        reset();
                        analysis.mutate();
                    }}
                >
                    {analysis.isPending
                        ? "Analyzing…"
                        : r
                          ? "Re-run analysis"
                          : "Analyze this wallet"}
                </button>
            </div>

            {analysis.error && (
                <p className="error">{(analysis.error as Error).message}</p>
            )}

            {r && (
                <div className="insight">
                    <div className="score-row">
                        <RiskMeter score={r.insight.risk_score} />
                        <div>
                            <p className="lead">{r.insight.summary}</p>
                            <p className="muted">
                                {r.insight.activity_overview}
                            </p>
                        </div>
                    </div>

                    {r.insight.flags.length > 0 && (
                        <ul className="flags">
                            {r.insight.flags.map((f, i) => (
                                <li key={i} className={`flag ${f.severity}`}>
                                    <strong>{f.title}</strong>
                                    <span>{f.detail}</span>
                                    {f.tx_hash && (
                                        <code>{f.tx_hash.slice(0, 10)}…</code>
                                    )}
                                </li>
                            ))}
                        </ul>
                    )}

                    {r.insight.suggestions.length > 0 && (
                        <>
                            <h3>Suggested next steps</h3>
                            <ul className="plain">
                                {r.insight.suggestions.map((s, i) => (
                                    <li key={i}>{s}</li>
                                ))}
                            </ul>
                        </>
                    )}

                    <div className="anchor">
                        <div>
                            <span className="stat-label">
                                Report hash (keccak256)
                            </span>
                            <code className="hash">{r.report_hash}</code>
                            <span className="muted small">
                                generated by {r.insight.generated_by}
                            </span>
                        </div>
                        <button
                            className="btn"
                            disabled={
                                !registry || isSigning || receipt.isLoading
                            }
                            onClick={() => save(r)}
                            title={
                                registry
                                    ? "Store this hash in InsightRegistry"
                                    : "Deploy the contract on this chain first"
                            }
                        >
                            {isSigning
                                ? "Confirm in wallet…"
                                : receipt.isLoading
                                  ? "Mining…"
                                  : "Save hash on-chain"}
                        </button>
                    </div>

                    {writeError && (
                        <p className="error">
                            {shortError(writeError.message)}
                        </p>
                    )}
                    {receipt.isSuccess && (
                        <p className="ok">
                            Saved. Transaction{" "}
                            <code>{txHash?.slice(0, 10)}…</code> mined in block{" "}
                            {receipt.data?.blockNumber.toString()}.
                        </p>
                    )}
                </div>
            )}
        </section>
    );
}

function RiskMeter({ score }: { score: number }) {
    const level =
        score > 80
            ? "critical"
            : score > 50
              ? "high"
              : score > 20
                ? "medium"
                : "low";
    return (
        <div
            className={`meter ${level}`}
            aria-label={`Risk score ${score} of 100`}
        >
            <span className="meter-value">{score}</span>
            <span className="meter-label">risk</span>
        </div>
    );
}

// Wallet errors are verbose; keep the first line.
const shortError = (m: string) => m.split("\n")[0];
