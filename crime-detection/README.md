# AI-Powered Digital Forensic Investigation System
## Major Project: YOLOv8 Suspicious & Crime Object Detection Module

### 📄 Abstract & Scope
This project fulfills the **Object Detection Subsystem** specified in Chapter 3 & 4 of the Digital Forensic Investigation System Software Requirements Specification (SRS). The primary objective is to automate the detection and identification of suspicious objects (such as weapons, knives, guns, scissors, abandoned items, backpacks, bottles, and cell phones) in uploaded image and video evidence.

Using **YOLOv8** deep learning architecture integrated with **OpenCV** and **FastAPI**, the system performs real-time frame-by-frame object detection. All suspicious objects are highlighted using **STRICT RED RECTANGULAR BOUNDING BOXES** (`BGR: 0, 0, 255`) with filled red background banners and clear risk badges. In accordance with SRS Section 3.2, every uploaded evidence file is processed through a **SHA-256 Cryptographic Hashing** engine to guarantee digital chain-of-custody integrity.

---

### ✨ Core Deliverables & Features

1. **Add Photo 📷**:
   - Allows users to upload image files (`.jpg`, `.png`, `.webp`) or select bundled dummy evidence photos.
   - Highlights detected objects with bold red bounding boxes, label names, risk categories, and confidence percentages.

2. **Add Video 🎥**:
   - Enables video evidence uploads (`.mp4`, `.avi`, `.mov`) or sample video streams.
   - Performs frame-by-frame inference while maintaining original video resolution, aspect ratio, and frame rate (FPS).

3. **1-Click Quick Dummy Data ⚡**:
   - Pre-loaded dummy test files for instant evaluation without requiring external files.

4. **Forensic Evidence SHA-256 Hashing**:
   - Generates unique cryptographic hash upon upload for verification and tamper detection.

5. **Downloadable Annotated Media**:
   - Provides direct download links for processed output images and videos.

6. **Structured JSON API & Table Breakdown**:
   - Exposes RESTful JSON endpoints (`/detect/image`, `/detect/video`, `/health`) and renders a live UI table detailing detection IDs, risk levels, bounding box pixel coordinates `[x1, y1, x2, y2]`, and confidence metrics.

---

### 💻 System Requirements & Architecture

#### Hardware Requirements (SRS Section 3.5.1)
- **RAM**: Minimum 4 GB (8 GB recommended)
- **CPU**: Dual-core processor minimum (Quad-core recommended)
- **GPU**: Optional CUDA-enabled NVIDIA GPU for reduced inference latency

#### Software Requirements (SRS Section 3.5.2)
- **Language**: Python 3.9+
- **Deep Learning Framework**: `ultralytics` (YOLOv8)
- **Computer Vision**: `opencv-python`
- **Backend Framework**: `FastAPI` + `Uvicorn`
- **Frontend Interface**: HTML5, Vanilla JavaScript, Tailwind CSS design system

---

### 🚀 How to Run the Application

#### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

#### Step 2: Launch the FastAPI Backend & Visualizer
```bash
python main.py
```

#### Step 3: Access Web Visualizer
Open your browser and navigate to:
```
http://127.0.0.1:8000
```

#### Step 4: Run Automated Verification Tests
```bash
python test_script.py
```

#### Step 5: Generate Ready-Made ZIP Folder
```bash
python create_project_zip.py
```

---

### 📦 Zip Folder Location
The ready-made project zip folder has been compiled and saved at:
- `crime_object_detection_yolov8.zip` (in parent workspace root and project folder)
