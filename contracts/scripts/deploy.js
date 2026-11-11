// Deploys InsightRegistry and writes the address + ABI where the dashboard and
// AI service can pick them up (../shared/InsightRegistry.json).
const fs = require("fs");
const path = require("path");
const hre = require("hardhat");

async function main() {
    const [deployer] = await hre.ethers.getSigners();
    const network = await hre.ethers.provider.getNetwork();
    console.log(
        `Deploying with ${deployer.address} on ${hre.network.name} (chainId ${network.chainId})`,
    );

    // On the local chain, burn a few nonces first so the contract doesn't land on
    // 0x5FbDB…, the well-known first-deploy address that wallets flag as malicious.
    if (hre.network.name === "localhost") {
        const burn = 5 + Math.floor(Math.random() * 20);
        for (let i = 0; i < burn; i++) {
            await (
                await deployer.sendTransaction({
                    to: deployer.address,
                    value: 0,
                })
            ).wait();
        }
    }

    const Registry = await hre.ethers.getContractFactory("InsightRegistry");
    const registry = await Registry.deploy();
    await registry.waitForDeployment();
    const address = await registry.getAddress();
    console.log(`InsightRegistry deployed to ${address}`);

    // Export ABI + address for the other packages
    const artifact = await hre.artifacts.readArtifact("InsightRegistry");
    const outDir = path.join(__dirname, "..", "..", "shared");
    fs.mkdirSync(outDir, { recursive: true });
    const outFile = path.join(outDir, "InsightRegistry.json");

    let existing = {};
    if (fs.existsSync(outFile))
        existing = JSON.parse(fs.readFileSync(outFile, "utf8"));
    const addresses = {
        ...(existing.addresses || {}),
        [String(network.chainId)]: address,
    };

    fs.writeFileSync(
        outFile,
        JSON.stringify({ abi: artifact.abi, addresses }, null, 2),
    );
    console.log(`Wrote ${outFile}`);
}

main().catch((err) => {
    console.error(err);
    process.exitCode = 1;
});
