// Thin client for the FastAPI service. Types mirror ai-service/app/schemas.py.

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";

export type Transaction = {
  hash: string;
  timestamp: number;
  from_address: string;
  to_address: string | null;
  value_eth: number;
  is_contract_interaction: boolean;
  method: string | null;
  failed: boolean;
};

export type WalletSnapshot = {
  address: string;
  chain_id: number;
  balance_eth: number;
  tx_count: number;
  transactions: Transaction[];
  history_available: boolean;
  note: string | null;
};

export type RiskFlag = {
  severity: "low" | "medium" | "high";
  title: string;
  detail: string;
  tx_hash: string | null;
};

export type WalletInsight = {
  summary: string;
  activity_overview: string;
  risk_score: number;
  flags: RiskFlag[];
  suggestions: string[];
  generated_by: string;
};

export type AnalyzeResponse = {
  snapshot: WalletSnapshot;
  insight: WalletInsight;
  report_json: string;
  report_hash: `0x${string}`;
};

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* not JSON */
    }
    throw new Error(detail);
  }
  return res.json();
}

export function fetchSnapshot(address: string): Promise<WalletSnapshot> {
  return fetch(`${API}/wallet/${address}/snapshot`).then((r) => handle<WalletSnapshot>(r));
}

export function analyzeWallet(address: string): Promise<AnalyzeResponse> {
  return fetch(`${API}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ address }),
  }).then((r) => handle<AnalyzeResponse>(r));
}
