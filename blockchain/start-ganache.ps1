# Starts Ganache with an on-disk database so evidence registrations survive restarts.
#
# Same network settings as before (127.0.0.1:8545, chain id 1337, deterministic
# accounts), plus --database.dbPath. Chain state lives in blockchain/ganache-data
# (git-ignored); delete that folder only if you intend to start a brand-new chain.
#
# Switching from an in-memory Ganache is a one-time migration, because in-memory
# state cannot be carried over:
#   1. Stop the in-memory Ganache and start this script.
#   2. Deploy the contract once: POST /admin/blockchain/redeploy (admin), or
#      `npx hardhat compile; node scripts/deploy.js` in this folder, then restart the backend.
#   3. In backend/: python backfill_blockchain_registration.py --apply
#      (re-registers every evidence item whose file still matches its upload hash).
$ErrorActionPreference = "Stop"
$dataDir = Join-Path $PSScriptRoot "ganache-data"
New-Item -ItemType Directory -Force $dataDir | Out-Null
npx ganache --server.host 127.0.0.1 --server.port 8545 --chain.chainId 1337 --wallet.deterministic --database.dbPath "$dataDir"
