# Secure Audit — Digital Evidence and Investigation Support System

[![React](https://img.shields.io/badge/Frontend-React%2018%20%7C%20Vite-blue?logo=react)](audit-frontend/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI%20%7C%20Python%203.10-009688?logo=fastapi)](backend/)
[![Blockchain](https://img.shields.io/badge/Blockchain-Ethereum%20%7C%20Solidity%200.8.28-3C3C3D?logo=ethereum)](blockchain/)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL%2015-336791?logo=postgresql)](docs/)
[![AI-Vision](https://img.shields.io/badge/AI-YOLOv8%20%7C%20COLMAP%203D-FF6F00)](crime-detection/)
[![AI-NLP](https://img.shields.io/badge/NLP-Legal--BERT%20%7C%20HGAT%20%7C%20BNS-8E24AA)](bns-backend/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

An enterprise-grade, multi-service digital forensics and investigation management platform for law enforcement agencies, cyber cells, and forensic examiners. Provides end-to-end evidence chain-of-custody tracking, tamper-evident cryptographic verification, Ethereum-anchored blockchain logging, multilingual document OCR, AI crime object detection, 3D crime scene photogrammetry, audio deepfake & speech forensics, and automated legal classification under the **Bharatiya Nyaya Sanhita (BNS)**.

---

## Table of Contents

1. [Project Title](#1-project-title)
2. [Overview](#2-overview)
3. [Features](#3-features)
4. [System Architecture](#4-system-architecture)
5. [Project Structure](#5-project-structure)
6. [Technology Stack](#6-technology-stack)
7. [System Workflow](#7-system-workflow)
8. [Module Descriptions](#8-module-descriptions)
9. [API Overview](#9-api-overview)
10. [Database Design](#10-database-design)
11. [Blockchain Integration](#11-blockchain-integration)
12. [AI Components](#12-ai-components)
13. [Security Features](#13-security-features)
14. [Installation](#14-installation)
15. [Running the Project](#15-running-the-project)
16. [Environment Variables](#16-environment-variables)
17. [Screenshots](#17-screenshots)
18. [Future Scope](#18-future-scope)
19. [Contributors](#19-contributors)
20. [License](#20-license)

---

## 1. Project Title

**Secure Audit** — *Digital Evidence and Investigation Support System*

---

## 2. Overview

### Purpose
Modern criminal investigations generate vast quantities of digital evidence (CCTV footage, intercepted audio, weapon imagery, scanned FIR documents, and mobile forensics). Traditional evidence handling relies on fragmented storage and manual logs, leaving evidence vulnerable to physical tampering, digital alterations, and procedural chain-of-custody challenges in court.

### Problem Statement
1. **Chain of Custody Vulnerability:** Lack of tamper-evident, decentralized verification makes proving evidence integrity difficult under legal scrutiny.
2. **Analysis Bottlenecks:** Manual examination of hours of surveillance video, multilingual FIRs, and forensic audio logs slows down charge-sheet filing.
3. **Legal Classification Complexity:** Mapping intricate incident narratives to newly enacted criminal codes (**Bharatiya Nyaya Sanhita, 2023**) requires specialized legal cross-referencing.
4. **Spatial Evidence Loss:** 2D crime scene photographs fail to preserve critical spatial geometry, distances, and 3D weapon trajectories.

### Objectives
- **Cryptographic Evidence Anchoring:** Compute SHA-256 digests on ingest and anchor them to an Ethereum smart contract ledger for mathematically verifiable integrity.
- **Automated AI Triage:** Detect weapons and illicit objects (YOLOv8), transcribe and analyze forensic audio (WhisperX & pyannote), and reconstruct 3D spatial scenes (COLMAP & Open3D).
- **Multilingual Legal Extraction:** Extract text from regional FIRs and legal documents with multilingual OCR (PaddleOCR/Tesseract) and classify applicable BNS penal sections with Explainable AI (Legal-BERT + HGAT).
- **Strict Role-Based Governance:** Enforce granular access control (Admin, Investigator, Forensic Examiner) backed by append-only audit trails.

### Real-World Use Case
A police department registers a multi-jurisdiction armed robbery. The investigation team uploads CCTV video, recovered weapon images, scanned regional FIRs, and recorded witness interviews. Secure Audit hashes each artifact onto the blockchain, extracts regional text from the FIR, predicts applicable BNS sections (e.g., robbery, armed assembly), runs weapon detection across footage, transcribes audio, builds a navigable 3D point cloud of the crime scene, and exports a tamper-proof court-admissible forensic report.

---

## 3. Features

### Authentication & Authorization
- **Supabase & JWT Authentication:** Secure login with session tokens and role-based payload validation.
- **Role-Based Access Control (RBAC):** Strict operational permissions for `Admin`, `Investigator`, and `Forensic Examiner`.
- **Session Security:** Automatic token validation and revocation handling.

### Case Management
- **Centralized Case Registry:** Unique, standardized case numbers (`SA-YYYY-XXXX`).
- **FIR Incident Details:** Structured metadata capture (offence category, incident timestamp, geographic location, complainant, victims, and suspects).
- **Investigator Assignment:** Link case responsibility to authorized officers and forensic teams.
- **POLE Entity Graphs:** Interactive Person-Object-Location-Event entity relationship mapping.

### Evidence Management
- **Multi-Format Ingestion:** Support for images (`.jpg`, `.png`, `.webp`), videos (`.mp4`, `.mov`, `.avi`), audio (`.mp3`, `.wav`, `.m4a`), and documents (`.pdf`).
- **Cryptographic Hashing:** Automated SHA-256 fingerprint generated at the exact millisecond of upload.
- **Structured Case Partitioning:** Secure local storage partitioned by case UUIDs (`backend/uploads/cases/{case_id}/`).
- **Duplicate Detection:** Automatic pre-upload hash comparison against historical records to prevent redundant storage.

### Blockchain Verification
- **Smart Contract Registry:** `EvidenceRegistry.sol` (Solidity 0.8.28) deployed on Ethereum/Ganache.
- **Immutable State Logs:** On-chain storage of `evidenceId`, `caseId`, `sha256Hash`, `uploader`, and `timestamp`.
- **One-Click Integrity Verification:** Live re-hashing of stored binary files compared against on-chain smart contract state with instant status badge (`Verified` / `Tampered`).
- **Custody Transfer Auditing:** Smart-contract-enforced custody change logs (`REGISTERED`, `VERIFIED`, `TRANSFERRED`).

### Optical Character Recognition (OCR)
- **High-Accuracy Multilingual Engine:** PaddleOCR (PP-OCRv5) for primary document and print parsing.
- **Regional Script Support:** Tesseract 5 fallback for regional Indic scripts (Kannada, Malayalam, Hindi, Tamil, Telugu).
- **Preprocessing & Normalization:** Automatic document deskewing, binarization, and orientation correction.
- **PDF Extraction:** Automatic multi-page PDF rasterization and page-by-page text mapping.

### Translation
- **Multilingual Legal Translation:** Translate regional FIR and witness text into English/standard format using integrated translation pipelines.
- **Preserved Entity Context:** Retains legal terminology and named entities during translation passes.

### BNS Legal Prediction
- **Bharatiya Nyaya Sanhita (BNS) Classification:** Multi-label neural classification predicting applicable criminal sections from FIR narratives.
- **Hybrid AI Architecture:** Legal-BERT sentence embeddings + Hierarchical Graph Attention Network (HGAT).
- **Explainable AI (XAI):** Sentence-level highlighting of narrative triggers justifying each predicted section.
- **Semantic Vector Search:** FAISS vector indexing over statutory definitions with penalty duration and cognizability metadata.

### 3D Photogrammetry & Scene Reconstruction
- **Automated Video-to-3D Pipeline:** Extract keyframes from crime scene video walkthroughs.
- **Structure-from-Motion (SfM):** COLMAP sparse and dense point cloud estimation.
- **Point Cloud & Mesh Post-Processing:** Open3D noise filtering, surface Poisson reconstruction, and GLB asset export.
- **Interactive Three.js Viewer:** Orbit, pan, zoom, and take spatial measurements directly inside the browser dashboard.

### Audio Forensics
- **Speech-to-Text Transcription:** WhisperX automatic speech recognition for recorded calls and interrogation tapes.
- **Speaker Diarization:** pyannote.audio speaker separation and voice turn timestamps.
- **Deepfake Audio Detection:** Acoustic frequency spectrum analysis and synthetic voice artifact scoring.
- **Forensic Entity Extraction:** Automatic extraction of named entities (names, times, locations) from transcripts via spaCy.

### Crime & Weapon Detection
- **Computer Vision Inference:** YOLOv8 neural network trained on forensic object datasets.
- **Threat Detection:** Real-time localization and bounding-box annotation for firearms, knives, and contraband.
- **Evidence Cross-Referencing:** Detected weapon classes automatically linked to case storyboard and BNS charge recommendations.

### Audit Logs & Governance
- **Append-Only Action Logs:** Every login, upload, verification, AI execution, and status change recorded with user ID, IP address, and timestamp.
- **Tamper-Evident History:** Unalterable chronological audit logs exportable for departmental compliance.

### User Management
- **Officer & Specialist Directory:** Manage registered investigators, department badges, and assigned roles.
- **Activity Monitoring:** Track officer active cases and forensic review history.

### Case Notes & Collaboration
- **Time-Stamped Case Annotations:** Add categorized forensic remarks, investigator notes, and forensic hypotheses directly to case files.

---

## 4. System Architecture

Secure Audit is built as a modular, distributed microservices architecture communicating via REST APIs and Web3 JSON-RPC protocols:

```
                                  +--------------------------------------------------+
                                  |            React 18 Frontend Dashboard           |
                                  |         (Vite + TailwindCSS + Lucide Icons)      |
                                  +------------------------+-------------------------+
                                                           |
                                                REST API / JWT Session
                                                           |
                                                           v
                                  +--------------------------------------------------+
                                  |            Core Backend Gateway (8000)           |
                                  |           FastAPI + SQLAlchemy + Pydantic        |
                                  +---+------------+------------+---------------+----+
                                      |            |            |               |
             +------------------------+            |            |               +-----------------------+
             |                                     |            |                                       |
             v                                     v            v                                       v
+------------------------+             +--------------+  +--------------+                   +------------------------+
|   PostgreSQL Database  |             |  Blockchain  |  | Supabase Auth|                   | Local Evidence Storage |
|  (Cases, Evidence,     |             |  (Ethereum / |  | (User Session|                   | (backend/uploads/      |
|   Detections, Audits)  |             |   Ganache)   |  |   & JWTs)    |                   |  cases/{case_id}/)     |
+------------------------+             +--------------+  +--------------+                   +------------------------+
             ^
             |
             +--------------------------------------------------------------------------------------------------+
             |                                              |                                                   |
             v                                              v                                                   v
+------------------------+                    +---------------------------+               +-----------------------------------+
|  Crime Detection (8003)|                    |    BNS Backend (8001)     |               |   Photogrammetry Backend (8002)   |
|   YOLOv8 Computer      |                    | Legal-BERT + HGAT Network |               |   COLMAP SfM + Open3D Meshing     |
|   Vision Service       |                    | + FAISS Statutory Search  |               |   Jobs: input_video -> GLB model  |
+------------------------+                    +---------------------------+               +-----------------------------------+
             |
             v
+------------------------+
|  Audio Backend (8004)  |
|  WhisperX + pyannote   |
|  Speech & Deepfake AI  |
+------------------------+
```

---

## 5. Project Structure

```
Secure Audit/
├── audit-frontend/             # React 18 frontend (Vite, TailwindCSS, Three.js)
│   ├── src/
│   │   ├── components/         # Reusable UI widgets, navigation, 3D viewers
│   │   ├── pages/              # Dashboard, Cases, Evidence, BNS, Photogrammetry
│   │   ├── context/            # Authentication & application state providers
│   │   └── services/           # Axios HTTP API client integration
│   ├── package.json            # Node.js dependencies
│   └── vite.config.js          # Vite build configuration
│
├── backend/                    # Core API Gateway (FastAPI, Port 8000)
│   ├── services/               # Blockchain, OCR, Translation, AI orchestration
│   ├── uploads/                # Local evidence storage (partitioned by case UUID)
│   │   └── cases/              # Active case evidence files
│   ├── app.py                  # Main FastAPI application router and endpoints
│   ├── models.py               # SQLAlchemy database models
│   ├── schemas.py              # Pydantic validation schemas
│   └── database.py             # PostgreSQL connection lifecycle
│
├── bns-backend/                # Bharatiya Nyaya Sanhita NLP Service (Port 8001)
│   ├── app/                    # FastAPI routes, HGAT inference engine, FAISS search
│   ├── Model_Data/             # HGAT weights, FAISS embeddings, metadata
│   ├── hgat_model.py           # Hierarchical Graph Attention Network definition
│   └── main.py                 # Microservice entrypoint
│
├── photogrammetry-backend/     # 3D Reconstruction Microservice (Port 8002)
│   ├── services/               # FrameExtractor, FrameSelector, ColmapRunner, Open3DProcessor
│   ├── jobs/                   # Isolated 3D job workspaces (frames, COLMAP, GLB)
│   ├── app.py                  # Job queue and execution lifecycle API
│   └── models.py               # 3D job database models
│
├── crime-detection/            # YOLOv8 Weapon & Crime Vision Service (Port 8003)
│   ├── model/                  # YOLOv8 weights (crime_best.pt, yolov8n.pt)
│   └── main.py                 # Real-time frame & image inference endpoint
│
├── audio-backend/              # Speech & Audio Forensics Service (Port 8004)
│   ├── services/               # WhisperX transcriber, pyannote diarizer, deepfake scorer
│   └── app.py                  # Audio analysis endpoints
│
├── blockchain/                 # Ethereum Smart Contracts & Migrations
│   ├── contracts/              # EvidenceRegistry.sol
│   ├── migrations/             # Truffle deployment scripts
│   └── truffle-config.js       # Ganache / EVM network settings
│
├── docs/                       # Architectural documentation & technical papers
└── README.md                   # Project documentation
```

---

## 6. Technology Stack

| Domain | Technologies |
| :--- | :--- |
| **Frontend** | React 18, Vite, TailwindCSS, Lucide Icons, Three.js, Axios, React Router 6 |
| **Core Backend** | Python 3.10, FastAPI, Uvicorn, SQLAlchemy, Pydantic, Web3.py |
| **Database** | PostgreSQL 15, Supabase Database |
| **Authentication** | Supabase Auth, JWT Tokens, PBKDF2 Hashing |
| **Blockchain** | Ethereum, Solidity 0.8.28, Truffle Suite, Ganache CLI / Local Node |
| **Computer Vision** | YOLOv8 (Ultralytics), OpenCV, Pillow |
| **3D Reconstruction** | COLMAP (Structure-from-Motion & Multi-View Stereo), Open3D, NumPy |
| **NLP & Legal AI** | Legal-BERT, PyTorch, PyTorch Geometric (HGAT), FAISS, Hugging Face Transformers |
| **Speech & Audio** | WhisperX (Faster-Whisper), pyannote.audio, Librosa, SoundFile, spaCy |
| **OCR & Text** | PaddleOCR (PP-OCRv5), Tesseract 5, PyMuPDF, pdf2image |

---

## 7. System Workflow

```
[ Investigator Login ]
          │
          ▼
[ Create Forensic Case ] ──► (Generates SA-YYYY-XXXX & DB Record)
          │
          ▼
[ Upload Evidence File ]
          │
          ├──────────────────────────────────────────────────────┐
          ▼                                                      ▼
[ Compute SHA-256 Digest ]                               [ Save Binary File ]
          │                                            (backend/uploads/cases/{id}/)
          ▼
[ Register on Blockchain ]
(EvidenceRegistry.sol on Ganache)
          │
          ├──────────────────────────┬──────────────────────────┬──────────────────────────┐
          ▼                          ▼                          ▼                          ▼
  [ Document / Image ]        [ Crime Image ]             [ Scene Video ]           [ Audio Tape ]
          │                          │                          │                          │
          ▼                          ▼                          ▼                          ▼
  [ Multilingual OCR ]     [ YOLOv8 Detection ]     [ Frame Selection & SfM ]    [ WhisperX Diarization ]
          │                          │                          │                          │
          ▼                          ▼                          ▼                          ▼
  [ Regional Translate ]   [ Weapon Bounding Boxes]   [ COLMAP + Open3D Meshing ] [ Deepfake Detection ]
          │                          │                          │                          │
          ▼                          │                          ▼                          │
  [ Legal-BERT + HGAT ]              │                 [ Three.js 3D View ]                │
  [ BNS Code Prediction]             │                          │                          │
          │                          │                          │                          │
          └──────────────────────────┴──────────────────────────┴──────────────────────────┘
                                     │
                                     ▼
                        [ Append-Only Audit Log ]
                                     │
                                     ▼
                     [ Live Hash Verification in UI ]
                     (Local SHA-256 vs. Blockchain Ledger)
```

---

## 8. Module Descriptions

### Core API Gateway (`backend/`)
The central orchestrator of Secure Audit. Exposes RESTful endpoints for case lifecycles, user administration, evidence ingestion, SHA-256 computation, Web3 smart contract calls, and dispatches asynchronous tasks to downstream AI microservices.

### BNS Legal Prediction Service (`bns-backend/`)
Consumes FIR narratives, incident facts, and metadata (victim demographics, weapons used). Utilizes a fine-tuned Legal-BERT model coupled with a Hierarchical Graph Attention Network (HGAT) to classify applicable sections of the **Bharatiya Nyaya Sanhita, 2023** and provide sentence-level XAI explanations.

### Photogrammetry & 3D Reconstruction (`photogrammetry-backend/`)
Processes crime scene walkthrough videos into high-density 3D spatial models. Operates an end-to-end pipeline: video frame extraction $
ightarrow$ sharpness-based keyframe selection $
ightarrow$ COLMAP Structure-from-Motion (SfM) $
ightarrow$ Open3D Poisson surface reconstruction $
ightarrow$ web-optimized `.glb` export.

### Crime Object Detection (`crime-detection/`)
A high-throughput computer vision service utilizing YOLOv8. Scans uploaded crime scene photos and CCTV stills to locate, classify, and score confidence for lethal weapons (firearms, knives), contraband, and forensic artifacts.

### Audio Forensics Service (`audio-backend/`)
Dedicated speech processing engine. Performs GPU-accelerated WhisperX transcription, pyannote speaker diarization, named entity recognition (NER), and spectral analysis to calculate synthetic voice (deepfake) probability.

### Blockchain Evidence Registry (`blockchain/`)
Contains the Solidity smart contract `EvidenceRegistry.sol`. Serves as the immutable root of trust, recording cryptographic hashes, case mappings, and chronological custody transfers across Ganache or any EVM-compatible network.

---

## 9. API Overview

The platform exposes structured REST APIs across all running microservices:

| Group | Base Route | Description |
| :--- | :--- | :--- |
| **Authentication** | `POST /auth/login`, `POST /auth/register` | User authentication, token issuance, password management |
| **Cases** | `GET/POST /cases/`, `GET /cases/{id}` | Case creation, FIR details, investigator assignment, POLE data |
| **Evidence** | `POST /evidence/upload`, `GET /evidence/{id}` | File ingestion, SHA-256 calculation, metadata retrieval |
| **Blockchain** | `POST /blockchain/verify`, `GET /blockchain/custody/{id}` | On-chain hash verification, block info, custody logs |
| **OCR & Text** | `POST /ocr/extract`, `POST /ocr/translate` | PaddleOCR/Tesseract parsing and multilingual translation |
| **BNS AI** | `POST http://localhost:8001/predict` | BNS section prediction, XAI rationale, penalty lookup |
| **Photogrammetry** | `POST http://localhost:8002/reconstruct` | Trigger 3D scene reconstruction job, status polling, GLB output |
| **Crime Vision** | `POST http://localhost:8003/detect` | YOLOv8 object and weapon bounding box detection |
| **Audio Forensics**| `POST http://localhost:8004/analyze` | WhisperX transcription, diarization, and deepfake scoring |
| **Audit Logs** | `GET /audit/logs`, `GET /audit/case/{id}` | Immutable system activity logs and compliance history |
| **Users** | `GET/POST /users/`, `PATCH /users/{id}/role` | Officer administration, RBAC roles, profile management |

---

## 10. Database Design

Secure Audit uses a relational PostgreSQL database schema managed through SQLAlchemy ORM:

```mermaid
erDiagram
    USERS ||--o{ CASES : "assigned_to"
    CASES ||--o{ EVIDENCE : "contains"
    CASES ||--o{ AUDIT_LOGS : "tracks"
    CASES ||--o{ BNS_PREDICTIONS : "evaluates"
    EVIDENCE ||--o{ DETECTIONS : "detects"
    EVIDENCE ||--o{ OCR_RESULTS : "extracts"
    EVIDENCE ||--o{ PHOTOGRAMMETRY_JOBS : "reconstructs"

    USERS {
        uuid id PK
        string email
        string full_name
        string role
        string badge_number
        timestamp created_at
    }

    CASES {
        uuid id PK
        string case_number
        string title
        string status
        jsonb fir_details
        uuid assigned_investigator_id FK
        timestamp created_at
    }

    EVIDENCE {
        uuid id PK
        uuid case_id FK
        string file_name
        string file_url
        string file_hash
        string mime_type
        bigint file_size
        string blockchain_tx_hash
        timestamp created_at
    }

    AUDIT_LOGS {
        uuid id PK
        uuid case_id FK
        uuid user_id FK
        string action
        jsonb details
        string ip_address
        timestamp timestamp
    }

    BNS_PREDICTIONS {
        uuid id PK
        uuid case_id FK
        jsonb predicted_sections
        jsonb xai_highlights
        timestamp created_at
    }

    DETECTIONS {
        uuid id PK
        uuid evidence_id FK
        string detected_class
        float confidence
        jsonb bounding_box
    }

    PHOTOGRAMMETRY_JOBS {
        uuid id PK
        uuid evidence_id FK
        string status
        int current_step
        string model_glb_url
        int vertex_count
    }
```

---

## 11. Blockchain Integration

### Cryptographic Evidence Integrity
1. **Hashing on Ingestion:** When an evidence file reaches the backend, its binary stream is processed through SHA-256:
   $$	ext{Evidence Hash} = 	ext{SHA-256}(	ext{Raw Binary Data})$$
2. **Smart Contract Storage:** The hash is anchored permanently into the Ethereum smart contract via `EvidenceRegistry.sol`:
   ```solidity
   function registerEvidence(
       string memory _evidenceId,
       string memory _caseId,
       string memory _fileName,
       string memory _sha256Hash
   ) public returns (bool);
   ```
3. **Chain of Custody Tracking:** Any transfer of evidence between investigators or forensic labs appends an on-chain event (`CustodyTransferred`).
4. **Verification Workflow:** During court presentation or audit review, the system reads the stored file, re-computes its SHA-256 hash in real-time, queries the smart contract, and evaluates:
   $$	ext{Status} = egin{cases} \mathbf{VERIFIED} & 	ext{if } 	ext{SHA-256}(	ext{File}) == 	ext{Hash}_{	ext{Blockchain}} \ \mathbf{TAMPERED} & 	ext{if } 	ext{SHA-256}(	ext{File}) 
eq 	ext{Hash}_{	ext{Blockchain}} \end{cases}$$

---

## 12. AI Components

| AI Engine | Model / Architecture | Primary Function | Input $
ightarrow$ Output |
| :--- | :--- | :--- | :--- |
| **Crime Detection** | YOLOv8 (`crime_best.pt`) | Detect weapons, firearms, knives | Image/Video $
ightarrow$ Annotated Bounding Boxes + Confidence |
| **BNS Classifier** | Legal-BERT + HGAT Network | Multi-label penal section prediction | FIR Narrative $
ightarrow$ Top BNS Sections + XAI Triggers |
| **Semantic Search** | FAISS + SentenceTransformers | Fast statutory law retrieval | Legal Query $
ightarrow$ Relevant Statutory Articles & Penalties |
| **Multilingual OCR**| PaddleOCR (PP-OCRv5) + Tesseract 5 | Text extraction from regional documents | Scanned FIR Image/PDF $
ightarrow$ Extracted Unicode Text |
| **3D Photogrammetry**| COLMAP (SfM) + Open3D | 3D crime scene reconstruction | Walkthrough Video $
ightarrow$ Dense Point Cloud + 3D Mesh (GLB) |
| **Audio Forensics** | WhisperX + pyannote.audio | Speech-to-text & deepfake scoring | Audio Recording $
ightarrow$ Diarized Transcript + Fake Score |

---

## 13. Security Features

- **Decentralized Integrity:** Immutable SHA-256 anchoring guarantees cryptographic proof against server-side data tampering.
- **Role-Based Access Control (RBAC):** Strict separation of privileges between administrators, forensic analysts, and field investigators.
- **JWT & Supabase Session Security:** Cryptographically signed tokens with automatic expiry and authenticated route guards.
- **Isolated Evidence Storage:** Evidence binaries stored in UUID-isolated case directories with restricted static access.
- **Comprehensive Audit Trail:** Append-only operational logging capturing IP addresses, user IDs, timestamps, and state transitions.

---

## 14. Installation

### Prerequisites
- **Node.js:** v18.0 or higher
- **Python:** v3.10
- **PostgreSQL:** v15 or higher (or Supabase PostgreSQL instance)
- **Ganache / Truffle:** `npm install -g ganache truffle`
- **COLMAP:** Installed and available on system `PATH` (for 3D photogrammetry)

### 1. Clone the Repository
```bash
git clone https://github.com/Josna-01/Secure-Audit.git
cd "Secure Audit"
```

### 2. Blockchain Setup
```bash
cd blockchain
npm install
npx ganache --server.host 127.0.0.1 --server.port 8545 --chain.chainId 1337
truffle migrate --network development
cd ..
```

### 3. Backend Setup
```bash
cd backend
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
# source venv/bin/activate
pip install -r requirements.txt
cd ..
```

### 4. AI Services Setup
```bash
# BNS Backend:
cd bns-backend && pip install -r requirements.txt && cd ..

# Crime Detection:
cd crime-detection && pip install -r requirements.txt && cd ..

# Photogrammetry Backend:
cd photogrammetry-backend && pip install -r requirements.txt && cd ..

# Audio Backend:
cd audio-backend && pip install -r requirements.txt && cd ..
```

### 5. Frontend Setup
```bash
cd audit-frontend
npm install
cd ..
```

---

## 15. Running the Project

Start all microservices in separate terminal windows:

| Service | Command | URL / Port |
| :--- | :--- | :--- |
| **Ganache Blockchain** | `npx ganache --server.host 127.0.0.1 --server.port 8545 --chain.chainId 1337` | `http://127.0.0.1:8545` |
| **Core Backend Gateway** | `cd backend && python app.py` | `http://127.0.0.1:8000` |
| **BNS Legal Backend** | `cd bns-backend && python -m uvicorn app.main:app --port 8001 --reload` | `http://127.0.0.1:8001` |
| **Photogrammetry 3D** | `cd photogrammetry-backend && python app.py` | `http://127.0.0.1:8002` |
| **Crime Detection** | `cd crime-detection && python main.py` | `http://127.0.0.1:8003` |
| **Audio Forensics** | `cd audio-backend && python app.py` | `http://127.0.0.1:8004` |
| **React Frontend** | `cd audit-frontend && npm run dev` | `http://localhost:5173` |

---

## 16. Environment Variables

Create `.env` files in each service directory based on the following templates:

### `backend/.env`
```ini
DATABASE_URL=postgresql://postgres:password@localhost:5432/secure_audit
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-supabase-service-role-key
USE_LOCAL_STORAGE=True
WEB3_PROVIDER_URI=http://127.0.0.1:8545
CONTRACT_ADDRESS=0xYourDeployedEvidenceRegistryAddress
CONTRACT_ABI_PATH=../blockchain/build/contracts/EvidenceRegistry.json
```

### `bns-backend/.env`
```ini
PORT=8001
DEVICE=cpu
MODEL_PATH=./Model_Data
```

### `photogrammetry-backend/.env`
```ini
PORT=8002
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-supabase-service-role-key
COLMAP_PATH=colmap
```

### `audit-frontend/.env`
```ini
VITE_API_URL=http://127.0.0.1:8000
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-supabase-anon-key
```

---

## 17. Screenshots

| Case Management & Evidence Hub | 3D Crime Scene Reconstruction |
| :---: | :---: |
| *Dashboard showing verified case evidence and blockchain status* | *Interactive 3D point cloud reconstructed from scene video* |
| *(Screenshot Placeholder)* | *(Screenshot Placeholder)* |

| BNS Legal Prediction & XAI | YOLOv8 Weapon Detection |
| :---: | :---: |
| *Ranked BNS sections with highlighted narrative triggers* | *Real-time weapon and firearm bounding boxes* |
| *(Screenshot Placeholder)* | *(Screenshot Placeholder)* |

---

## 18. Future Scope

- **Edge Deployment for Patrol Units:** Lightweight mobile edge inference for on-scene evidence hashing and instant weapon scanning.
- **Zero-Knowledge Proofs (ZKP):** Implement zk-SNARKs for selective evidence disclosure without revealing sensitive case details.
- **Multimodal Video Diarization:** Synchronized facial recognition and voice diarization across multi-camera interrogation rooms.
- **National Crime Records Integration:** Automated interoperability with national criminal databases and CCTNS frameworks.

---

## 19. Contributors

| Name | USN | Module Ownership & Key Responsibilities |
| :--- | :--- | :--- |
| **Ancilla Josna** | `4SO23CS026` | **Project Lead**, BNS Legal Classification Backend (HGAT), Multilingual OCR Extraction & Blockchain Backend |
| **Amisha** | `4SO23CS019` | React Frontend Architecture, Core FastAPI Gateway, 3D Photogrammetry Scene Reconstruction |
| **Apeksha** | `4SO23CS031` | Audio Forensics (WhisperX / Deepfake Detection) & Audio Frontend Module |
| **Alisha** | `4SO23CS017` | Crime & Weapon Detection (YOLOv8 Computer Vision Service) |

---

## 20. License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.
