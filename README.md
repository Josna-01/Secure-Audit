# Secure Audits — Digital Evidence & Investigation Support System

Welcome to **Secure Audits V1**, a dark-themed digital forensics and case management workspace built for law enforcement and investigation audits. The platform provides secure case tracking, OTP-based secure authentication, file integrity verification (SHA-256 hashing on Supabase), object detection on evidence, OCR, and AI-driven Bharatiya Nyaya Sanhita (BNS) section prediction.

---

## 📂 Repository Structure

The project is divided into three main components:

1. **[audit-frontend/](file:///c:/Users/amish/Desktop/Secure%20Audit/audit-frontend)**
   * **Tech Stack:** React 18 + TypeScript + Vite 5 + Vanilla CSS
   * **Role:** Dark-themed investigator dashboard, audit logging views, interactive case creation wizards, and live graphs.
2. **[backend/](file:///c:/Users/amish/Desktop/Secure%20Audit/backend)**
   * **Tech Stack:** Python 3.9+ + FastAPI + Supabase Python client + Uvicorn
   * **Role:** Primary system REST API handling authentication (password + OTP email verification), user lifecycles, and audit logging.
3. **[bns-backend/](file:///c:/Users/amish/Desktop/Secure%20Audit/bns-backend)**
   * **Tech Stack:** Python + FastAPI + PyTorch + FAISS
   * **Role:** Machine Learning server executing semantic legal retrieval and graph attention network inference (Legal-BERT) for BNS sections matching.

---

## ⚙️ Installation & Requirements

### 1. Main API Backend (`backend/`)
Requires Python 3.9+ installed.

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # On Windows:
   .\venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```
3. Install the required Python packages:
   ```bash
   pip install -r requirements.txt
   ```
4. Create a `.env` file based on `.env.example` (or copy credentials provided by the admin) and configure:
   * `SUPABASE_URL`
   * `SUPABASE_KEY`
   * `SUPABASE_SERVICE_ROLE_KEY`
   * `JWT_SECRET`
   * `EMAIL_USER`
   * `EMAIL_PASSWORD` (App password for SMTP)
5. Start the backend server:
   ```bash
   python app.py
   ```

---

### 2. Frontend Application (`audit-frontend/`)
Requires Node.js installed.

1. Navigate to the frontend directory:
   ```bash
   cd audit-frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Create a `.env` file containing:
   ```env
   VITE_SUPABASE_URL=https://your-project.supabase.co
   VITE_SUPABASE_ANON_KEY=your-anon-key
   VITE_API_BASE_URL=http://localhost:8000
   ```
4. Start the Vite local development server:
   ```bash
   npm run dev
   ```

---

### 3. BNS Model Backend (`bns-backend/`)
1. Navigate to the folder:
   ```bash
   cd bns-backend
   ```
2. Install requirements and model dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Start the model server (runs on Port `8001` or as configured):
   ```bash
   uvicorn app.main:app --reload --port 8001
   ```

---

## 🤝 Collaboration & Branching Git Workflow

Since you are collaborating on this project, **do not commit directly to the `main` branch**. Working directly on `main` will result in merge conflicts and override each other's work. Instead, follow this branch-based collaboration workflow:

### 1. Sync your local `main` branch
Always get the latest changes from GitHub before starting any new feature:
```bash
git checkout main
git pull origin main
```

### 2. Create a separate feature branch
Create a new branch for the specific task you are working on. Use a descriptive prefix like `feature/` or `bugfix/`:
```bash
# Example: Creating a branch to add profile avatars
git checkout -b feature/avatar-upload
```

### 3. Make changes and commit locally
Make your code modifications. Once tested and ready, commit them to your branch:
```bash
git status
git add .
git commit -m "feat: implement avatar upload and profile photo display"
```

### 4. Push your branch to GitHub
Push your local branch to the remote repository:
```bash
git push origin feature/avatar-upload
```

### 5. Open a Pull Request (PR)
1. Go to the GitHub repository online.
2. You will see a prompt saying **"Compare & pull request"** for your branch.
3. Click it, describe what you did, and submit the Pull Request.
4. Your partner can review the code changes, leave feedback, and safely merge the branch into `main` directly on GitHub.
