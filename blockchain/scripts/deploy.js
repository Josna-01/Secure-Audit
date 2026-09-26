import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import hre from "hardhat";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

async function main() {
  console.log("Starting EvidenceRegistry deployment process...");

  // 1. Locate and read compiled contract artifact
  const artifactPath = path.join(
    __dirname,
    "../artifacts/contracts/EvidenceRegistry.sol/EvidenceRegistry.json"
  );

  if (!fs.existsSync(artifactPath)) {
    throw new Error(
      `Artifact not found at ${artifactPath}. Please run 'npx hardhat compile' first.`
    );
  }

  const artifactRaw = fs.readFileSync(artifactPath, "utf-8");
  const artifact = JSON.parse(artifactRaw);
  const bytecode = artifact.bytecode;

  if (!bytecode || bytecode === "0x") {
    throw new Error("Contract bytecode is empty.");
  }

  // 2. Determine target RPC URL
  let rpcUrl = "http://127.0.0.1:8545";
  const netConf = hre.config?.networks?.localhost;
  if (typeof netConf === "string" && netConf.startsWith("http")) {
    rpcUrl = netConf;
  } else if (netConf && typeof netConf.url === "string" && netConf.url.startsWith("http")) {
    rpcUrl = netConf.url;
  }

  console.log(`Connecting to Ethereum network at ${rpcUrl}...`);

  // Helper for JSON-RPC requests
  async function jsonRpcCall(method, params = []) {
    const response = await fetch(rpcUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        jsonrpc: "2.0",
        method,
        params,
        id: Date.now(),
      }),
    });
    const data = await response.json();
    if (data.error) {
      throw new Error(`JSON-RPC Error (${method}): ${data.error.message}`);
    }
    return data.result;
  }

  // 3. Fetch accounts
  const accounts = await jsonRpcCall("eth_accounts");
  if (!accounts || accounts.length === 0) {
    throw new Error("No accounts available on target network.");
  }
  const deployer = accounts[0];
  console.log(`Deploying contract from account: ${deployer}`);

  // 4. Send deployment transaction
  console.log("Sending deployment transaction...");
  const txHash = await jsonRpcCall("eth_sendTransaction", [
    {
      from: deployer,
      gas: "0x47b760", // 4,700,000 gas limit
      data: bytecode,
    },
  ]);

  // 5. Poll for transaction receipt
  let receipt = null;
  let attempts = 0;
  while (!receipt && attempts < 20) {
    receipt = await jsonRpcCall("eth_getTransactionReceipt", [txHash]);
    if (!receipt) {
      await new Promise((resolve) => setTimeout(resolve, 500));
      attempts++;
    }
  }

  if (!receipt || !receipt.contractAddress) {
    throw new Error("Deployment receipt not received or contract address missing.");
  }

  console.log("\n==================================================");
  console.log("EvidenceRegistry Contract Deployed Successfully!");
  console.log("==================================================");
  console.log(`Contract Address: ${receipt.contractAddress}`);
  console.log(`Transaction Hash: ${txHash}`);
  console.log(`Deployer Account: ${deployer}`);
  console.log(`Block Number:     ${parseInt(receipt.blockNumber, 16)}`);
  const deploymentDir = path.join(__dirname, "../deployments");
  fs.mkdirSync(deploymentDir, { recursive: true });
  fs.writeFileSync(path.join(deploymentDir, "localhost.json"), JSON.stringify({
    address: receipt.contractAddress, transactionHash: txHash, chainId: parseInt(await jsonRpcCall("eth_chainId"), 16), deployedAt: new Date().toISOString()
  }, null, 2));
  console.log("==================================================\n");
}

main().catch((error) => {
  console.error("Deployment failed:", error);
  process.exitCode = 1;
});
