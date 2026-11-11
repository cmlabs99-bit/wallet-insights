import registry from "../../shared/InsightRegistry.json";

// Written by contracts/scripts/deploy.js: { abi, addresses: { "<chainId>": "0x..." } }
export const insightRegistryAbi = registry.abi;

const addresses = registry.addresses as Record<string, `0x${string}`>;

export function registryAddress(chainId: number | undefined): `0x${string}` | undefined {
  if (!chainId) return undefined;
  return addresses[String(chainId)];
}
