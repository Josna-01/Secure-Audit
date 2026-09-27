# Secure Audit System — Technical Report: OCR, BNS Classification and Blockchain Evidence Integrity

This report reverse-engineers three modules of the Secure Audit System directly from the source code:

1. the multilingual **OCR module** (PaddleOCR + Tesseract hybrid, translation),
2. the **BNS (Bharatiya Nyaya Sanhita) section classification module** (Legal-BERT + FAISS retrieval + graph attention network + rule-based post-processing),
3. the **blockchain evidence integrity module** (Solidity `EvidenceRegistry` contract on a Ganache Ethereum node, accessed through Web3.py).

It is written to be lifted into an IEEE research paper and a final-year project report. Every statement about behaviour cites the file (and, where useful, the function) that implements it. Nothing is described that the code does not do; where a requested topic has no implementation, the report says so explicitly.

## Chapters

| # | File | Contents |
|---|------|----------|
| 1 | [01-module-overview.md](01-module-overview.md) | Purpose, research objective, problem statement, contribution, architecture, inter-module interaction |
| 2 | [02-ocr-module.md](02-ocr-module.md) | OCR internals: input handling, preprocessing, detection, hybrid recognition, multilingual logic, layout, translation, mathematics |
| 3 | [03-ocr-database.md](03-ocr-database.md) | OCR tables, columns, JSONB schemas, caching and translation storage |
| 4 | [04-ocr-api.md](04-ocr-api.md) | Every OCR endpoint: request, response, validation, errors, frontend usage |
| 5 | [05-ocr-performance.md](05-ocr-performance.md) | Measured execution time, CPU/MKL-DNN, model selection, accuracy benchmark |
| 6 | [06-bns-module.md](06-bns-module.md) | BNS classification: RAG-HGAT model, retrieval, post-processing rule engine, training, APIs, mathematics |
| 7 | [07-blockchain-module.md](07-blockchain-module.md) | Smart contract, Web3 gateway, registration, verification, events, gas, mathematics |
| 8 | [08-database-interaction.md](08-database-interaction.md) | PostgreSQL / Supabase / storage interaction of all three modules, ER diagram |
| 9 | [09-security-analysis.md](09-security-analysis.md) | Authentication, authorization, integrity guarantees, attack surface |
| 10 | [10-algorithms.md](10-algorithms.md) | Pseudocode for every pipeline |
| 11 | [11-file-by-file.md](11-file-by-file.md) | Every source file involved, with purpose, functions and callers |
| 12 | [12-ieee-paper.md](12-ieee-paper.md) | Consolidated IEEE-style paper draft with references |

## Provenance

- **Source snapshot:** repository commit `b7b478c` ("feat: Handle missing/unregistered evidence & backfill").
- **Main backend:** `backend/` (FastAPI, Python 3.10.10). OCR, blockchain gateway and the BNS proxy live here.
- **BNS service:** `bns-backend/` (separate FastAPI service, expected on port 8001).
- **Smart contract:** `blockchain/` (Hardhat 3 project, Solidity 0.8.28).
- **Frontend:** `audit-frontend/` (React 18, TypeScript 5, Vite 5, Axios).

### Experimental environment (all measurements in this report)

| Item | Value |
|---|---|
| CPU | 13th Gen Intel Core i5-1335U (10 cores, 12 logical processors) |
| GPU | Intel Iris Xe (integrated; **not** usable by PaddlePaddle, which accelerates only NVIDIA CUDA) |
| RAM | 15.7 GB |
| OS | Windows 11 Pro 10.0.26200 |
| OCR stack | paddleocr 3.7.0, paddlepaddle 3.1.0 (CPU build, MKL-DNN enabled), paddlex 3.7.2, Tesseract 5.4.0 (`tessdata_best`), OpenCV 4.10.0, Pillow 12.3.0, NumPy 2.2.6, pypdfium2 5.12.1, deep-translator 1.11.4 |
| Blockchain stack | Ganache 7.9.2 (chain id 1337), web3.py 7.16.0, Solidity 0.8.28 (EVM target `shanghai`) |
| BNS stack | torch 2.13.0, transformers 5.14.1, sentence-transformers 5.6.1, faiss-cpu 1.15.0, torch-geometric 2.8.0.post1, scikit-learn 1.7.2 |
| Web stack | FastAPI 0.141.1, SQLAlchemy 2.0.51, PostgreSQL (via Supabase), React 18 |

### Evidence conventions

Each technical claim is backed by one of:

- **[code]** — read directly from the cited source file;
- **[measured]** — executed during the preparation of this report on the environment above (OCR accuracy/timing benchmarks, blockchain gas figures, BNS retrieval probe);
- **[reported]** — a figure recorded in a repository artefact but not re-measured here (e.g. BNS training metrics in `bns-backend/data/model_performance_summary.csv`).

Status markers used throughout: **Implemented**, **Partially implemented**, **Not implemented**.

> **Important for the paper.** Several requested topics are *not implemented* in this codebase and must not be claimed: page-level perspective (keystone) correction, OCR precision/recall/F1 and WER computation in the application, Merkle trees in application logic, LLM prompt engineering in BNS classification, on-chain anchoring of OCR results or BNS predictions. Each is discussed where it arises. In addition, the deployed BNS service currently runs in retrieval-only mode (no trained checkpoint is present) and has a score-inversion defect that is demonstrated in Chapter 6; the reported BNS training metrics describe the model in the training notebook, not the deployed service.
