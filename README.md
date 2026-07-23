# Secure Audits - Digital Evidence & Investigation Support System

**Secure Audits** - digital forensics and case management workspace built for law enforcement and investigation audits. The platform provides secure case tracking, OTP-based secure authentication, file integrity verification (SHA-256 hashing on Supabase), object detection on evidence, OCR, and AI-driven Bharatiya Nyaya Sanhita (BNS) section prediction.

---

## 2. Problem Statement

Traditional law enforcement and forensic investigations often rely on fragmented, offline workflows, making it difficult to maintain a reliable chain of custody for digital evidence. Insecure logging allows potential data tampering to go unnoticed, and investigators lack centralized, AI-assisted tools for rapid object detection, OCR analysis, and semantic legal search. Secure Audits addresses these challenges by offering a unified, audit-logged environment that safeguards evidence integrity, aids semantic legal retrieval under the BNS framework, and automates media scanning.

---

## 3. Objectives

* **Secure Case Management:** Centralized case indexing with automatic, sequential case number generation (`SA-YYYY-XXXX`).
* **Digital Evidence Storage:** Secure hosting of forensic evidence files within encrypted Supabase storage buckets.
* **Evidence Integrity Verification:** Re-computing and comparing SHA-256 hashes before AI analysis to detect file modification or tampering.
* **AI-Assisted Analysis:** Deep learning object detection (YOLOv8) to scan evidence photos for weapons and contraband.
* **Audit Trail Maintenance:** Immutable, append-only system logging tracking user activity, logins, and evidence verification.
* **Crime Scene Reconstruction:** Interactive case graphs mapping suspects, victims, locations, and linked evidence items.
* **Investigation Reporting:** Centralized case reports compiling FIR text, parsed data, and legal predictions.

---

## 4. Key Features

### Case Management

* **Create and Manage Cases:** Create audit cases with detailed incident reports, victim/suspect profiles, and incident timestamps.
* **Investigator Assignment:** Assign cases to specific officers with role-based visibility restrictions.
* **Case Tracking:** View current case details, priority levels, and related event timelines.

### Evidence Management

* **Upload Evidence:** Upload photos, documents, and videos directly under a case folder structure.
* **SHA-256 Integrity Verification:** Check if evidence has been altered by comparing its current byte hash against its upload state.
* **Duplicate Detection:** Block redundant files by scanning case evidence hashes before committing storage space.

### OCR Analysis

* **Extract Text from Images and Documents:** Read printed text, numbers, and handwritten scripts on digital evidence documents.
* **Searchable Results:** Store OCR transcripts to enable system-wide text lookup.

### Object Detection

* **Weapon and Object Detection:** Scan images for weapons, firearms, and items using a customized YOLOv8 model.
* **Bounding Box Coordinates:** Return predicted confidence scores and normalized boundary coordinates for visual highlight mapping on the frontend.

### Audio Intelligence

* **Speech-to-Text:** Transcribe voice notes, phone taps, and recorded interrogations.
* **Entity Extraction:** Parse critical names, dates, times, and key phrases from transcriptions.
* **Keyword Analysis:** Flag threat terms or suspicious keywords.

### Photogrammetry & 3D Reconstruction

* **Video-to-3D Crime Scene Reconstruction:** Generate 3D point clouds and meshes from crime scene walk-through video recordings.
* **Interactive Scene Visualization:** Render reconstructed models dynamically using WebGL-based viewers on the frontend.

### Audit Logging

* **Immutable Audit Trail:** Append-only database logs that track logouts, logins, uploads, and AI analysis events.
* **User Activity Tracking:** Monitor IP, user roles, action statuses, and verification history for high-security transparency.

---

## 5. System Architecture

```
         Frontend (React + Vite)
                    │
                    ▼ (HTTP REST API)
         Backend API (FastAPI)
         ┌──────────┴──────────┐
         ▼                     ▼
 Supabase DB & Storage    AI Processing Services
 (Postgres / gotrue)      (Roboflow YOLO, FAISS, Legal-BERT)
                               │
                               ▼
                     Investigation Modules
```

---

## 6. Technology Stack

### Frontend

* React 18
* TypeScript
* Vite 5
* React Flow (Graph Visualizations)

### Backend

* FastAPI
* Python 3.9+
* Uvicorn

### Database & Storage

* Supabase (PostgreSQL & Object Storage)
* PostgREST API (through Python / JS Client SDKs)

### AI & Computer Vision

* OpenCV (Image Processing)
* Roboflow API (YOLOv8 Contraband Detection)
* Legal-BERT / PyTorch (BNS Prediction)
* FAISS (Vector Retrieval Engine)
* Open3D & COLMAP (3D Photogrammetry Pipelines)

---

## 7. Project Structure

```
secure-audit-workspace/
├── audit-frontend/      # React client application and dashboard
├── backend/             # FastAPI API gateway and main backend service
├── bns-backend/         # Machine learning model server for BNS classification
├── audio-backend/       # Dedicated backend folder for Audio Intelligence
├── object-backend/      # Dedicated backend folder for Object Detection
└── README.md            # Repository documentation
```

---

## 8. Database Design

### Users
Stores information on investigators, admins, and active staff.
* `id` (UUID, Primary Key)
* `email` (TEXT, Unique)
* `full_name` (TEXT)
* `role` (TEXT — `Admin` or `Investigator`)
* `department` (TEXT)
* `badge_number` (TEXT)
* `clearance_level` (INT)
* `is_active` (BOOLEAN)
* `can_create_case` (BOOLEAN)
* `last_login` (TIMESTAMP)

### Cases
Stores metadata for registered investigation files.
* `id` (UUID, Primary Key)
* `case_number` (TEXT, Unique)
* `title` (TEXT)
* `offence_type` (TEXT)
* `fir_description` (TEXT)
* `fir_language` (TEXT)
* `complainant_name` (TEXT)
* `complainant_contact` (TEXT)
* `victims` (JSONB)
* `suspects` (JSONB)
* `incident_date` (TEXT)
* `incident_location` (TEXT)
* `created_by` (UUID)

### Evidence
Houses metadata and integrity hashes for evidence files.
* `id` (UUID, Primary Key)
* `case_id` (UUID, Foreign Key)
* `evidence_type` (TEXT)
* `description` (TEXT)
* `file_url` (TEXT)
* `file_hash` (TEXT — SHA-256)
* `file_name` (TEXT)
* `file_size` (INT)
* `status` (TEXT — `Verified` or `Tampered`)
* `verified_at` (TIMESTAMP)
* `verified_by` (UUID)

### Audit Logs
Immutable history recording all system-critical operations.
* `id` (BIGINT, Primary Key)
* `user_id` (UUID / TEXT)
* `action` (TEXT)
* `case_id` (UUID)
* `file_hash` (TEXT)
* `metadata` (JSONB)
* `created_at` (TIMESTAMP)

### OCR Results
Stores extracted text records.
* `id` (UUID, Primary Key)
* `evidence_id` (UUID, Foreign Key)
* `extracted_text` (TEXT)
* `language` (TEXT)
* `created_at` (TIMESTAMP)

### Object Detection Results
Houses class tags and localization coordinates.
* `id` (UUID, Primary Key)
* `evidence_id` (UUID, Foreign Key)
* `predictions` (JSONB — Bounding boxes, labels, and confidences)
* `image_url` (TEXT)

### Photogrammetry Models
Maintains references to reconstructed 3D environments.
* `id` (UUID, Primary Key)
* `case_id` (UUID, Foreign Key)
* `model_url` (TEXT)
* `point_cloud_url` (TEXT)
* `status` (TEXT — `Processing`, `Completed`, `Failed`)

---

## 9. Workflow

### Case Creation
```
 Investigator
      │
      ▼
 Fill Case Wizard (FIR details, Suspects, Victims)
      │
      ▼
 Backend API (Assigns case number SA-YYYY-XXXX & created_by UUID)
      │
      ▼
 Postgres Database (Creates Case Record)
```

### Evidence Upload
```
 Evidence File
      │
      ▼
 Compute SHA-256 Hash on Client/Server
      │
      ▼
 Check for duplicates in DB
      │
      ▼
 Upload to Supabase Storage Bucket
      │
      ▼
 Insert DB Evidence Record (marked as "Verified")
```

### Analysis
```
 Evidence Image/Doc
      │
      ▼
 Verify Current SHA-256 matches Stored Hash
      │
      ├── (Valid) ──► Run YOLOv8 Scan / OCR ──► Save JSON Results in DB
      │
      └── (Mismatch) ──► Block Analysis ──► Mark as "Tampered" ──► Trigger Audit Alert
```

---

## 10. Installation Guide

### Backend Setup
1. Navigate to the backend folder:
   ```bash
   cd backend
   ```
2. Set up virtual environment and install packages:
   ```bash
   python -m venv venv
   .\venv\Scripts\activate  # Windows
   # source venv/bin/activate  # macOS/Linux
   pip install -r requirements.txt
   ```
3. Run the FastAPI development server:
   ```bash
   python app.py
   ```

### ML BNS Backend Setup
1. Navigate to the model backend folder:
   ```bash
   cd bns-backend
   ```
2. Activate environment, install dependencies, and run:
   ```bash
   python -m venv venv
   .\venv\Scripts\activate  # Windows
   pip install -r requirements.txt
   uvicorn app.main:app --reload --port 8001
   ```

### Audio Backend Setup
1. Navigate to the audio-backend folder:
   ```bash
   cd audio-backend
   ```
2. Activate environment, install dependencies, and run:
   ```bash
   python -m venv venv
   .\venv\Scripts\activate  # Windows
   pip install -r requirements.txt
   python app.py
   ```

### Object Backend Setup
1. Navigate to the object-backend folder:
   ```bash
   cd object-backend
   ```
2. Activate environment, install dependencies, and run:
   ```bash
   python -m venv venv
   .\venv\Scripts\activate  # Windows
   pip install -r requirements.txt
   python app.py
   ```

### Frontend Setup
1. Navigate to the frontend folder:
   ```bash
   cd audit-frontend
   ```
2. Install package dependencies and start:
   ```bash
   npm install
   npm run dev
   ```

### Environment Variables
Configure `/backend/.env` (using the template in [.env.example](file:///c:/Users/amish/Desktop/Secure%20Audit/backend/.env.example)):
```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-supabase-service-role-key
ROBOFLOW_API_KEY=your-roboflow-yolo-key
JWT_SECRET=your-jwt-auth-secret
EMAIL_USER=your-smtp-email
EMAIL_PASSWORD=your-smtp-app-password
```

Configure `/audit-frontend/.env` (using the template in [.env.example](file:///c:/Users/amish/Desktop/Secure%20Audit/audit-frontend/.env.example)):
```env
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-supabase-anon-key
VITE_API_BASE_URL=http://localhost:8000
```

---

## 11. Future Enhancements

* **AI Storyboard Generation:** Automated case timeline generation compiling evidence tags, locations, and incident sequences.
* **Evidence Relationship Graph:** Interactive 2D/3D visualizations mapping link associations among suspects, call records, locations, and cases.
* **Advanced Audio Intelligence:** Real-time speaker diarization and audio analysis during suspect interrogation.
* **Investigator Assistant (RAG):** Local generative LLM agent to query case notes, evidence details, and legal regulations.
* **Real-time Collaboration:** WebRTC or WebSocket-based collaborative workspaces for joint audits.
* **Government Deployment Infrastructure:** Docker containerization templates for local sovereign cloud deployments.

---

## 12. Team Members

Ancilla - 4SO23CS026
Amisha - 4SO23CS019
Apeksha - 4SO23CS031
Alisha - 4SO23CS017
