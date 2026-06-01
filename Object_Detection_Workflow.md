# Secure Audit: Object Detection Architecture & Data Flow

This document outlines the end-to-end technical workflow for the Secure Audit Object Detection feature. It traces the data path from user upload, through backend processing and AI inference, into the database, and back to the frontend rendering engine.

---

## Phase 1: Frontend Capture & Upload
**Environment:** React Frontend  
**Lead File:** `audit-frontend/src/pages/OtherPages.tsx`

When an investigator initiates a scan on a crime scene image via the Detection tab (`Upload New`), the sequence begins natively in the React client.

* **Action:** The `runDetection` asynchronous function intercepts the uploaded file.
* **Mechanism:** It instantiates a `FormData` object to securely package the raw image file. Crucially, it links the `case_id` directly to this form metadata to ensure strict referential integrity.
* **Network Call:** The frontend dispatches a `POST` request (`api.uploadEvidence`) to the FastAPI backend, formally submitting the image into the criminal case record.

---

## Phase 2: Evidence Integrity & Storage
**Environment:** FastAPI Server  
**Lead File:** `backend/app.py`  
**Endpoint:** `POST /evidence/upload`

Upon receiving the `multipart/form-data` payload, the system begins forensic processing.

* **File Streaming:** The server intercepts the `MultipartFile` and streams the payload asynchronously in byte-chunks into the local `uploads/` volume directory.
* **Cryptographic Hashing:** During the stream, Python's `hashlib.sha256()` algorithm continuously ingests the byte chunks to generate a mathematically immutable SHA-256 hash signature. This establishes tamper-evident security.
* **Database Commitment:** The server communicates with the **Supabase (PostgreSQL)** database, executing an `INSERT` command into the `public.evidence` table. The row binds the generated `file_hash`, file metadata, and the local file path. An `evidence_id` is successfully returned to the client.

---

## Phase 3: Roboflow YOLO Inference
**Environment:** FastAPI Server / Python Roboflow SDK  
**Lead File:** `backend/app.py`  
**Endpoint:** `POST /ai/detect`

With the evidence successfully committed, the frontend automatically kicks off the AI workflow by passing the newly obtained `evidence_id` back to the server.

* **Validation:** The server hits Supabase to verify that the `evidence_id` exists and fetches its associated `file_url` path.
* **AI Execution:** The Python engine invokes `model.predict(file_path).json()`. This command connects to the externally isolated **Roboflow Workspace** (utilizing the curated `weapon-detection-using-yolov8` model version 1).
* **Payload Generation:** Roboflow evaluates the image and returns a strict JSON payload mapping identified weapons. Key vectors returned include the object `label`, confidence score, and center-mapped Cartesian coordinates translated into a `[x, y, width, height]` array format.

---

## Phase 4: Database Finalization
**Environment:** Supabase (PostgreSQL)  
**Table:** `public.detections`

Before completing the HTTP response, the backend persists the AI findings to ensure permanent auditing.

* **Data Linking:** The backend prepares a payload containing foreign keys for both the `case_id` and the `evidence_id`, alongside a full URL string pointing to the original image (`image_url`).
* **JSONB Storage:** The raw Roboflow coordinate mappings and labels are packaged into a JSON dictionary string (`predictions: { objects: [...] }`).
* **Execution:** A new row is executed into the `detections` table, securely archiving the exact mathematical output against the original evidence hash.

---

## Phase 5: Dynamic UI Rendering & CSS Annotation
**Environment:** React Frontend  
**Lead File:** `audit-frontend/src/pages/OtherPages.tsx`

FastAPI returns a `200 Success` code containing the full analytical data mapping back to the React client, which had been awaiting the API response block.

* **Image Load:** The frontend parses the `image_url` and leverages a native HTML `<img>` tag to display the unmodified evidence picture in the browser.
* **Dynamic Overlay Algorithm:** Rather than processing a computationally expensive *new* image with hardcoded boxes painted onto it, the system utilizes React's `.map()` rendering loop. 
* **Execution:** It parses the `[x, y, width, height]` vectors directly from the JSON. It then generates transparent HTML `<div>` blocks styled with prominent red borders. By mapping the array properties to absolute CSS positioning logic, it seamlessly overlays the red bounding boxes perfectly over the underlying image, creating the illusion of a single annotated graphic.
