# Blockchain integration

## Architecture

```mermaid
flowchart LR
  UI[React evidence details and dashboard] --> API[FastAPI routes]
  API --> SVC[EvidenceBlockchainService]
  API --> DB[(PostgreSQL)]
  SVC --> RPC[Ganache / Ethereum JSON-RPC]
  RPC --> REG[EvidenceRegistry contract]
  REG --> EVT[EvidenceRegistered / EvidenceVerified / CustodyTransferred]
  API --> LOG[Application, audit and blockchain logs]
  DB --> LOG
```

## Upload and verification sequence

```mermaid
sequenceDiagram
  participant U as React
  participant A as FastAPI
  participant D as PostgreSQL
  participant C as EvidenceRegistry
  U->>A: upload file
  A->>A: save file and SHA-256
  A->>D: flush evidence metadata
  A->>C: registerEvidence
  C-->>A: mined receipt + registered custody event
  A->>D: receipt, custody record, audit/blockchain logs
  A-->>U: evidence including chain metadata
  U->>A: POST /evidence/{id}/verify
  A->>A: recompute SHA-256
  A->>C: verifyEvidence + addCustodyRecord(VERIFIED)
  C-->>A: receipts
  A->>D: status, verification and custody logs
  A-->>U: verification result
```

## API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| POST | `/evidence/upload` | Stores file and metadata, registers it on-chain, returns receipt metadata. |
| POST | `/evidence/{id}/verify` | Re-hashes the file, verifies on-chain, and appends custody. |
| GET | `/evidence/{id}/blockchain` | Chain status, stored receipt metadata and chronological custody history. |
| POST | `/evidence/{id}/custody/transfer` | Body: `{"officer_id":"..."}`. Appends a TRANSFERRED custody entry. |
| GET | `/blockchain/dashboard` | Admin chain health, evidence counts, transactions and blocks. |
| POST | `/admin/blockchain/redeploy` | Admin-only compile/deploy, then reloads ABI and deployment address. |

## Database changes

`evidence` gains transaction hash, block number, contract address, gas used, registration timestamp, and latest verification timestamp. `evidence_custody_records` is the queryable mirror of custody events; `blockchain_logs` is the immutable local event/transaction log. Apply with `python migrate_blockchain.py` from `backend`.

## Deployment

1. Start PostgreSQL and apply existing schema, then run `python migrate_blockchain.py` in `backend`.
2. In `blockchain`, start Ganache at the configured RPC endpoint, then run `npx hardhat compile` and `node scripts/deploy.js`. The script writes `blockchain/deployments/localhost.json`; the backend automatically reads it.
3. Install backend requirements and start FastAPI from `backend`: `uvicorn app:app --reload`.
4. Start the React client from `audit-frontend`: `npm run dev`.

Use these environment variables: `ETHEREUM_RPC_URL`, `EVIDENCE_REGISTRY_ADDRESS` (optional when deployment JSON exists), `EVIDENCE_REGISTRY_ARTIFACT` (optional), `EVIDENCE_REGISTRY_DEPLOYMENT` (optional), `ETHEREUM_SENDER_ADDRESS`, `ETHEREUM_PRIVATE_KEY` (server-only; never prefix with `VITE_`), `BLOCKCHAIN_TX_TIMEOUT_SECONDS`, `BLOCKCHAIN_RETRIES`, and `BLOCKCHAIN_AUTO_REDEPLOY` (default `false`).

Ganache may use its unlocked account through `ETHEREUM_SENDER_ADDRESS`; production deployments should provide a protected `ETHEREUM_PRIVATE_KEY` via the server secret manager.

## Persistence and legacy evidence

Run Ganache with an on-disk database so registrations survive restarts: `blockchain/start-ganache.ps1` (or `npm run chain` in `blockchain`). An in-memory Ganache loses every registration when it stops. The backend no longer redeploys a missing contract automatically (`BLOCKCHAIN_AUTO_REDEPLOY=false`); it reports the problem instead, because a silently redeployed empty registry would make every existing evidence item fail verification.

Evidence without a valid on-chain registration (uploaded before the integration, or registered on a contract lost to a chain reset) is handled by `python backfill_blockchain_registration.py` in `backend` (dry run by default, `--apply` to write). Items whose file still matches the upload hash are registered; the rest are marked `Unregistered`, never `Verified`, with an audit log entry explaining why.

## Verification statuses

`POST /evidence/{id}/verify` re-hashes the stored file and uses the contract's `EvidenceVerified.isMatch` as the verdict:

| Status | HTTP | Meaning |
|---|---|---|
| `Verified` | 200 | File hash matches the on-chain hash. |
| `Tampered` | 200 | File hash differs from the on-chain hash. |
| `Missing` | 404 | The stored file no longer exists; audit action `Evidence File Missing`. |
| `Unregistered` | 409 | No on-chain registration exists; audit action `Evidence Not Registered On-Chain`. |

The response carries `databaseHash`, `blockchainHash`, `databaseMatchesBlockchain` and `warnings`; a database/blockchain difference is also written to the audit log as `Database Hash Mismatch`. `POST /blockchain/verify` (caller-supplied hash) still records the on-chain check but no longer changes the evidence status.
