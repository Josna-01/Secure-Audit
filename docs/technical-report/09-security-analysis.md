# Chapter 9 — Security Analysis

This chapter covers the security properties of the OCR, BNS and blockchain modules and the platform mechanisms they rely on. Findings marked **[verified]** were demonstrated at runtime during this work; the rest are established from code.

## 9.1 Authentication

| Mechanism | Implementation | Source |
|---|---|---|
| Login | Email-OTP flow (`/auth/send-otp`, `/auth/verify-otp`) with password verification against Supabase Auth, OTP tokens in `otp_tokens` | `app.py` |
| Session token | JWT, HS256, secret `JWT_SECRET` (environment), claims `sub`, `email`, `role`, `name`, `iat`, `exp = iat + 24 h` | `create_jwt`, `decode_jwt` |
| Per-request check | `get_current_user_info`: Bearer header required → signature and expiry validated → Supabase `users.is_active` checked (403 if deactivated) → user mirrored into Postgres | `app.py` |

**Weaknesses**
- **Role comes from the token.** It is taken from the JWT claim, not re-read from the database. A role change takes effect only when the user obtains a new token (up to 24 h).
- **No revocation.** There is no revocation list and no `jti`, so a stolen token is valid until expiry unless the account is deactivated.
- **Silent fail-open.** If the Supabase `users` lookup raises an exception, it is swallowed, and the token is accepted without the `is_active` check.

## 9.2 Authorization

| Control | Rule | Applied to |
|---|---|---|
| RBAC (`ROLE_PERMISSIONS`, `has_permission`) | Admin: all. Investigator: create case, upload evidence, run AI analysis, view **owned** cases and logs | Upload (`upload_evidence`); admin redeploy (role check) |
| Case ownership (`check_case_access`) | Admin: all cases. Investigator: a case is visible if `created_by` is the user **or NULL** | OCR run, OCR search (per result), evidence verify, blockchain details, custody transfer, BNS store and read |

**Gaps**

| Endpoint | Missing control |
|---|---|
| `POST /ai/ocr*` | `run_ai_analysis` permission is never checked (case access only) |
| `POST /bns/predict` | **No authentication at all** (open proxy to the BNS service) |
| BNS service `:8001` (all routes) | No authentication. CORS limits browsers only, not direct HTTP clients |
| `POST /blockchain/register`, `POST /blockchain/verify` | Authentication only: no case access, no role check, no audit |
| `GET /blockchain/history/{id}` | No case access check (cross-case information disclosure) |
| `GET /blockchain/status` | Unauthenticated; discloses the contract address and sender account |
| `GET /ocr/search` | For an Investigator, a match in an inaccessible case aborts the whole search with 403, which **reveals that such a match exists** |
| Cases with `created_by = NULL` | Visible to every investigator |

## 9.3 Evidence integrity guarantees

| Property | Holds? | Mechanism |
|---|---|---|
| A change to a registered file's content is detected | **Yes** [verified] | SHA-256 recomputed server-side and compared on-chain (`isMatch` from the contract event) |
| File deletion or relocation is detected | **Yes** [verified] | 404 → status `Missing` + audit |
| A database hash edit is detected | **Yes** [verified] | `databaseMatchesBlockchain = false`, audit "Database Hash Mismatch" |
| Detection is persistent in the UI | Partially | Status updates only when someone runs verification; there is no scheduled re-verification |
| Metadata (case, file name, uploader) integrity | **No** | Stored on-chain but never compared |
| OCR output / BNS output integrity | **No** | Not anchored |
| Audit-log integrity | **No** | Ordinary table; append-only only by convention |

Security reduces to SHA-256 second-preimage resistance ($2^{256}$ work) **provided the on-chain record itself is trustworthy**. Sections 9.5–9.6 show where that assumption fails.

## 9.4 Hash verification bypass analysis

| # | Vector | Status | Impact |
|---|---|---|---|
| B1 | `POST /blockchain/verify` with the publicly known hash | **Mitigated** [verified]: returns the chain result but no longer changes `evidence.status` | Only log noise |
| B2 | `POST /blockchain/register` for an evidence ID not yet on-chain, with the hash of a *tampered* file | **Open.** Accepts a caller-supplied hash and sets status Verified | Any later verification of the tampered file passes. All current evidence is registered, but every newly created ID is exposed during the upload window, and so is any evidence after a chain reset. |
| B3 | Direct contract calls via the RPC endpoint (open contract, public Ganache key) | **Open** [verified]: forged `TRANSFERRED` custody entry, arbitrary `registerEvidence`, and `EvidenceVerified(isMatch=true)` emitted without the file | Custody history forgery; ID squatting; misleading events |
| B4 | Event listener sets `status` from `EvidenceVerified.isMatch` | **Latent.** Currently neutralised only because indexed-string decoding prevents mapping verify events to evidence (Section 7.9) | Fixing the decoding naively would let B3 whitewash tampered evidence |
| B5 | Chain reset (in-memory Ganache) followed by B2 | **Open** until the chain is persistent | Registry wiped; re-registration of arbitrary hashes |
| B6 | Direct `UPDATE evidence SET status='Verified'` | **Open** | The UI shows Verified until the next verification |

## 9.5 Blockchain security

| Aspect | Assessment |
|---|---|
| Consensus / decentralisation | Single-node private Ganache. No independent validators; the node operator can rewrite history (e.g. restart the chain). |
| Keys | Ganache deterministic mnemonic: the sender's private key is public. `ETHEREUM_PRIVATE_KEY` is supported for local signing, but not configured. |
| Contract access control | None (Section 7.4.2). |
| Transaction replay | Prevented by the protocol. Each transaction carries the sender nonce (`get_transaction_count(sender, "pending")`) and `chainId` (EIP-155 replay protection across chains). |
| Application-level replay | Re-sending a verification request simply performs a new verification (idempotent outcome, new custody entry). A timeout retry in `_transact` can create a duplicate custody entry, or report a mined registration as failed. |
| Re-entrancy / arithmetic | Not applicable: no value transfer or external calls; Solidity 0.8 checked arithmetic. |
| Denial of service | Registration requires the chain. When the node is down, uploads are refused (503) rather than accepted without an anchor, which is a deliberate integrity-over-availability choice. |

## 9.6 Storage security
- **Confidentiality:** evidence objects are addressed by **public** Supabase URLs. Anyone holding a URL can download the file; the URLs appear in API responses and database rows.
- **Local mode:** `/uploads` is served by `StaticFiles` **without authentication**.
- **Path traversal:** local paths derived from `file_url` are normalised and must stay under `uploads/` (`commonpath` check) → 400.
- **Size and bomb limits:** the OCR download is capped at `OCR_MAX_FILE_BYTES`; Pillow's decompression-bomb guard is honoured (413).
- **Type validation:** the upload endpoint accepts any file type. OCR validates by magic bytes and decoder.

## 9.7 API security (cross-cutting)

| Aspect | Finding | Source |
|---|---|---|
| SQL injection | ORM with bound parameters; `/ocr/search` escapes `%`, `_`, `\` for `ILIKE` and limits `q` to 200 characters | `app.py` |
| CORS | `allow_origins=["*"]` with `allow_credentials=True` (Starlette then reflects any origin). Tokens are sent as Bearer headers, not cookies, which limits CSRF exposure | `app.py` |
| XSS | React renders OCR and BNS text as text nodes; OCR output is not injected as HTML | `OcrTextViewer.tsx` |
| Error disclosure | Some handlers return raw exception text in `detail` (e.g. `/bns/store`, `/blockchain/register` 500s, the BNS service's 500s) | `app.py`, `main.py` |
| Rate limiting | None on any endpoint | — |
| Secrets | `JWT_SECRET`, Supabase keys and the DB URL come from `.env` (git-ignored for `backend/`). `bns-backend/.env` is tracked but holds no secrets | `.gitignore` |
| Unsafe deserialisation | The BNS wrapper retries `torch.load(..., weights_only=False)` and unpickles `reranker.pkl`: arbitrary code execution if the model directory is writable by an attacker | `model_wrapper.py` |

## 9.8 Translation data egress
When `translate=true`, OCR text (potentially sensitive evidence) is sent to third-party services (Google web endpoint, MyMemory). This is documented in `.env.example`, and the UI labels translations as machine output. Nothing is sent unless the user requests a translation. There is no redaction and no on-premise option (Chapter 2, Section 2.20).

## 9.9 Prompt security
**Not applicable.** No module sends text to a large language model; BNS classification is a supervised classifier (Chapter 6). Prompt-injection risks therefore do not arise. The analogous risk is **adversarial input** to the classifier (crafted FIR text that triggers or suppresses sections). The rule engine's explicit preconditions partly constrain this, but no adversarial testing has been done.

## 9.10 Risk register (ordered by severity)

| # | Risk | Likelihood | Impact | Remediation |
|---|---|---|---|---|
| 1 | Open contract + public key (B3) | High on any shared network | Forged custody; misleading events | Access control; private key in a secret store |
| 2 | `/blockchain/register` accepts caller hashes (B2) | Medium | Tampered evidence certified | Remove, or admin-only with server-side hashing |
| 3 | In-memory chain (B5) | High on restart | Loss of all anchors | Persistent Ganache or a permissioned chain |
| 4 | Public evidence URLs | High | Evidence disclosure | Private bucket + signed, short-lived URLs |
| 5 | Unauthenticated BNS endpoints | Medium | Abuse / DoS of the model service | Authentication; bind the service to localhost |
| 6 | Unsafe model deserialisation | Low | Remote code execution | `weights_only=True`, signed artefacts |
| 7 | Cross-case disclosure (history, search) | Medium | Information leak | Case checks; filter rather than 403 |
| 8 | No audit-log integrity | Medium | Undetectable log edits | Hash-chained log with periodic on-chain anchoring |
