const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("InsightRegistry", function () {
  async function deploy() {
    const [alice, bob] = await ethers.getSigners();
    const Registry = await ethers.getContractFactory("InsightRegistry");
    const registry = await Registry.deploy();
    await registry.waitForDeployment();
    return { registry, alice, bob };
  }

  const hashOf = (text) => ethers.keccak256(ethers.toUtf8Bytes(text));

  it("saves an insight and emits an event", async function () {
    const { registry, alice } = await deploy();
    const h = hashOf('{"summary":"looks fine"}');

    await expect(registry.connect(alice).saveInsight(h, 12, "ipfs://abc"))
      .to.emit(registry, "InsightSaved")
      .withArgs(alice.address, 0, h, 12, "ipfs://abc");

    expect(await registry.insightCount(alice.address)).to.equal(1);
    const stored = await registry.getInsight(alice.address, 0);
    expect(stored.reportHash).to.equal(h);
    expect(stored.riskScore).to.equal(12);
    expect(stored.uri).to.equal("ipfs://abc");
    expect(stored.savedAt).to.be.gt(0);
  });

  it("keeps wallets' lists separate", async function () {
    const { registry, alice, bob } = await deploy();
    await registry.connect(alice).saveInsight(hashOf("a"), 1, "");
    await registry.connect(bob).saveInsight(hashOf("b"), 2, "");
    await registry.connect(bob).saveInsight(hashOf("c"), 3, "");

    expect(await registry.insightCount(alice.address)).to.equal(1);
    expect(await registry.insightCount(bob.address)).to.equal(2);
  });

  it("returns latest insights newest-first", async function () {
    const { registry, alice } = await deploy();
    for (let i = 0; i < 4; i++) {
      await registry.connect(alice).saveInsight(hashOf(`r${i}`), i * 10, "");
    }
    const latest = await registry.latestInsights(alice.address, 3);
    expect(latest.length).to.equal(3);
    expect(latest[0].riskScore).to.equal(30);
    expect(latest[2].riskScore).to.equal(10);
  });

  it("rejects bad input", async function () {
    const { registry, alice } = await deploy();
    await expect(registry.connect(alice).saveInsight(ethers.ZeroHash, 5, ""))
      .to.be.revertedWithCustomError(registry, "EmptyHash");
    await expect(registry.connect(alice).saveInsight(hashOf("x"), 101, ""))
      .to.be.revertedWithCustomError(registry, "InvalidRiskScore")
      .withArgs(101);
  });
});
