# 🚀 How to Run the Secure Audit Platform

Because your platform uses a microservice architecture with heavy AI models, it requires **three separate servers** to run simultaneously. You will need to open **three separate terminals** to start them all.

---

## 1️⃣ Start the Main Backend (FastAPI)
This server connects to Supabase, handles case management, saves evidence, logs audits, and securely routes requests to the AI server.

1. Open **Terminal 1**.
2. Navigate to your backend folder:
   ```powershell
   cd "c:\Users\amish\Desktop\Secure Audit\backend"
   ```
3. Activate your virtual environment (if you use one) and run the server:
   ```powershell
   python app.py
   ```
*(This server will start on **http://localhost:8000**)*

---

## 2️⃣ Start the BNS AI Backend (Teammate's Server)
This server runs the massive machine learning models (PyTorch, Faiss) required to classify FIR texts into Indian Penal Codes.

1. Open **Terminal 2**.
2. Navigate to the `bns-backend` folder:
   ```powershell
   cd "c:\Users\amish\Desktop\Secure Audit\bns-backend"
   ```
3. **Activate the Python 3.10 environment** (this step is extremely important because her ML models will crash on other Python versions!):
   ```powershell
   .\venv310\Scripts\activate
   ```
4. Set the port to 8001 and start the Uvicorn server:
   ```powershell
   $env:PORT="8001"
   uvicorn app.main:app --port 8001
   ```
*(This server will start on **http://localhost:8001**)*

---

## 3️⃣ Start the React Frontend
This is the user interface where investigators will interact with the platform.

1. Open **Terminal 3**.
2. Navigate to your frontend folder:
   ```powershell
   cd "c:\Users\amish\Desktop\Secure Audit\audit-frontend"
   ```
3. Start the Vite development server:
   ```powershell
   npm run dev
   ```
*(This server will start on **http://localhost:5173**)*

---

> **What happens if I forget to start the BNS server?**  
> Your main app will still work perfectly (you can upload evidence, view cases, etc.). However, if you click the "Run BNS Classification" button, it will fail and show a connection error because the AI brain is turned off.

> **Quick Testing Check**  
> Always check your terminals if something isn't working. If one of the terminals has a red error or says "Shutting down", you just need to restart that specific terminal command.
