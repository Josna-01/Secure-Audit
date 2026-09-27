# Chapter 11 — File-by-File Analysis

Legend: **M** = module (OCR / BNS / BC = blockchain). "Called by" lists the in-repository callers.

## 11.1 Backend (`backend/`)

### `app.py` — FastAPI application (M: OCR, BNS, BC)
- **Purpose.** Hosts every HTTP endpoint and orchestrates the services, the database and storage.
- **Dependencies.** FastAPI, SQLAlchemy session (`db.get_db`), `models`, `services.*`, `supabase`, `requests`, `jwt` (PyJWT), `hashlib`.
- **Key definitions for this report.**

  | Area | Definitions |
  |---|---|
  | Authentication and authorization | `create_jwt`, `decode_jwt`, `get_current_user_info`, `ROLE_PERMISSIONS`, `has_permission`, `get_data_visibility`, `check_case_access`, `sync_user_to_postgres` |
  | Audit | `write_audit_log` (append-only by convention) |
  | Blockchain event handling | `synchronize_blockchain_events`, `blockchain_event_listener`, `start_blockchain_event_listener` (startup), `make_json_safe` |
  | Schema hook | `ensure_ocr_result_columns` (startup) |
  | Evidence | `upload_evidence`, `get_evidence`, `EvidenceFileMissing`, `compute_evidence_file_hash`, `verify_evidence_hash`, `evidence_blockchain_details`, `transfer_evidence_custody` |
  | Blockchain API | `blockchain_status`, `blockchain_register`, `blockchain_verify`, `blockchain_evidence_history`, `blockchain_dashboard`, `redeploy_evidence_registry` |
  | OCR | `LEGACY_OCR_PLACEHOLDERS`, `_ocr_evidence_lock`, `resolve_ocr_evidence_source`, `load_cached_ocr_pages`, `cached_ocr_is_usable`, `cached_ocr_result`, `store_ocr_pages`, `_text_digest`, `translate_ocr_result`, `ocr_response`, `run_stored_evidence_ocr`, `run_ai_ocr_by_id`, `run_ai_ocr_body`, `search_ocr` |
  | BNS | `BNSRequest`, `BNSStore`, `bns_predict` (proxy), `bns_store`, `bns_get_case`, `get_bns_case` (stub) |
  | Request models | `OCRRequest` (`evidence_id`, `language`, `force`, `translate`, `target_language`), `CustodyTransferRequest`, `BlockchainRegisterRequest`, `BlockchainVerifyRequest` |

- **Called by.** The frontend over HTTP; `backfill_blockchain_registration.py` reuses models and services but not `app.py`.

### `models.py` — SQLAlchemy ORM (M: all)
- **Classes.** `User`, `Case`, `Evidence` (including blockchain receipt columns and `status`), `EvidenceCustodyRecord`, `BlockchainLog`, `AuditLog` (`metadata_` → column `metadata`), `OCRResult` (with `detected_languages`, `ocr_metadata`), `BNSPrediction`, `OTPToken`.
- **Called by.** `app.py`, `backfill_blockchain_registration.py`, migration scripts.

### `db.py` — database engine
- **Contents.** Builds `DATABASE_URL` (or composes it from `DB_*` variables with URL-encoded credentials) and creates the pooled `engine`, `SessionLocal` and `Base`. Provides the `get_db()` dependency.
- **Called by.** `app.py`, `models.py`, migrations, the backfill.

### `services/ocr_service.py` — OCR engine orchestration (M: OCR)
- **Classes.**
  - Errors: `OCRServiceError` (+ `OCRLanguageError` 400, `OCRLimitError` 413, `OCRUnsupportedFileError` 415, `OCRInvalidFileError` 422, `OCREngineUnavailableError` 503, `OCRProcessingError` 500).
  - `PaddleOCRService`: thread-safe singleton with model caches and locks.
- **Configuration.** `DETECTION_MODEL`, `RECOGNITION_MODELS`, `SPACE_POOR_LANGUAGES`, `MODEL_RETRY_SECONDS`, `tesseract_languages()`, `check_dependencies()`.
- **Functions by stage.**

  | Stage | Functions |
  |---|---|
  | Input | `_read_source`, `_is_pdf`, `_pil_to_bgr`, `_open_document`, `_open_image`, `_open_pdf`, `_open_pdf_with_poppler` |
  | Preprocessing | `_is_blank`, `_noise_sigma`, `_estimate_page_skew`, `_rotate`, `preprocess_page`, `preprocess_image` (compatibility) |
  | Recognition helpers | `_result_dict`, `_to_list`, `_crop_line`, `_split_word_crops`, `_reading_score`, `restore_dropped_digits`, `_adds_missing_script`, `_own_script_ratio`, `_unavailable_message` |
  | Service methods | `resolve_languages`, `normalize_language`, `_load_cached`, `_get_pipeline`, `_get_recognizer`, `_run_pipeline`, `_read_crops`, `_rerecognize`, `_fix_upside_down_lines`, `_refine_with_tesseract`, `_restore_word_spacing`, `_recognize`, `extract_page`, `extract_document`, `extract_image` |
  | Output | `build_document_result`, `_failed_page`, `_add_warning`, `_elapsed_ms`, `extract_text` (compatibility); singleton `ocr_service` |

- **Dependencies.** PaddleOCR / PaddleX (lazy import), OpenCV, NumPy, Pillow, pypdfium2 (or pdf2image), `ocr_text`, `tesseract_engine`.
- **Called by.** `app.py` (`ocr_service.extract_document`, `resolve_languages`, `build_document_result`), `tests/test_ocr_engine_rules.py`, diagnostic scripts under `scratch/`.

### `services/ocr_text.py` — pure text and layout logic (M: OCR)
- **Classes.** `LanguageSpec`, `_Box`.
- **Tables.** `SUPPORTED_LANGUAGES`, `LANGUAGE_ALIASES`, `_SCRIPT_RANGES`, `_FOREIGN_SCRIPTS`, `_ZERO_TO_ANUSVARA`, `_CHILLU`.
- **Functions.**
  - Languages: `auto_languages`, `resolve_languages`, `char_script`, `script_counts`, `detect_languages`, `language_label`, `dominant_language`, `native_script_ratio`.
  - Cleaning: `fix_indic_confusions`, `clean_segment`, `collapse_repeated_words`, `is_noise_segment`, `normalize_list_marker`, `is_list_item`.
  - Layout: `estimate_skew`, `dedupe_overlapping`, `_group_rows`, `_split_cells`, `_join_segments`, `_cluster_anchors`, `_table_from_rows`, `reconstruct_layout`.
  - Confidence: `weighted_confidence`.
- **Dependencies.** Standard library only. **Called by:** `ocr_service.py`, `translation_service.py` (`dominant_language`), `app.py` (`detect_languages`, `UNKNOWN_LANGUAGE`), `tests/test_ocr_text.py`.

### `services/tesseract_engine.py` — Tesseract line recogniser (M: OCR)
- **Functions.** `tesseract_command`, `tessdata_dir`, `available_languages` (cached `--list-langs`), `_normalize_crop`, `read_lines` (stacked-sheet TSV recognition). Constant: `TESSERACT_CODES`.
- **Dependencies.** The Tesseract 5 binary (subprocess), OpenCV, NumPy.
- **Called by.** `ocr_service.py`.

### `services/translation_service.py` — translation (M: OCR)
- **Classes.** `TranslationError`, `NoTranslationFound`, `QuotaExceeded`, `TranslationService`.
- **Functions.** `resolve_target_language`, `_google`, `_mymemory`, `_describe_failure`, `TranslationService.providers/_available/_cache_key/_translate_chunk/translate_pages`, `_segments`, `_split_long_line`. Singleton `translation_service`.
- **Tables.** `TARGET_LANGUAGES`, `TARGET_ALIASES`, `_MYMEMORY_CODES`, `_LIMITS`, `PROVIDERS`.
- **Dependencies.** `deep-translator`, `ocr_text`.
- **Called by.** `app.py::translate_ocr_result`, `tests/test_translation.py`.

### `services/blockchain_service.py` — Web3 gateway (M: BC)
- **Classes.** `BlockchainUnavailable`, `BlockchainTransactionError`, `EvidenceBlockchainService`.
- **Methods.**
  - Connection: `is_rpc_alive`, `_redeploy_if_needed`, `_contract_address`, `_connect`, `reload`, `_ready`, `status`.
  - Transactions: `_sender`, `_transact`, `register_evidence`, `verify_evidence`, `_verified_event_result`, `transfer_custody`.
  - Reads: `contract_address` (property), `get_registration`, `find_registration_receipt`, `custody_history`, `recent_blocks`, `events_since`.
- **Dependencies.** web3.py, the Hardhat artifact (ABI), the deployment JSON.
- **Called by.** `app.py`, `backfill_blockchain_registration.py`.

### `backfill_blockchain_registration.py` (M: BC)
- **Functions.** `file_hash`, `audit`, `store_registration`, `process`, `main` (`--apply`).
- **Behaviour.** Registers or adopts legacy evidence, or marks it `Unregistered` with a reason (Algorithm 7).
- **Called by.** An operator (CLI).

### `migrate_ocr_results.py`, `migrate_blockchain.py`, `migrate_evidence_table.py`
Idempotent DDL scripts. The OCR one also de-duplicates rows and creates the `(evidence_id, page_number)` unique index.

### `setup_tessdata.py` (M: OCR)
Downloads `tessdata_best` models (English always, plus `OCR_TESSERACT_LANGUAGES`) into `backend/tessdata/`.

### `tests/`
| File | Tests | Covers |
|---|---|---|
| `test_ocr_text.py` | 25 | language resolution, script detection, cleaning (including Indic confusions and chillu), noise, layout (paragraphs, tables, lists, skew, tall boxes), deduplication, confidence |
| `test_ocr_engine_rules.py` | 6 | `restore_dropped_digits`, `_adds_missing_script` |
| `test_translation.py` | 9 | segmentation, fallback, rate-limit pause, partial or total failure, no-match, quota warning, target validation |

All 40 pass (`python -m unittest discover tests`). **No automated tests exist** for the blockchain service, the smart contract, the API endpoints or the BNS service.

### Configuration
- **`requirements.txt`:** `paddlepaddle==3.1.0`, `paddleocr>=3.7,<4`, `pypdfium2>=4.0`, `deep-translator>=1.11,<2`, `opencv-python`, `pillow`, `pdf2image`, `SQLAlchemy>=2.0`, `psycopg2-binary`, `web3>=7,<8`, `PyJWT`, `fastapi`, `supabase<2.5`, …
- **`.env.example`:** `OCR_*`, `TRANSLATION_*`, `MYMEMORY_EMAIL`, `TESSERACT_CMD`, `OCR_TESSDATA_DIR`, `OCR_TESSERACT_LANGUAGES`, `POPPLER_PATH`, `BLOCKCHAIN_AUTO_REDEPLOY`.

### `scratch/`
Developer diagnostics (`diagnose_ocr.py`, `test_ai_ocr_endpoint.py`, `inspect_paddle_*.py`, …). Not part of the runtime.

## 11.2 BNS service (`bns-backend/`)

| File | Purpose | Main definitions | Dependencies | Called by |
|---|---|---|---|---|
| `app/main.py` | HTTP API + metrics | `PredictRequest`, `SectionPrediction`, `PredictResponse`, `health`, `metrics`, `predict`, `predict_verbose`, `retrieve`, Prometheus counters and histograms, `_sync_postprocess_metrics_to_prometheus` | FastAPI, prometheus_client, `model_wrapper`, `postprocess` | `backend/app.py::bns_predict` over HTTP |
| `app/model_wrapper.py` | Inference wrapper | `RAGHGATWrapper.__init__` (loads Legal-BERT, MiniLM, FAISS, metadata, node features, edges, checkpoint, reranker), `_load_reranker`, `_encode_for_reranker`, `_apply_reranker`, `retrieve`, `predict` | torch, transformers, sentence-transformers, faiss, pickle | `main.py`, `scripts/train_reranker.py` |
| `app/hgat_model.py` | Network definition | `init_lin`, `ImprovedSectionHead`, `RAGLCHGATModel` (`_ensure_edge_index`, `infer_from_features`, `predict_proba`) | torch, torch_geometric (optional `GATConv`) | `model_wrapper.py` |
| `app/postprocess.py` | Legal rule engine | regexes (`AGE_RE`, `WEAPON_WORDS`, …), `CLUSTER_MAP`, `SECTION_TO_CLUSTER`, `CLUSTER_THRESHOLDS`, `extract_basic_attrs`, `build_meta_map`, `_normalize_raw_sections`, `post_process_predictions`, `get_metrics_snapshot` | `re`, `bns` | `main.py`, `model_wrapper.py` (cluster map) |
| `app/bns.py` | Section catalogue | `BNS_SECTION_DETAILS` (crime, title, description, severity, punishment, legal elements, keywords, cognizable, bailable, related sections…) | — | `postprocess.py`, `model_wrapper.py`, `main.py` fallbacks, `scripts/build_faiss.py`, `scripts/build_cooccur_graph.py` |
| `scripts/build_faiss.py` | Build the retrieval index | `load_bns_sections`, `build` (encode, save `.npy` and metadata, normalise, `IndexFlatIP`) | sentence-transformers, faiss | operator |
| `scripts/build_cooccur_graph.py` | Build the section graph | `build_cooccurrence` (edges between sections sharing keywords) | torch | operator |
| `scripts/train_reranker.py` | Train the reranker | `cluster_one_hot`, `extract_features_for_section`, `main` (LogisticRegression, `reranker.pkl`, config α=0.7) | scikit-learn | operator (never effective: `val.jsonl` is empty) |
| `scripts/validate_rerank.py`, `auto_retrain.py`, `persist_node_features.py` | Tuning, retraining and feature helpers | — | — | operator |
| `hgatm.ipynb` | Training and evaluation | data preparation, `AsymmetricLoss`, `FocalLoss`, training loop, `EarlyStopping`, metrics, plots, exports | torch, sklearn, pandas, matplotlib | researcher |
| `Model_Data/*` | Index, embeddings, metadata | — | — | `model_wrapper.py` |
| `data/*.csv` | Corpus and exported metrics (ablation rows 2–5 are placeholders) | — | — | notebook, report |

## 11.3 Smart contract (`blockchain/`)

| File | Purpose | Definitions | Called by |
|---|---|---|---|
| `contracts/EvidenceRegistry.sol` | Evidence registry and custody log | structs `Evidence`, `CustodyRecord`; functions `registerEvidence`, `verifyEvidence`, `getEvidence`, `addCustodyRecord`, `getCustodyHistory`; events `EvidenceRegistered`, `EvidenceVerified`, `CustodyTransferred` | `blockchain_service.py` via ABI |
| `hardhat.config.ts` | Compiler and network | solc 0.8.28, EVM `shanghai`, `localhost` at `http://127.0.0.1:8545` | `npx hardhat compile`, `deploy.js` |
| `scripts/deploy.js` | Deployment | `main()`: read artifact, `jsonRpcCall`, deploy from `accounts[0]`, poll the receipt, write `deployments/localhost.json` | operator, `/admin/blockchain/redeploy`, opt-in auto-redeploy |
| `deployments/localhost.json` | Current address | `address`, `transactionHash`, `chainId`, `deployedAt` | `blockchain_service.py` |
| `start-ganache.ps1`, `package.json` (`chain`) | Persistent node | Ganache with `--database.dbPath ganache-data` | operator |

## 11.4 Frontend (`audit-frontend/src/`)

| File | Role for these modules | Key functions / components |
|---|---|---|
| `services/api.ts` | HTTP client (Axios, JWT header) | `uploadEvidence`, `getEvidence`, `verifyHash`, `getEvidenceBlockchain`, `getBlockchainDashboard`, `redeployEvidenceRegistry`, `runOCR(evidenceId, language, {translate, target_language, force})` (300 s timeout), `searchOCR`, `predictBNS`, `storeBNS`, `getBNSResults`; helper `describeVerification` |
| `pages/OtherPages.tsx` | Feature pages | `EvidencePage` (upload, list, Verify Hash with the real result, status banners), `BNSPage` (classify / accept; hard-coded insight strings), `OCRPage` (upload + OCR, language modes, viewer, OCR search tab) |
| `pages/CaseDetail.tsx` | Case workspace | Evidence tab: Verify Integrity, Blockchain Details, custody timeline, status banners. OCR Analysis tab (summary + `OcrTextViewer`). BNS tab (stored prediction). |
| `components/OcrTextViewer.tsx` | OCR text viewer | page tabs, Original/Translated toggle, target selector, translation status, copy/download |
| `pages/BlockchainDashboard.tsx` | Chain dashboard | network status, counts, latest transactions and blocks |
| `pages/Dashboard.tsx` | Home dashboard | blockchain counts panel; tamper alert count |
| `components/UI.tsx` | UI kit | `Badge` colours for Verified / Tampered / Processing / Unregistered / Missing |
| `types/index.ts` | Types | `EvidenceStatus`, `BNSResult`, `BNSSection`, `CustodyRecord`, `BlockchainEvidence` |

## 11.5 Documentation
- `docs/BLOCKCHAIN_INTEGRATION.md`: operator guide (architecture, endpoints, persistence, statuses).
- `docs/technical-report/`: this report.
