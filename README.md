# Secure Audits — Digital Evidence & Investigation Support System

**Secure Audits** is a multi-service digital forensics and case management platform built for law enforcement and forensic investigation teams. It provides secure case tracking, OTP/JWT-based authentication, tamper-evident file integrity verification (SHA-256), blockchain-anchored chain-of-custody, AI-driven crime detection, multilingual OCR, BNS legal classification, audio forensics, and photogrammetric 3D crime scene reconstruction.

> Detailed blockchain setup, smart contract deployment, and custody tracking are documented in [docs/BLOCKCHAIN_INTEGRATION.md](docs/BLOCKCHAIN_INTEGRATION.md).

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Objectives](#2-objectives)
3. [Key Features](#3-key-features)
4. [System Architecture](#4-system-architecture)
5. [Technology Stack](#5-technology-stack)
6. [Project Structure](#6-project-structure)
7. [Database Design](#7-database-design)
8. [Workflows](#8-workflows)
9. [API Overview](#9-api-overview)
10. [Installation Guide](#10-installation-guide)
11. [Environment Variables](#11-environment-variables)
12. [Running the System](#12-running-the-system)
13. [Future Work](#13-future-work)
14. [Team Members](#14-team-members)

---

## 1. Problem Statement

Traditional law enforcement and forensic investigations rely on fragmented, offline workflows that make it difficult to maintain a reliable chain of custody for digital evidence. Insecure logging allows potential data tampering to go undetected, and investigators lack centralized, AI-assisted tools for rapid object detection, OCR analysis, and semantic legal search. Secure Audits addresses these challenges by providing a unified, audit-logged environment that safeguards evidence integrity, automates media analysis, supports semantic legal retrieval under the Bharatiya Nyaya Sanhita (BNS) framework, and anchors evidence records permanently to a blockchain.

---

## 2. Objectives

- **Secure Case Management:** Centralized case indexing with automatic sequential case number generation (`SA-YYYY-XXXX`).
- **Digital Evidence Storage:** Secure storage of forensic evidence files with SHA-256 integrity tracking and local file storage (`uploads/`).
- **Blockchain Chain-of-Custody:** Immutable on-chain registration and custody audit trail for every evidence item via the `EvidenceRegistry` smart contract.
- **AI-Assisted Analysis:** YOLOv8-based object/crime detection to scan evidence images for weapons, firearms, and contraband.
- **Multilingual OCR:** Automated text extraction from images and documents using PaddleOCR (PP-OCRv5) with Tesseract fallback for Kannada and Malayalam.
- **BNS Legal Classification:** Multi-label Bharatiya Nyaya Sanhita section prediction using a Hierarchical Graph Attention Network (HGAT) and Legal-BERT embeddings.
- **Audio Forensics:** Speech-to-text transcription, speaker diarization, and entity extraction from audio evidence using WhisperX.
- **3D Scene Reconstruction:** Photogrammetric 3D point cloud and mesh generation from crime scene video using COLMAP and Open3D.
- **Audit Trail Maintenance:** Append-only database logs capturing all system operations — logins, uploads, analysis, and blockchain events.
- **POLE Graph Visualization:** Interactive Person-Object-Location-Event (POLE) graphs mapping case entities and relationships.

---

## 3. Key Features

### Case Management
- Create cases with full FIR details: offence type, complainant, incident date/time/location, victims, and suspects (stored as JSONB).
- Automatic case number generation (`SA-YYYY-XXXX`) on the backend.
- Investigator assignment with role-based access control (`Admin` / `Investigator`).

### Evidence Management
- Upload photos, documents, videos, and audio files linked to a specific case.
- SHA-256 hash computed on upload and stored in the database.
- Local file storage under the `uploads/` directory.
- Per-evidence blockchain registration (transaction hash, block number, contract address stored in the `evidence` table).
- Chain-of-custody status tracking (`Collected`, `Verified`, `Transferred`).
- Duplicate detection by comparing file hashes before storage.

### Blockchain Chain-of-Custody
- Ethereum-compatible `EvidenceRegistry.sol` smart contract (Solidity 0.8.28) deployed on a local Ganache chain.
- On-chain registration of evidence metadata: `evidenceId`, `caseId`, `fileName`, `sha256Hash`, `uploadedBy`, `uploadTimestamp`.
- On-chain verification: `verifyEvidence()` compares stored hash against a newly computed hash.
- Ordered chain-of-custody log: `addCustodyRecord()` appends `REGISTERED`, `VERIFIED`, or `TRANSFERRED` events.
- Blockchain events: `EvidenceRegistered`, `EvidenceVerified`, `CustodyTransferred`.
- Blockchain interaction managed via `web3.py` in `backend/services/blockchain_service.py`.

### OCR Analysis
- Extracts text from images (JPEG, PNG) and multi-page PDFs using PaddleOCR (PP-OCRv5 mobile detection model).
- Tesseract 5 fallback for Kannada (`kn`) and Malayalam (`ml`) lines.
- Automatic language detection across English, Hindi, Kannada, Telugu, Tamil, and Malayalam.
- Document orientation correction and deskewing.
- Per-page results stored in `ocr_results` with confidence scores and `detected_languages` JSONB.
- Optional translation of extracted text via Google Translate / MyMemory APIs.

### Crime Object Detection
- YOLOv8-based object detection service (`crime-detection/`) running on port `8003`.
- Detects weapons (guns, knives), contraband, and other criminal objects from evidence images.
- Returns bounding box coordinates, class labels, and confidence scores stored in the `detections` table.

### BNS Legal Classification
- Multi-label Bharatiya Nyaya Sanhita (BNS) section classifier (`bns-backend/`) running on port `8001`.
- Model pipeline: Legal-BERT text embeddings → HGAT (`hgat_model.py`) → multi-label sigmoid classifier.
- Accepts FIR narrative text and optional metadata: `victim_age`, `victim_gender`, `num_offenders`, `weapon_used`.
- Returns ranked BNS sections with confidence scores, triggering sentences, natural-language XAI explanations, severity, and cognizability/bail status.
- FAISS-based semantic retrieval across BNS statutory definitions (`faiss-cpu`).
- Predictions stored in the `bns_predictions` table.

### Audio Forensics
- Audio analysis service (`audio-backend/`) running on port `8002`.
- WhisperX-based automatic speech recognition for transcribing voice notes, recorded interrogations, and phone taps.
- Speaker diarization via `pyannote.audio`.
- Entity extraction (names, dates, times, locations, keywords) from transcripts using spaCy (`en_core_web_sm`).
- Supports common audio formats via `pydub` and `soundfile`.

### Photogrammetry & 3D Reconstruction
- Photogrammetry service (`photogrammetry-backend/`) running on port `8004`.
- Accepts crime scene video uploads and extracts keyframes using `frame_extractor.py` and `frame_selector.py`.
- Runs COLMAP Structure-from-Motion (SfM) pipeline via `colmap_runner.py` to reconstruct sparse point clouds.
- Converts sparse reconstruction to dense point clouds and exports GLB/PLY meshes using Open3D (`open3d_processor.py`).
- Job status tracking (`Pending` → `Processing` → `Completed` / `Failed`) persisted in the `photogrammetry_models` table.
- Output model URLs stored in the database for frontend 3D rendering with Three.js.

### POLE Graph
- Interactive Person-Object-Location-Event relationship graph built with `@xyflow/react` (React Flow).
- Maps suspects, victims, locations, evidence items, and events within a case into a visual network graph.

### Audit Logging
- Append-only `audit_logs` table captures all system events: logins, logouts, uploads, analysis runs, blockchain actions, and integrity verifications.
- `user_id` stored as TEXT to decouple from user deletions.
- Metadata stored as JSONB for extensible event payloads.

### User & Role Management
- `Admin` role: full system access, user creation, and case management.
- `Investigator` role: case access governed by the `can_create_case` flag.
- `clearance_level` (1–5) for graduated data access.
- Forced password change flow for newly provisioned accounts (`ForcedPasswordPage`).

---

## 4. System Architecture

```
+--------------------------------------------------------------+
|             Frontend -- React + Vite + TypeScript            |
|                      http://localhost:5173                    |
+------+----------------------------+---------------------------+
       | REST (Axios)              | Supabase JS Client (Auth)
       v                           v
+-----------------+      +------------------------+
| FastAPI Backend |      | Supabase Auth (OTP)    |
| :8000 (py 3.10) |      | JWT issuance           |
+--------+--------+      +------------------------+
         | SQLAlchemy / psycopg2
         v
+------------------------------+
|   PostgreSQL Database        |
|   (schema.sql)               |
+------------------------------+
         | web3.py
         v
+------------------------------+
|  Ganache Local Chain :8545   |
|  EvidenceRegistry.sol        |
|  (Hardhat + Solidity 0.8.28) |
+------------------------------+

Microservices (called by FastAPI backend or directly by frontend):

  +--------------------+   +--------------------+
  | BNS Backend :8001  |   | Audio Backend :8002 |
  | HGAT + Legal-BERT  |   | WhisperX + pyannote |
  +--------------------+   +--------------------+

  +--------------------+   +--------------------------+
  | Crime Detection    |   | Photogrammetry Backend   |
  | :8003 -- YOLOv8    |   | :8004 -- COLMAP + Open3D |
  +--------------------+   +--------------------------+

Evidence Files -> Local Storage: uploads/
```

---

## 5. Technology Stack

### Frontend

| Library / Tool           | Version  | Purpose                                      |
|--------------------------|----------|----------------------------------------------|
| React                    | 18.x     | UI component framework                       |
| TypeScript               | 5.x      | Static typing                                |
| Vite                     | 5.x      | Build tool and dev server                    |
| React Router DOM         | 6.x      | Client-side routing                          |
| `@xyflow/react`          | 12.x     | POLE graph visualizations (React Flow)       |
| Three.js                 | 0.185+   | 3D model viewer for photogrammetry output    |
| Recharts                 | 2.x      | Dashboard analytics charts                   |
| `@supabase/supabase-js`  | 2.x      | Supabase Auth client (OTP / JWT)             |
| Axios                    | 1.x      | HTTP client for backend API calls            |
| `@excalidraw/excalidraw` | 0.18+    | Freehand sketch canvas                       |

### Backend (Core -- `backend/`)

| Library / Tool    | Version   | Purpose                                     |
|-------------------|-----------|---------------------------------------------|
| FastAPI           | latest    | REST API framework                          |
| Uvicorn           | latest    | ASGI server                                 |
| SQLAlchemy        | >= 2.0    | ORM for PostgreSQL                          |
| psycopg2-binary   | >= 2.9    | PostgreSQL driver                           |
| Alembic           | >= 1.13   | Database migrations                         |
| PaddleOCR         | >= 3.7    | OCR engine (PP-OCRv5)                       |
| PaddlePaddle      | 3.1.0     | Deep learning runtime for PaddleOCR         |
| pypdfium2         | >= 4.0    | PDF rendering for OCR                       |
| deep-translator   | >= 1.11   | OCR result translation                      |
| OpenCV            | latest    | Image preprocessing                         |
| Pillow            | latest    | Image I/O                                   |
| web3              | >= 7.0    | Blockchain interaction (EvidenceRegistry)   |
| PyJWT             | >= 2.10   | JWT auth token validation                   |
| bcrypt            | >= 4.2    | Password hashing                            |
| supabase          | < 2.5     | Supabase Python client (Auth integration)   |
| python-dotenv     | >= 1.0    | Environment variable loading                |

### BNS Classification Backend (`bns-backend/`)

| Library / Tool                | Purpose                                    |
|-------------------------------|--------------------------------------------|
| FastAPI + Uvicorn             | API framework and ASGI server              |
| PyTorch                       | Deep learning runtime                      |
| Transformers (HuggingFace)    | Legal-BERT embeddings                      |
| torch-geometric               | Hierarchical Graph Attention Network (HGAT)|
| sentence-transformers         | Semantic embedding (all-MiniLM-L6-v2)     |
| faiss-cpu                     | Vector index for BNS statutory retrieval  |
| spaCy (`en_core_web_sm`)      | Named entity recognition                  |
| scikit-learn                  | Classifier calibration utilities          |
| prometheus-client             | Metrics endpoint (`/metrics`)             |

### Audio Backend (`audio-backend/`)

| Library / Tool    | Purpose                                       |
|-------------------|-----------------------------------------------|
| WhisperX          | Speech-to-text transcription                  |
| pyannote.audio    | Speaker diarization                           |
| torchaudio        | Audio processing                              |
| pydub / soundfile | Audio format conversion and I/O               |
| SpeechRecognition | Fallback ASR integration                      |
| FastAPI + Uvicorn | API framework                                 |

### Crime Detection Backend (`crime-detection/`)

| Library / Tool       | Purpose                                       |
|----------------------|-----------------------------------------------|
| Ultralytics YOLOv8   | Object/weapon detection                       |
| OpenCV               | Image preprocessing                           |
| FastAPI + Uvicorn    | API framework                                 |

### Photogrammetry Backend (`photogrammetry-backend/`)

| Library / Tool        | Purpose                                                   |
|-----------------------|-----------------------------------------------------------|
| COLMAP (system binary)| Structure-from-Motion 3D reconstruction                   |
| Open3D >= 0.19        | Point cloud processing and mesh export (GLB/PLY)          |
| OpenCV < 4.11         | Frame extraction from video                               |
| FastAPI + Uvicorn     | API framework                                             |
| supabase              | Optional cloud upload of output files                     |

### Blockchain (`blockchain/`)

| Tool                   | Purpose                                         |
|------------------------|-------------------------------------------------|
| Solidity 0.8.28        | `EvidenceRegistry.sol` smart contract           |
| Hardhat                | Smart contract compilation and deployment       |
| Ganache (npx ganache)  | Local Ethereum chain at `localhost:8545`        |
| web3.py (backend)      | On-chain interactions from FastAPI              |

### Database

| Technology   | Role                                        |
|--------------|---------------------------------------------|
| PostgreSQL   | Primary relational database (via Supabase)  |
| Supabase     | Auth (OTP email login + JWT), hosted PostgreSQL |

---

## 6. Project Structure

```
secure-audit/
+-- audit-frontend/              # React + Vite + TypeScript client
|   +-- src/
|   |   +-- pages/               # Route-level page components
|   |   |   +-- AuthPage.tsx         # OTP login + Supabase Auth
|   |   |   +-- Dashboard.tsx        # Case and system overview
|   |   |   +-- Cases.tsx            # Case list
|   |   |   +-- CaseDetail.tsx       # Evidence, OCR, BNS, detection tabs
|   |   |   +-- CreateCase.tsx       # Case creation wizard
|   |   |   +-- AudioForensicsPage.tsx
|   |   |   +-- BlockchainDashboard.tsx
|   |   |   +-- UsersPage.tsx
|   |   |   +-- ProfilePage.tsx
|   |   |   +-- ForcedPasswordPage.tsx
|   |   |   +-- OtherPages.tsx       # OCR, POLE graph, photogrammetry, etc.
|   |   +-- components/          # Reusable UI components
|   |   +-- context/             # React context providers (Auth, etc.)
|   |   +-- services/            # Axios API service wrappers
|   |   +-- types/               # TypeScript type definitions
|   |   +-- styles/              # Global CSS
|   +-- package.json
|   +-- vite.config.ts
|
+-- backend/                     # FastAPI core backend -- port 8000
|   +-- app.py                   # Main FastAPI application (all routes)
|   +-- models.py                # SQLAlchemy ORM models
|   +-- db.py                    # Database connection and session
|   +-- services/
|   |   +-- blockchain_service.py    # web3.py EvidenceRegistry integration
|   |   +-- ocr_service.py           # PaddleOCR pipeline orchestration
|   |   +-- ocr_text.py              # OCR text post-processing
|   |   +-- tesseract_engine.py      # Tesseract fallback engine
|   |   +-- translation_service.py  # OCR result translation
|   +-- requirements.txt
|   +-- .env.example
|
+-- bns-backend/                 # BNS classification service -- port 8001
|   +-- app/
|   |   +-- main.py              # FastAPI app: /predict, /retrieve, /health
|   |   +-- multilabel_classifier.py  # Multi-label BNS pipeline
|   |   +-- hgat_model.py        # Hierarchical Graph Attention Network
|   |   +-- model_wrapper.py     # Model loading and inference wrapper
|   |   +-- bns.py               # Full BNS section definitions
|   |   +-- postprocess.py       # Score calibration and XAI generation
|   +-- requirements.txt
|
+-- audio-backend/               # Audio forensics service -- port 8002
|   +-- app.py                   # FastAPI app: transcription, diarization, entities
|   +-- requirements.txt
|
+-- crime-detection/             # Object/crime detection service -- port 8003
|   +-- objectdetection.py       # YOLOv8 inference + FastAPI routes
|   +-- main.py                  # Uvicorn entry point (port 8003)
|   +-- requirements.txt
|
+-- photogrammetry-backend/      # 3D reconstruction service -- port 8004
|   +-- app.py                   # FastAPI app: job submission and status
|   +-- db.py                    # Database session for job tracking
|   +-- models.py                # Photogrammetry job model
|   +-- services/
|   |   +-- frame_extractor.py   # Video -> keyframes
|   |   +-- frame_selector.py    # Keyframe quality filtering
|   |   +-- colmap_runner.py     # COLMAP SfM pipeline runner
|   |   +-- open3d_processor.py  # Point cloud -> GLB/PLY export
|   +-- requirements.txt
|
+-- blockchain/                  # Smart contracts and Ganache node
|   +-- contracts/
|   |   +-- EvidenceRegistry.sol # On-chain evidence & custody registry
|   +-- scripts/                 # Hardhat deployment scripts
|   +-- hardhat.config.ts        # Solidity 0.8.28, localhost network
|   +-- deployments/             # Deployed contract addresses (JSON)
|   +-- start-ganache.ps1        # Persistent Ganache launcher (port 8545)
|
+-- uploads/                     # Local evidence file storage
+-- schema.sql                   # Full PostgreSQL schema (source of truth)
+-- start_all.ps1                # One-command launcher for all 7 services
+-- docs/
|   +-- BLOCKCHAIN_INTEGRATION.md
+-- README.md
```

---

## 7. Database Design

The schema is defined in [`schema.sql`](schema.sql) and managed via SQLAlchemy ORM models in [`backend/models.py`](backend/models.py).

### `users`
Stores investigator and admin accounts. UUIDs are issued by Supabase Auth.

| Column            | Type        | Notes                              |
|-------------------|-------------|------------------------------------|
| `id`              | UUID PK     | Matches Supabase Auth UID          |
| `email`           | TEXT UNIQUE |                                    |
| `full_name`       | TEXT        |                                    |
| `role`            | TEXT        | `Admin` or `Investigator`          |
| `department`      | TEXT        |                                    |
| `badge_number`    | TEXT        |                                    |
| `clearance_level` | INTEGER     | Default `1`                        |
| `is_active`       | BOOLEAN     | Default `true`                     |
| `can_create_case` | BOOLEAN     | Default `true`                     |
| `last_login`      | TIMESTAMPTZ |                                    |
| `created_at`      | TIMESTAMPTZ |                                    |

### `cases`

| Column               | Type        | Notes                              |
|----------------------|-------------|------------------------------------|
| `id`                 | UUID PK     |                                    |
| `case_number`        | TEXT UNIQUE | Auto-generated `SA-YYYY-XXXX`      |
| `title`              | TEXT        |                                    |
| `offence_type`       | TEXT        |                                    |
| `fir_description`    | TEXT        |                                    |
| `fir_language`       | TEXT        | Default `en`                       |
| `complainant_name`   | TEXT        |                                    |
| `complainant_contact`| TEXT        |                                    |
| `victims`            | JSONB       | Array of victim objects            |
| `suspects`           | JSONB       | Array of suspect objects           |
| `incident_date`      | DATE        |                                    |
| `incident_time`      | TIME        |                                    |
| `incident_location`  | TEXT        |                                    |
| `created_by`         | UUID FK     | -> `users.id`                      |
| `created_by_name`    | TEXT        | Denormalized for display           |
| `created_at`         | TIMESTAMPTZ |                                    |

### `evidence`

| Column                       | Type        | Notes                                    |
|------------------------------|-------------|------------------------------------------|
| `id`                         | UUID PK     |                                          |
| `case_id`                    | UUID FK     | -> `cases.id` ON DELETE CASCADE          |
| `evidence_type`              | TEXT        |                                          |
| `description`                | TEXT        |                                          |
| `file_url`                   | TEXT        | Local path or URL                        |
| `file_hash`                  | TEXT        | SHA-256 digest                           |
| `file_name`                  | TEXT        |                                          |
| `file_size`                  | BIGINT      | Bytes                                    |
| `mime_type`                  | TEXT        |                                          |
| `uploaded_by`                | UUID FK     | -> `users.id`                            |
| `uploaded_by_name`           | TEXT        |                                          |
| `verified_at`                | TIMESTAMPTZ |                                          |
| `verified_by`                | UUID FK     | -> `users.id`                            |
| `chain_of_custody_status`    | TEXT        | `Collected`, `Verified`, `Transferred`   |
| `status`                     | TEXT        | `Verified` or `Tampered`                 |
| `blockchain_tx_hash`         | TEXT UNIQUE | Transaction hash of on-chain registration|
| `blockchain_block_number`    | BIGINT      |                                          |
| `blockchain_contract_address`| TEXT        |                                          |
| `blockchain_gas_used`        | BIGINT      |                                          |
| `blockchain_registered_at`   | TIMESTAMPTZ |                                          |
| `latest_verification_at`     | TIMESTAMPTZ |                                          |
| `created_at`                 | TIMESTAMPTZ |                                          |

### `evidence_custody_records`
Mirrors on-chain `CustodyRecord` events in the off-chain database.

| Column             | Type        | Notes                                        |
|--------------------|-------------|----------------------------------------------|
| `id`               | UUID PK     |                                              |
| `evidence_id`      | UUID FK     | -> `evidence.id` CASCADE                     |
| `officer_id`       | TEXT        |                                              |
| `action`           | TEXT        | `REGISTERED`, `VERIFIED`, `TRANSFERRED`      |
| `occurred_at`      | TIMESTAMPTZ |                                              |
| `transaction_hash` | TEXT UNIQUE |                                              |
| `block_number`     | BIGINT      |                                              |
| `created_at`       | TIMESTAMPTZ |                                              |

### `blockchain_logs`
Stores raw blockchain event payloads.

| Column             | Type        | Notes                     |
|--------------------|-------------|---------------------------|
| `id`               | UUID PK     |                           |
| `evidence_id`      | UUID FK     | -> `evidence.id` CASCADE  |
| `event_name`       | TEXT        |                           |
| `transaction_hash` | TEXT        |                           |
| `block_number`     | BIGINT      |                           |
| `payload`          | JSONB       | Full event data           |
| `created_at`       | TIMESTAMPTZ |                           |

### `audit_logs`

| Column       | Type        | Notes                                               |
|--------------|-------------|-----------------------------------------------------|
| `id`         | UUID PK     |                                                     |
| `user_id`    | TEXT        | TEXT (not FK) to survive user deletion              |
| `action`     | TEXT        |                                                     |
| `case_id`    | UUID FK     | -> `cases.id` CASCADE                               |
| `file_hash`  | TEXT        |                                                     |
| `metadata`   | JSONB       |                                                     |
| `created_at` | TIMESTAMPTZ |                                                     |

### `otp_tokens`

| Column       | Type        | Notes                   |
|--------------|-------------|-------------------------|
| `id`         | UUID PK     |                         |
| `user_id`    | UUID FK     | -> `users.id` CASCADE   |
| `token`      | TEXT        |                         |
| `expires_at` | TIMESTAMPTZ |                         |
| `used`       | BOOLEAN     | Default `false`         |
| `created_at` | TIMESTAMPTZ |                         |

### `detections`
Stores YOLOv8 object/crime detection results.

| Column        | Type        | Notes                                              |
|---------------|-------------|----------------------------------------------------|
| `id`          | UUID PK     |                                                    |
| `case_id`     | UUID FK     | -> `cases.id` CASCADE                              |
| `evidence_id` | UUID FK     | -> `evidence.id` CASCADE                           |
| `image_url`   | TEXT        |                                                    |
| `predictions` | JSONB       | Bounding boxes, class labels, confidence scores    |
| `created_at`  | TIMESTAMPTZ |                                                    |

### `ocr_results`
One row per evidence page; re-running OCR replaces existing rows.

| Column               | Type        | Notes                               |
|----------------------|-------------|-------------------------------------|
| `id`                 | UUID PK     |                                     |
| `evidence_id`        | UUID FK     | -> `evidence.id` CASCADE            |
| `extracted_text`     | TEXT        |                                     |
| `language`           | TEXT        |                                     |
| `confidence`         | FLOAT       |                                     |
| `page_number`        | INTEGER     | Default `1`                         |
| `detected_languages` | JSONB       | Per-language ratios and char counts |
| `ocr_metadata`       | JSONB       | Preprocessing steps, warnings, etc. |
| `created_at`         | TIMESTAMPTZ |                                     |

### `bns_predictions`

| Column       | Type        | Notes                                          |
|--------------|-------------|------------------------------------------------|
| `id`         | UUID PK     |                                                |
| `case_id`    | UUID FK     | -> `cases.id` CASCADE                          |
| `crime_type` | TEXT        | Top-level predicted crime category             |
| `sections`   | JSONB       | Array of section predictions with scores/XAI  |
| `fir_text`   | TEXT        | FIR input used for prediction                  |
| `created_at` | TIMESTAMPTZ |                                                |

### `photogrammetry_models`

| Column            | Type        | Notes                                               |
|-------------------|-------------|-----------------------------------------------------|
| `id`              | UUID PK     |                                                     |
| `case_id`         | UUID FK     | -> `cases.id` CASCADE                               |
| `evidence_id`     | UUID FK     | -> `evidence.id` CASCADE                            |
| `model_url`       | TEXT        | Path to exported GLB mesh                           |
| `point_cloud_url` | TEXT        | Path to PLY point cloud                             |
| `status`          | TEXT        | `Pending`, `Processing`, `Completed`, `Failed`      |
| `frame_count`     | INTEGER     |                                                     |
| `created_at`      | TIMESTAMPTZ |                                                     |
| `completed_at`    | TIMESTAMPTZ |                                                     |
| `error_message`   | TEXT        |                                                     |

---

## 8. Workflows

### Authentication Flow
```
User enters email
      |
      v
Supabase Auth sends OTP to email
      |
      v
User submits OTP -> Supabase validates -> Issues JWT
      |
      v
Frontend stores JWT -> Sent as Authorization header on all API requests
      |
      v
FastAPI backend validates JWT -> Looks up user record in PostgreSQL users table
```

### Case Creation
```
Investigator fills Case Wizard (FIR details, suspects, victims, location)
      |
      v
POST /cases -> FastAPI backend
      |
      v
Backend generates case_number (SA-YYYY-XXXX) -> Inserts into cases table
      |
      v
Audit log entry written (action: "case_created")
```

### Evidence Upload & Blockchain Registration
```
User selects evidence file
      |
      v
Backend computes SHA-256 hash
      |
      v
Checks hash against existing evidence (duplicate detection)
      |
      v
Saves file to uploads/ directory
      |
      v
Inserts evidence record in PostgreSQL (status: "Verified")
      |
      v
blockchain_service.py calls EvidenceRegistry.registerEvidence()
      |
      v
Stores tx_hash, block_number, contract_address in evidence table
      |
      v
Appends custody record (action: "REGISTERED") to evidence_custody_records
      |
      v
Audit log entry written (action: "evidence_uploaded")
```

### Evidence Integrity Verification
```
User triggers verification on an evidence item
      |
      v
Backend re-fetches file and recomputes SHA-256
      |
      +-- (Match) --> blockchain_service.py calls verifyEvidence()
      |                |
      |                v
      |             On-chain EvidenceVerified event emitted
      |                |
      |                v
      |             evidence.status = "Verified" | latest_verification_at updated
      |
      +-- (Mismatch) --> evidence.status = "Tampered"
                         |
                         v
                      Audit log: action = "evidence_tampered"
```

### OCR Analysis
```
User submits OCR request on an evidence image/PDF
      |
      v
backend/services/ocr_service.py fetches file from uploads/
      |
      v
PaddleOCR (PP-OCRv5) detects text regions per page
      |
      +-- Lines in kn/ml -> re-read by Tesseract 5 (tesseract_engine.py)
      |
      v
Language detection, confidence scoring, deskew/orientation correction
      |
      v
Upsert results into ocr_results (one row per page)
      |
      v
Optional: translation via translation_service.py (Google / MyMemory)
```

### BNS Legal Classification
```
User submits FIR text from a case
      |
      v
POST /predict -> bns-backend:8001
      |
      v
Legal-BERT encodes FIR text -> HGAT processes legal knowledge graph
      |
      v
Multi-label sigmoid classifier returns section scores
      |
      v
FAISS retrieval ranks BNS sections by semantic similarity
      |
      v
postprocess.py: calibrate scores, extract trigger sentences, generate XAI explanations
      |
      v
Results saved to bns_predictions table (via main backend)
```

### Crime Object Detection
```
User submits evidence image for detection
      |
      v
POST /detect -> crime-detection:8003
      |
      v
YOLOv8 model runs inference -> returns bounding boxes, labels, confidence scores
      |
      v
Results stored in detections table (via main backend)
      |
      v
Frontend renders annotated bounding boxes over evidence image
```

### Audio Forensics
```
User uploads audio evidence file
      |
      v
POST /transcribe -> audio-backend:8002
      |
      v
WhisperX: ASR transcription with word-level timestamps
      |
      v
pyannote.audio: speaker diarization (who spoke when)
      |
      v
spaCy: named entity extraction (persons, dates, locations, keywords)
      |
      v
Transcript + entities returned to frontend
```

### 3D Photogrammetry
```
User uploads crime scene video
      |
      v
POST /reconstruct -> photogrammetry-backend:8004
      |
      v
frame_extractor.py extracts frames at configured interval
      |
      v
frame_selector.py filters for sharpness and coverage quality
      |
      v
colmap_runner.py: COLMAP feature extraction -> matching -> SfM -> sparse point cloud
      |
      v
open3d_processor.py: dense reconstruction -> mesh -> export as GLB + PLY
      |
      v
photogrammetry_models table updated (status: "Completed", model_url, point_cloud_url)
      |
      v
Frontend loads GLB via Three.js for interactive 3D viewing
```

---

## 9. API Overview

All core API routes are served by the FastAPI backend on `http://localhost:8000`.

### Authentication
| Method | Endpoint          | Description                               |
|--------|-------------------|-------------------------------------------|
| POST   | `/auth/login`     | Verify OTP + JWT, create session          |
| POST   | `/auth/logout`    | Invalidate session, write audit log       |
| POST   | `/auth/register`  | Admin-provisioned user registration       |

### Cases
| Method | Endpoint       | Description                               |
|--------|----------------|-------------------------------------------|
| GET    | `/cases`       | List all cases accessible to the user     |
| POST   | `/cases`       | Create new case (generates case number)   |
| GET    | `/cases/{id}`  | Retrieve case detail                      |
| PUT    | `/cases/{id}`  | Update case metadata                      |
| DELETE | `/cases/{id}`  | Delete case (Admin only)                  |

### Evidence
| Method | Endpoint                  | Description                                    |
|--------|---------------------------|------------------------------------------------|
| GET    | `/cases/{id}/evidence`    | List evidence for a case                       |
| POST   | `/cases/{id}/evidence`    | Upload and register new evidence               |
| GET    | `/evidence/{id}`          | Get evidence detail                            |
| POST   | `/evidence/{id}/verify`   | Recompute hash + blockchain verification       |
| DELETE | `/evidence/{id}`          | Delete evidence item                           |

### Blockchain
| Method | Endpoint                                | Description                                   |
|--------|-----------------------------------------|-----------------------------------------------|
| GET    | `/evidence/{id}/blockchain`             | Get on-chain registration and custody history |
| POST   | `/evidence/{id}/blockchain/register`    | Manually trigger on-chain registration        |
| POST   | `/evidence/{id}/custody`               | Append custody record (VERIFIED/TRANSFERRED)  |

### OCR
| Method | Endpoint              | Description                              |
|--------|-----------------------|------------------------------------------|
| POST   | `/evidence/{id}/ocr`  | Run OCR on image/PDF evidence            |
| GET    | `/evidence/{id}/ocr`  | Retrieve stored OCR results              |

### Crime Detection
| Method | Endpoint                    | Description                              |
|--------|-----------------------------|------------------------------------------|
| POST   | `/evidence/{id}/detect`     | Run YOLOv8 object detection              |
| GET    | `/evidence/{id}/detections` | Retrieve stored detection results        |

### BNS Classification (`bns-backend` -- port 8001)
| Method | Endpoint       | Description                                       |
|--------|----------------|---------------------------------------------------|
| POST   | `/predict`     | Multi-label BNS section prediction from FIR text  |
| POST   | `/retrieve`    | Semantic BNS retrieval (FAISS)                    |
| GET    | `/health`      | Service health check                              |
| GET    | `/metrics`     | Prometheus metrics                                |

### Audio Forensics (`audio-backend` -- port 8002)
| Method | Endpoint        | Description                                        |
|--------|-----------------|---------------------------------------------------|
| POST   | `/transcribe`   | Transcribe audio file (WhisperX + diarization)    |
| GET    | `/health`       | Service health check                               |

### Photogrammetry (`photogrammetry-backend` -- port 8004)
| Method | Endpoint          | Description                                 |
|--------|-------------------|---------------------------------------------|
| POST   | `/reconstruct`    | Submit video for 3D reconstruction job      |
| GET    | `/jobs/{id}`      | Get job status and output URLs              |

### Users & Roles
| Method | Endpoint       | Description                               |
|--------|----------------|-------------------------------------------|
| GET    | `/users`       | List all users (Admin only)               |
| POST   | `/users`       | Create new user (Admin only)              |
| PUT    | `/users/{id}`  | Update user role, clearance, active status|
| DELETE | `/users/{id}`  | Deactivate user (Admin only)              |

### Audit Logs
| Method | Endpoint       | Description                        |
|--------|----------------|------------------------------------|
| GET    | `/audit-logs`  | Retrieve system audit logs         |

---

## 10. Installation Guide

### Prerequisites

- **Python 3.10** (required for all backend services)
- **Node.js 18+** and **npm**
- **PostgreSQL** (via Supabase hosted instance or local)
- **COLMAP** (system binary, added to `PATH`) -- required for photogrammetry
- **Tesseract OCR** (optional, for Kannada/Malayalam OCR fallback)
- **Git**

---

### 1. Clone the Repository

```bash
git clone <repository-url>
cd "Secure Audit"
```

---

### 2. Database Setup

Apply the schema to your PostgreSQL database (Supabase or local):

```bash
psql -U <your_user> -d <your_database> -f schema.sql
```

---

### 3. Core Backend (`backend/` -- port 8000)

```bash
cd backend
python -m venv venv
.\venv\Scripts\activate        # Windows
# source venv/bin/activate     # macOS/Linux
pip install -r requirements.txt

# Copy and configure environment variables
copy .env.example .env
# Edit .env with your values (see Environment Variables section)

py -3.10 app.py
```

---

### 4. BNS Classification Backend (`bns-backend/` -- port 8001)

```bash
cd bns-backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt

.\venv\Scripts\python.exe -m uvicorn app.main:app --port 8001 --reload
```

---

### 5. Audio Forensics Backend (`audio-backend/` -- port 8002)

```bash
cd audio-backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt

.\venv\Scripts\python.exe app.py
```

> **Note:** WhisperX and pyannote.audio models are downloaded automatically on first run. Ensure sufficient disk space (~2-5 GB) and a HuggingFace access token if pyannote model gating requires one.

---

### 6. Crime Detection Backend (`crime-detection/` -- port 8003)

```bash
cd crime-detection
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt

.\venv\Scripts\python.exe main.py
```

---

### 7. Photogrammetry Backend (`photogrammetry-backend/` -- port 8004)

> **Prerequisite:** Install COLMAP as a system binary and ensure it is on your system `PATH`. See [COLMAP installation guide](https://colmap.github.io/install.html).

```bash
cd photogrammetry-backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt

.\venv\Scripts\python.exe app.py
```

---

### 8. Blockchain Node (`blockchain/`)

```bash
cd blockchain
npm install

# Start persistent Ganache chain (port 8545, chain ID 1337)
.\start-ganache.ps1

# In a separate terminal: compile and deploy the EvidenceRegistry contract
npx hardhat compile
npx hardhat run scripts/deploy.ts --network localhost
```

> The deployed contract address is saved to `blockchain/deployments/`. The backend reads it automatically.

---

### 9. Frontend (`audit-frontend/` -- port 5173)

```bash
cd audit-frontend
npm install

# Copy and configure environment variables
copy .env.example .env
# Edit .env with your Supabase URL and anon key

npm run dev
```

---

### 10. Quick Launch (All Services)

To start all 7 services simultaneously in separate terminal windows:

```powershell
.\start_all.ps1 -NewWindows
```

This launches:
1. Ganache blockchain node (`:8545`)
2. FastAPI core backend (`:8000`)
3. BNS classification backend (`:8001`)
4. Audio forensics backend (`:8002`)
5. Crime detection backend (`:8003`)
6. Photogrammetry backend (`:8004`)
7. React frontend dev server (`:5173`)

---

## 11. Environment Variables

### `backend/.env`

```env
# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-supabase-service-role-key

# Auth
JWT_SECRET=your-jwt-auth-secret

# Email (OTP dispatch)
EMAIL_USER=your-smtp-email
EMAIL_PASSWORD=your-smtp-app-password

# Roboflow (used by crime-detection service)
ROBOFLOW_API_KEY=your-roboflow-api-key

# Storage: True = save files locally in uploads/, False = Supabase Storage
USE_LOCAL_STORAGE=True

# OCR configuration (PaddleOCR)
OCR_DET_MODEL=PP-OCRv5_mobile_det
OCR_AUTO_LANGUAGES=en,hi,kn,te,ta,ml
OCR_TESSERACT_LANGUAGES=kn,ml
OCR_LANGUAGE_RECHECK_THRESHOLD=0.93
OCR_MIN_LINE_CONFIDENCE=0.35
OCR_DOC_ORIENTATION=true
OCR_DESKEW=true
OCR_MIN_IMAGE_DIM=1600
OCR_MAX_IMAGE_DIM=2560
OCR_PDF_DPI=300
OCR_MAX_FILE_BYTES=52428800
OCR_MAX_PDF_PAGES=50
POPPLER_PATH=C:\Program Files\poppler\bin

# OCR Translation
TRANSLATION_PROVIDERS=google,mymemory
TRANSLATION_TIMEOUT_SECONDS=20
TRANSLATION_MAX_CHARS=30000
MYMEMORY_EMAIL=

# Blockchain
BLOCKCHAIN_AUTO_REDEPLOY=false
```

### `audit-frontend/.env`

```env
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-supabase-anon-key
VITE_API_BASE_URL=http://localhost:8000
```

### `bns-backend/.env`

```env
FRONTEND_ORIGIN=http://localhost:5173
MODEL_DIR=model_data
PORT=8001
LEGAL_BERT_NAME=nlpaueb/legal-bert-base-uncased
SENT_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

### `audio-backend/.env`

```env
PORT=8002
```

### `photogrammetry-backend/.env`

```env
SUPABASE_URL=your-supabase-project-url
SUPABASE_SERVICE_ROLE_KEY=your-supabase-service-role-key
UPLOAD_DIR=./uploads
OUTPUT_DIR=./outputs
COLMAP_BINARY=colmap
PORT=8004
```

---

## 12. Running the System

| Service                    | Command                                                                   | Port |
|----------------------------|---------------------------------------------------------------------------|------|
| Ganache blockchain node    | `npx ganache --server.host 127.0.0.1 --server.port 8545 --chain.chainId 1337 --wallet.deterministic --database.dbPath ./ganache-data` | 8545 |
| FastAPI core backend       | `py -3.10 app.py`                                                         | 8000 |
| BNS classification backend | `py -3.10 -m uvicorn app.main:app --port 8001 --reload`                   | 8001 |
| Audio forensics backend    | `py -3.10 app.py`                                                         | 8002 |
| Crime detection backend    | `py -3.10 main.py`                                                        | 8003 |
| Photogrammetry backend     | `py -3.10 app.py`                                                         | 8004 |
| React frontend             | `npm run dev`                                                             | 5173 |

Access the application at: **http://localhost:5173**

---

## 13. Future Work

- **Investigator AI Assistant (RAG):** Local generative LLM agent to query case notes, evidence text, OCR extracts, and BNS sections using Retrieval-Augmented Generation.
- **Real-Time Collaboration:** WebSocket-based collaborative case workspaces for joint remote audits.
- **Advanced Audio Diarization:** Real-time speaker identification during live interrogation sessions.
- **Government Deployment Infrastructure:** Docker Compose containerization templates for sovereign cloud or on-premise deployment.
- **Automated Case Timeline:** AI-generated storyboard compiling evidence tags, entity timelines, and incident sequences.

---

## 14. Team Members

| Name    | Roll Number  |
|---------|--------------|
| Ancilla | 4SO23CS026   |
| Amisha  | 4SO23CS019   |
| Apeksha | 4SO23CS031   |
| Alisha  | 4SO23CS017   |
