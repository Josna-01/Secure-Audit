# AI-Powered Digital Forensic Investigation System
## YOLOv8 Suspicious Object Detection Module (Major Project)

### 📌 Overview
This module provides automated **real-time suspicious object detection** (weapons, knives, scissors, guns, abandoned items) for images and video evidence using **YOLOv8** and **OpenCV**. All detected objects are annotated with **STRICT RED Bounding Boxes** (`BGR: 0, 0, 255`) and classified by risk levels. Each piece of uploaded evidence is verified using **SHA-256 Cryptographic Hashing** to ensure forensic chain of custody integrity (SRS Section 3.2 compliance).

---

### 🚀 Key Features
1. **Add Photo 📷**: Upload any image file (`.jpg`, `.png`, `.webp`) for object detection.
2. **Add Video 🎥**: Upload any video file (`.mp4`, `.avi`, `.mov`) for frame-by-frame red box tracking while maintaining original FPS and resolution.
3. **1-Click Quick Dummy Data ⚡**: Test immediately with pre-loaded dummy evidence files (Knife Evidence, Suspicious Bag/Phone, CCTV Stream).
4. **Strict RED Bounding Boxes**: Bounding boxes drawn in pure red with red background banners and crisp white text.
5. **SHA-256 Integrity Hash**: Calculates digital evidence hash immediately upon upload.
6. **Detailed Object Breakdown**: Shows object counts, risk category (High/Weapon, Medium/Evidence, Low/General), confidence scores, and precise bounding box coordinates.
7. **Downloadable Outputs**: Download annotated images or videos directly from the browser.

---

### 🛠️ Quick Setup & Execution Instructions

#### 1. Requirements
- Python 3.9+ installed
- Virtual environment (`venv`) or standard Python environment
- Dependencies listed in `requirements.txt`:
  - `ultralytics`
  - `fastapi`
  - `uvicorn`
  - `opencv-python`
  - `python-multipart`
  - `numpy`

#### 2. Install Dependencies
Open terminal / PowerShell in project root and run:
```bash
pip install -r requirements.txt
```

#### 3. Start the Server
Run the main FastAPI server:
```bash
python main.py
```
*The server will start at:* `http://127.0.0.1:8003` *(Originally configured for port 8001 / 8000; updated to 8003 to prevent port collision with BNS service on 8001)*.

#### 4. Open the Web Visualizer
Open your browser and navigate to:
👉 **`http://127.0.0.1:8003`**

- Click **"📷 Add Photo"** or **"🎥 Add Video"**.
- Or click **"⚡ Dummy Photo (Knife)"** / **"⚡ Dummy Video"** for instant 1-click demonstration!
- View detected objects highlighted in **RED BOXES** on screen!

---

### 🧪 Automated System Verification
To verify all API endpoints and model performance automatically, run:
```bash
python test_script.py
```

---

### 📁 Ready-Made Project Structure
```
crime-detection/
├── main.py                 # FastAPI backend server with RED bounding box renderer
├── static/
│   └── index.html          # Interactive Web Visualizer with Add Photo & Add Video
├── sample_data/            # Bundled dummy sample images & video
│   ├── sample_knife_evidence.jpg
│   ├── sample_suspicious_scene.jpg
│   └── sample_surveillance_stream.mp4
├── model/
│   └── yolov8n.pt          # YOLOv8 object detection model weights
├── create_sample_data.py   # Script to generate sample dummy evidence
├── test_script.py          # End-to-end automated testing script
├── create_project_zip.py   # Script to package project into a ready-made ZIP archive
├── requirements.txt        # Python package dependencies
├── HOW_TO_RUN.md           # Step-by-step setup guide
└── README.md               # Project documentation & SRS report summary
```

---

### 📦 Ready-Made ZIP Archive
To recreate or update the ready-made zip folder `crime_object_detection_yolov8.zip`, run:
```bash
python create_project_zip.py
```
This produces `crime_object_detection_yolov8.zip` in the root workspace ready for submission or distribution.
