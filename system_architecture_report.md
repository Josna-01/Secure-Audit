# Secure Audit System Documentation

## 1. USE CASE DIAGRAM (TEXT FORMAT)

**Actors:**
*   **Investigating Officer (User):** Primary user interacting with the system to manage cases and evidence.
*   **External AI Services:** Automated actors (Roboflow API, BNS Classification API) that process data when triggered.

**Core Use Cases & Relationships:**

*   **Manage Case Metadata** (Create, Retrieve, Update)
*   **Upload Digital Evidence**
    *   *«includes»* **Generate SHA-256 Hash**
    *   *«includes»* **Write to Audit Log**
*   **Verify Evidence Integrity**
    *   *«includes»* **Recompute Hash from Disk**
    *   *«includes»* **Write to Audit Log**
*   **Run AI Object Detection**
    *   *«includes»* **Verify Evidence Integrity** (Pre-flight integrity block)
    *   *«extends»* **Block AI Execution** (Triggered if Integrity Verification fails)
*   **View POLE Relationship Graph**
*   **Use Personal Investigative Notes**
    *   *«includes»* **Export Canvas Drawing** (Excalidraw Base64 export)
*   **Classify BNS Sections**
*   **View Immutable Audit Logs**

---

## 2. SYSTEM ARCHITECTURE

The Secure Audit platform operates on a decoupled, three-tier architecture augmented by external AI service integrations.

**1. Frontend (React 18 & Vite)**
Acts as the presentation layer. It manages application state, handles client-side routing, and provides specialized interactive components such as `@xyflow/react` for the POLE graph and `@excalidraw` for freehand investigative notes. It communicates securely with the backend via Axios HTTP requests.

**2. Backend (FastAPI - Python)**
Acts as the central integration and security broker. It handles file system I/O (storing uploaded evidence in the local `uploads/` directory), cryptographic operations (calculating SHA-256 hashes in memory chunks), and orchestrates requests to the database and external APIs. It strictly enforces forensic rules, such as preventing duplicate file uploads and blocking tampered files from reaching the AI layer.

**3. Database (Supabase / PostgreSQL)**
The persistent data tier. It maintains normalized relational tables (`cases`, `evidence`, `detections`, `personal_notes`) and an append-only `audit_logs` table. The backend uses the `supabase-py` client to interface with this database, ensuring metadata is strongly coupled to the binary files on the backend disk.

**4. External Services**
*   **Roboflow YOLO Integration:** A computer vision API. The backend securely transmits validated forensic images to Roboflow to detect objects (e.g., weapons), receives bounding box coordinates, normalizes them to percentages, and returns them to the frontend.
*   **BNS API:** An external Natural Language Processing integration intended to analyze unstructured FIR text and return relevant legal sections.

---

## 3. DATA FLOW (STEP-BY-STEP)

**A. Evidence Flow:**
1.  User selects an image file in the frontend UI.
2.  Frontend transmits the file via `multipart/form-data` to the backend `/evidence/upload` endpoint.
3.  Backend streams the file to the local `uploads/` directory, computing the SHA-256 hash dynamically during the write process.
4.  Backend queries the Supabase database to ensure the hash does not already exist (duplicate prevention).
5.  Backend inserts the evidence metadata and `stored_hash` into the `evidence` table.
6.  Backend appends an "Evidence Upload" event to the `audit_logs` table.

**B. Tamper Detection Flow:**
1.  User clicks "Verify Hash" on an existing piece of evidence.
2.  Backend `/evidence/{id}/verify` endpoint locates the physical file on the disk.
3.  Backend recomputes the SHA-256 hash directly from the physical file.
4.  Backend compares the newly computed hash against the `stored_hash` in the database.
5.  If mismatched, the backend updates the evidence status to "Tampered" and records a "Tamper Detected" audit log.

**C. Object Detection Flow:**
1.  User selects an evidence file and triggers Object Detection.
2.  Backend intercepts the request and performs an automatic Tamper Detection check (as defined in Flow B).
3.  If tampered, the backend immediately blocks execution, returning a 403 Forbidden error.
4.  If verified, the backend sends the image to the Roboflow YOLO API.
5.  Backend receives raw pixel coordinates, converts them to responsive percentages, saves them to the `detections` table, and returns the data to the frontend for overlay rendering.

**D. POLE Graph Flow:**
1.  User navigates to the POLE Graph page and selects a case ID.
2.  Backend `/cases/{id}/graph` endpoint queries the case metadata.
3.  Backend dynamically constructs a central Case node, Event node, and Location node.
4.  Backend iterates over the `victims` and `suspects` JSON arrays, appending Person nodes.
5.  Backend queries the `evidence` table, appending Object nodes for any files linked to the case.
6.  Backend calculates layout coordinates (`x, y`) for each node, generates connecting edges, and returns the complete schema to the frontend's React Flow engine.

**E. BNS Classification Flow:**
1.  User inputs or auto-fills the FIR text in the BNS interface.
2.  Frontend sends the textual data to the external API.
3.  External API analyzes the narrative and returns predicted legal sections.
4.  Frontend displays the predictions; upon user acceptance, the frontend links the classification to the case and triggers an audit log update.

---

## 4. SEQUENCE DIAGRAM (TEXT FORMAT)

### Scenario 1: Evidence Upload & Verification
`User → Frontend:` Select image and click Upload
`Frontend → Backend:` POST /evidence/upload (multipart form)
`Backend → File System:` Write file to disk & calculate SHA-256
`Backend → DB:` Query existing hash (check for duplicates)
`Backend → DB:` Insert new record into `evidence` table
`Backend → DB:` Insert "Evidence Upload" event into `audit_logs`
`Backend → Frontend:` Return Success (Evidence ID)
`User → Frontend:` Click "Verify Hash"
`Frontend → Backend:` POST /evidence/{id}/verify
`Backend → File System:` Read file from disk & recompute SHA-256
`Backend → DB:` Retrieve `stored_hash` and compare
`Backend → DB:` Insert "Hash Verified" event into `audit_logs`
`Backend → Frontend:` Return "Verified" status

### Scenario 2: Object Detection with Tamper Blocking
`User → Frontend:` Click "Run Detection" on an image
`Frontend → Backend:` POST /ai/detect
`Backend → File System:` Read file and calculate hash
`Backend → DB:` Retrieve `stored_hash`
`Backend → Backend:` Compare hashes. **[Mismatch Detected]**
`Backend → DB:` Update evidence status to "Tampered"
`Backend → DB:` Insert "Tamper Detected" event into `audit_logs`
`Backend → Frontend:` Return HTTP 403 Forbidden (Integrity Compromised)
`Frontend → User:` Display "Detection Failed" error message

### Scenario 3: POLE Graph Generation
`User → Frontend:` Open POLE Graph and search for a Case
`Frontend → Backend:` GET /cases/{id}/graph
`Backend → DB:` Select case metadata (Victims, Suspects, Location)
`Backend → DB:` Select evidence linked to case_id
`Backend → Backend:` Aggregate nodes and assign `{x, y}` positions
`Backend → Frontend:` Return complete JSON graph payload
`Frontend → User:` React Flow renders interactive relationship web
