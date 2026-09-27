# Chapter 10 — Algorithms

Pseudocode follows the implementation. Each algorithm names its source. Notation: `←` assignment, `‖` concatenation, `σ` logistic sigmoid.

## Algorithm 1 — OCR pipeline (document level)
*Source: `ocr_service.py::extract_document`, `extract_page`; `app.py::run_stored_evidence_ocr`*

```text
Input : evidence id e, language request λ, force f, translate τ, target t
Output: document result R (+ translation)

 1  authenticate; E ← evidence(e); require case access(E.case)
 2  L ← RESOLVE-LANGUAGES(λ)                      ▷ Algorithm 2, step 1
 3  acquire lock(e)
 4  rows ← latest row per page of ocr_results(e)
 5  if ¬f ∧ CACHE-USABLE(rows, L, λ) then R ← rows-to-result(rows); cached ← true
 6  else
 7      B ← fetch bytes of E.file_url (size ≤ 50 MB, streamed)
 8      (P, load, kind) ← OPEN-DOCUMENT(B)        ▷ magic-byte sniffing; PDF via PDFium; TIFF frames
 9      require |P| ≤ 50
10      for i ← 1..|P| do
11          try  pages[i] ← EXTRACT-PAGE(load(i), L)
12          catch EngineUnavailable or Limit: raise
13          catch other error ε: pages[i] ← FAILED-PAGE(i, ε)
14      if all pages failed then raise ProcessingError
15      R ← BUILD-RESULT(pages, L, kind)          ▷ join page texts; character-weighted confidence; languages
16      BEGIN; advisory-lock(e); DELETE ocr_results(e); INSERT pages; COMMIT
17      audit("OCR Extraction")
18  release lock(e)
19  if τ then R.translation ← TRANSLATE-OCR(e, R, t)   ▷ Algorithm 3
20  return R

EXTRACT-PAGE(I, L):
 1  (I′, info) ← PREPROCESS(I)                    ▷ Algorithm 1a
 2  if info.blank then return EMPTY-PAGE
 3  lines ← RECOGNIZE(I′, L)                      ▷ Algorithm 2
 4  raw ← join(lines.text, "\n")
 5  keep ← {ℓ ∈ lines : ℓ.conf ≥ 0.35 ∧ ¬NOISE(CLEAN(ℓ.text), ℓ.conf)}
 6  keep ← DEDUPE-OVERLAPPING(keep)               ▷ overlap > 0.6 ∧ similar text
 7  (text, tables) ← RECONSTRUCT-LAYOUT(keep)     ▷ Algorithm 1b
 8  D ← DETECT-LANGUAGES(text); C ← Σ|t|·c / Σ|t|
 9  return page{text, raw, C, D, tables, lines, rotation, skew, preprocessing, time}
```

### Algorithm 1a — Conditional preprocessing
*Source: `ocr_service.py::preprocess_page`*

```text
 1  g ← gray(I)
 2  if std(g) < 2.5 ∧ P99.5(g) − P0.5(g) < 16 then return (I, blank)
 3  L ← longest side of I
 4  if L > 2560 then I ← resize(I, 2560/L, AREA)
 5  σ̂ ← IMMERKAER-NOISE(gray(I)) over pixels with |∇| < P80(|∇|)
 6  if σ̂ > 8 ∧ max side ≤ 3000 then I ← NL-MEANS(I, h = min(12, 0.8σ̂), 7, 21)
 7  if L < 1600 then I ← resize(I, min(1600/L, 3), CUBIC)
 8  g ← gray(I)
 9  if median(g) − P0.2(g) < 100 then I ← CLAHE on L-channel(I, clip 2.0, 8×8)
10  θ ← PROJECTION-SKEW(gray(I))                  ▷ Otsu; ink ratio ∈ [0.005, 0.3]; ±45° step 1°, refine ±1° step 0.1°
11  if |θ| ≥ 0.3 ∧ Var(P_θ) ≥ 1.15·Var(P_0) then I ← ROTATE-EXPAND(I, θ)
12  return I
```

### Algorithm 1b — Layout reconstruction
*Source: `ocr_text.py::reconstruct_layout`*

```text
 1  ᾱ ← median angle of boxes with width > 2·height
 2  rotate every polygon by −ᾱ; take axis-aligned boxes
 3  h̃ ← median box height; w̃ ← median(box width / text length); g ← max(2.5w̃, 1.2h̃)
 4  sort boxes by (centre-y, x0)
 5  for each box b:                                  ▷ row grouping
 6      band ← (median y0, median y1) of the last row
 7      if overlap(b, band) ≥ 0.5·min(h_b, median row height) then append b to the row else start a new row
 8  for each row: sort by x0; split into cells at gaps ≥ g
 9  for maximal runs of consecutive rows with ≥ 2 cells and row gap ≤ 1.5h̃:
10      anchors ← cluster(cell x0, tolerance 3w̃)
11      if run length ≥ 3 ∧ #anchors used by ≥ max(2, len/2) rows ≥ 2 then mark as a table
12  for each row r:
13      if gap to the previous row > 0.9h̃ or the table membership changes then emit a blank line
14      if r is in a table then emit non-empty cells joined by " | "
15      else text ← cells joined by 3 spaces; normalise bullet glyphs to "•"
16           if list item then indent by 2·round((x0 − margin)/(4w̃)) spaces (≤ 4 levels)
17  collapse runs of 3+ newlines
```

## Algorithm 2 — Multilingual recognition
*Source: `ocr_service.py::_recognize`, `_fix_upside_down_lines`, `_rerecognize`, `_refine_with_tesseract`, `_restore_word_spacing`; `ocr_text.py::resolve_languages`*

```text
Input : page image I′, candidate languages L = (ℓ1, …, ℓk)
Output: lines {text, conf, bbox, language, engine}

RESOLVE-LANGUAGES(λ): "auto" ↦ (en, hi, kn, te, ta, ml); aliases ↦ ISO codes; "a+b" ↦ (a, b)

 1  p ← first ℓ ∈ L with a PaddleOCR model that loads (else "en" as a detection carrier)
 2  (quads, texts, scores, Î) ← PADDLE-PIPELINE_p(I′)        ▷ doc orientation, detection, recognition
 3  lines ← {(t_i, c_i, q_i, ℓ = p, engine = paddle)}
 4  crop(i) ← PERSPECTIVE-RECTIFY(Î, q_i); rotate 90° if h/w ≥ 1.5; rotate 180° if flipped
 5  for i with c_i < 0.85:                                     ▷ upside-down test
 6      (t′, c′) ← REC_p(rotate180(crop(i)))
 7      if c′ ≥ 0.85 ∧ c′ ≥ c_i + 0.1 then line_i ← (t′, c′, flipped)
 8  if p ∉ L then set c_i ← 0 temporarily for all i          ▷ carrier mode
 9  U ← {i : R(t_i, c_i, ℓ_i) < 0.93}                          ▷ R = c·(0.5 + 0.5·ν_ℓ(t))
10  in parallel for ℓ′ ∈ L \ {p}: readings[ℓ′] ← READ(ℓ′, {crop(i) : i ∈ U})
11      ▷ READ uses Tesseract for ℓ′ ∈ {kn, ml} (if installed) else the PaddleOCR recogniser of ℓ′
12  for ℓ′ in order: for i ∈ U: APPLY(i, ℓ′, readings[ℓ′][i])
13  present ← {ℓ′ that won ≥ 1 line}
14  if present ≠ ∅: in parallel read the remaining lines with each ℓ′ ∈ present; APPLY in order
15  restore carrier confidences for lines still in language p
16  for ℓ ∈ {kn, ml} with Tesseract data:                      ▷ Tesseract refinement
17      S ← lines with language ℓ not yet read by Tesseract
18      out ← TESSERACT-STACKED(crops(S), "ℓ+eng")            ▷ one process; TSV mapped by vertical band
19      for i ∈ S with out_i non-empty ∧ conf ≥ 0.3 ∧ ρ_ℓ(out_i) ≥ 0.5:
20          line_i ← (RESTORE-DROPPED-DIGITS(out_i, t_i), conf, tesseract)
21  for Kannada lines still on PaddleOCR with no space and ≥ 6 characters:
22      words ← split crop at gaps ≥ max(0.22h, 2·median gap); re-read each word; join with spaces
23  return lines

APPLY(i, ℓ′, (t′, c′)):
 1  if ρ_ℓ′(t′) < 0.2 then return                              ▷ output is not in ℓ′'s script
 2  if ℓ′ ≠ en ∧ letters of ℓ′'s script in t′ < 3 then return
 3  if R(t′, c′, ℓ′) > R(t_i, c_i, ℓ_i) + 0.02 ∨ ADDS-MISSING(t_i, t′, c′, ℓ′) then
 4      line_i ← (t′, c′, ℓ′, engine(ℓ′)); count a win for ℓ′

ADDS-MISSING(t, t′, c′, ℓ′):  ℓ′ ≠ en ∧ c′ ≥ 0.7 ∧ t has no ℓ′-script letter ∧ t′ has ≥ 2
                              ∧ |Latin(t)| ≥ 3 ∧ ratio(Latin(t), Latin(t′)) ≥ 0.8

RESTORE-DROPPED-DIGITS(tT, tP):
 1  A ← digit runs of tT; B ← digit runs of tP; align A with B (SequenceMatcher)
 2  for each "replace" block, pair runs right-aligned: if |b| > |a| ∧ b ends with a then a ← b
```

## Algorithm 3 — Translation pipeline
*Source: `translation_service.py`; `app.py::translate_ocr_result`*

```text
Input : OCR result R (pages), target t
Output: translation {status, pages, translated_text, providers, error, message}

 1  t ← RESOLVE-TARGET(t); on failure return {status: failed, error}
 2  for each page p: if ocr_metadata.translations[t].source_digest = SHA256(p.text) then use the stored text
 3  if every page had a stored translation then return it (cached = true)
 4  if Σ|p.text| > 30 000 then return failed
 5  for each page: units ← SEGMENTS(p.text)            ▷ same-language consecutive lines, ≤ provider limit;
 6                                                      ▷ lines without letters get source = ∅
 7  jobs ← units with source ∉ {∅, t}
 8  if jobs = ∅ then return skipped (original text)
 9  for each job (u, s):
10      try  u ← TRANSLATE-CHUNK(u, s, t)
11      catch NoTranslationFound: untranslated += 1       ▷ keep the original
12      catch error ε: failures += ε                      ▷ keep the original
13  status ← success if no failures; failed if every attempted job failed; else partial
14  if status ∈ {success, skipped} then store translations[t] ← {text, source_digest, providers, …}
15  return result

TRANSLATE-CHUNK(u, s, t):
 1  if SHA256(s ">" t 0x00 u) ∈ LRU then return it
 2  for provider π in (google, mymemory):
 3      if π is paused or u exceeds π's limit then continue
 4      try  r ← π(u, s, t) with a 20 s timeout
 5      catch timeout / 429 / quota / unreachable: pause π for 300 s; continue
 6      catch NoTranslationFound: noMatch ← true; continue
 7      if r ≠ "" then LRU ← r; return r
 8  raise NoTranslationFound if noMatch else ProviderError
```

## Algorithm 4 — BNS classification
*Source: `bns-backend/app/model_wrapper.py::predict`, `hgat_model.py`, `postprocess.py`; `backend/app.py::bns_predict`*

```text
Input : FIR facts F (≥ 5 characters)
Output: {bns: [(section_id, name, meaning)], crime_type}

 1  h ← LegalBERT-CLS(truncate(F, 512))                    ▷ ∈ ℝ^768
 2  q ← MiniLM(F)                                          ▷ ∈ ℝ^384, ‖q‖ = 1
 3  H_k ← FAISS-IP-TOP-k(q, k = 20); s_j ← 1 − q·e_j       ▷ as implemented (inverted; correct: s_j = q·e_j)
 4  if no trained model then S ← top-5 of H_k; crime ← "unknown"
 5  else
 6      r ← 10·s scattered over the N sections; x ← [h ; r]
 7      c ← CASE-ENCODER(x); H ← GAT₂(GAT₁(V, E)); a ← CrossAttn(c, proj(H))
 8      z ← SECTION-HEAD(SharedBase([c; a; mean(H); max(H)])); u ← CRIME-HEAD(…)
 9      S ← {j : σ(z_j) ≥ 0.5}; crime ← label(argmax softmax(u))
10      if S = ∅ then S ← top-5 of H_k
11      else rank S by reranker α·p̂ + (1 − α)·σ(z_j) (α = 0.7) or by (σ(z_j), s_j)
12  (bns, crime) ← POST-PROCESS(S, F, H_k, crime)
13  proxy: split each meaning at " | " into (name, meaning); score ← 0.0
14  return {bns, crime_type}

POST-PROCESS(S, F, H_k):
 1  infer victim age, gender, offender count, weapon use from F (regexes)
 2  C ← ∅
 3  for (j, s_j) ∈ S with retrieval score r̃_j:
 4      drop if r̃_j < 0.55 ∧ s_j < 0.75
 5      drop if keywords(j) ≠ ∅ ∧ r̃_j < 0.7 ∧ no keyword of j occurs in F
 6      apply cluster rules (violent / murder / sexual / kidnapping / property thresholds and preconditions)
 7      otherwise add j to C with its cluster
 8  if C = ∅ then return top-10 of H_k with titles
 9  for j ∈ C: s′_j ← s_j · clip(1 + 0.6·(mean_cluster − mean)/mean, 0.6, 1.6)
10      if F is about property ∧ cluster(j) ≠ property ∧ s′_j < 0.95 ∧ r̃_j < 0.9 then s′_j ← 0.4·s′_j
11      if a keyword of j occurs in F then s′_j ← min(0.9999, s′_j + 0.03)
12  prune by cluster thresholds; prune if r̃_j < 0.55 ∧ no keyword ∧ s′_j < 0.95
13  sort by s′ descending; de-duplicate; if empty then top-5 property candidates
14  return [(j, title_j, text_j[:400])]
```

## Algorithm 5 — Evidence upload and blockchain registration
*Source: `app.py::upload_evidence`; `blockchain_service.py::register_evidence`, `_transact`*

```text
Input : case c, file bytes B, user u
 1  require JWT ∧ permission(upload_evidence) ∧ case access(c)
 2  h ← SHA256(B) (hex)
 3  if ∃ evidence(case = c, file_hash = h) then return 409 {evidence_id}
 4  path ← store B at cases/c/uuid_name (Supabase Storage or local)
 5  BEGIN; INSERT evidence(…, file_hash = h, status = "Verified"); flush → id
 6  if getEvidence(id) exists on-chain then raise "already registered"
 7  receipt ← TRANSACT(registerEvidence(id, c, name, h, u))
 8  on failure: ROLLBACK; return 503                          ▷ the stored file remains
 9  evidence.blockchain_{tx, block, contract, gas, registered_at} ← receipt
10  INSERT custody(REGISTERED, tx); INSERT blockchain_logs(EvidenceRegistered); COMMIT
11  audit("Evidence Upload"); return evidence

TRANSACT(fn):
 1  for attempt ← 1..3:
 2      try  nonce ← pendingNonce(sender); tx ← build(fn, from, nonce, chainId); send (signed or unlocked)
 3           receipt ← wait(tx, 90 s); require receipt.status = 1
 4           return {tx, block, gasUsed, to, blockTime}
 5      catch error: reconnect; sleep 2^(attempt−1) s
 6  raise TransactionError
```

## Algorithm 6 — Blockchain verification and tamper detection
*Source: `app.py::verify_evidence_hash`, `compute_evidence_file_hash`; `blockchain_service.py::verify_evidence`*

```text
Input : evidence id e, user u
Output: status ∈ {Verified, Tampered, Missing, Unregistered} and hashes
 1  require JWT ∧ case access; E ← evidence(e)
 2  try h_f ← SHA256(stored file of E)
 3  catch Missing (HTTP 404 or Supabase 400 "not_found", or no local file):
 4      E.status ← Missing; audit("Evidence File Missing"); return 404
 5  catch storage unreachable: return 502                     ▷ status unchanged
 6  reg ← getEvidence(e)
 7  if reg = none then E.status ← Unregistered; audit("Evidence Not Registered On-Chain"); return 409
 8  rcpt ← TRANSACT(verifyEvidence(e, h_f))
 9  isMatch ← EvidenceVerified.isMatch decoded from rcpt       ▷ contract verdict: keccak(reg.hash) = keccak(h_f)
10  require isMatch = (reg.hash = h_f)
11  TRANSACT(addCustodyRecord(e, u, VERIFIED))
12  E.status ← Verified if isMatch else Tampered
13  INSERT custody(VERIFIED); INSERT blockchain_logs(calculated, blockchain, database hashes); COMMIT
14  audit("Hash Verified" if isMatch else "Tamper Detected")
15  dbOK ← (E.file_hash = reg.hash)
16  if ¬dbOK then audit("Database Hash Mismatch"); warnings ← "database record may have been altered"
17  return {verified: isMatch, databaseHash, blockchainHash: reg.hash, calculatedHash: h_f,
            databaseMatchesBlockchain: dbOK, warnings, tx, custodyHistory}
```

## Algorithm 7 — Legacy evidence backfill
*Source: `backfill_blockchain_registration.py`*

```text
 1  K ← current contract address
 2  for E in evidence ordered by created_at with (no tx hash ∨ contract ≠ K):
 3      try h ← SHA256(file(E)) catch missing/unreachable: mark(E, Unregistered, reason); continue
 4      if E.file_hash ≠ ∅ ∧ E.file_hash ≠ h then mark(E, Unregistered, "file changed since upload"); continue
 5      reg ← getEvidence(E.id)
 6      if reg exists: if reg.hash = h then adopt the receipt found via EvidenceRegistered logs
 7                     else mark(E, Unregistered, "on-chain hash conflicts with file")
 8      else if --apply then receipt ← registerEvidence(E.id, E.case, E.name, h, uploader); store the receipt
 9      audit(outcome); commit per item                         ▷ never undo completed on-chain work
```

## Algorithm 8 — Contract event synchronisation
*Source: `app.py::synchronize_blockchain_events`*

```text
every 10 s:
 1  if cursor = ⊥ then cursor ← latestBlock − 1 (only when connected)
 2  (events, latest) ← logs of {EvidenceRegistered, EvidenceVerified, CustodyTransferred} in [cursor, latest]
 3  for ev in events (sorted by block, tx):
 4      E ← evidence with blockchain_tx_hash = ev.tx, else evidence(UUID(ev.evidenceId))
 5          ▷ indexed string ⇒ evidenceId is keccak256(id) ⇒ the UUID lookup always fails
 6      if E ∧ ev is EvidenceVerified then E.status ← Verified if ev.isMatch else Tampered
 7      if E ∧ ev is CustodyTransferred ∧ no custody row for ev.tx then insert a custody row
 8      if no blockchain_logs(ev.tx, ev.name) then insert one (evidence_id = E or NULL)
 9  COMMIT; cursor ← latest + 1           ▷ on error: ROLLBACK and retry next poll
```
