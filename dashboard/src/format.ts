export const short = (addr: string) => `${addr.slice(0, 6)}…${addr.slice(-4)}`;

export const eth = (n: number, digits = 4) => `${n.toFixed(digits)} ETH`;

export const when = (unix: number | bigint) =>
  new Date(Number(unix) * 1000).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
