# Secure Audits — Frontend

React + TypeScript + Vite frontend for the Digital Evidence and Investigation Support System.

## Tech Stack

- **Framework:** React 18 + TypeScript
- **Build Tool:** Vite 5
- **Routing:** React Router v6
- **Backend Integration:** Axios (FastAPI) + Supabase JS client
- **Styling:** CSS Variables (no Tailwind — pure CSS-in-JS inline styles)

## Setup

### 1. Install dependencies
```bash
npm install
```

### 2. Configure environment
```bash
cp .env.example .env
```
Edit `.env` with your Supabase URL/key and FastAPI backend URL:
```
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key
VITE_API_BASE_URL=http://localhost:8000
```

### 3. Start dev server
```bash
npm run dev
```
Runs on http://localhost:5173 — API calls proxied to http://localhost:8000

### 4. Build for production
```bash
npm run build
```

## Project Structure

```
frontend/
├── src/
│   ├── pages/
│   │   ├── AuthPage.tsx         Login · OTP · Register · Forgot · Pending
│   │   ├── Dashboard.tsx        Main dashboard with stats, cases, audit feed
│   │   ├── Cases.tsx            Case list with search/filter/pagination
│   │   ├── CreateCase.tsx       4-step wizard: Basics → People → FIR → Review
│   │   ├── CaseDetail.tsx       Case tabs: Overview · Evidence · Detection · BNS · Storyboard
│   │   └── OtherPages.tsx       Evidence · Detection · BNS · OCR · Audit · Profile · Settings · Personal
│   ├── components/
│   │   ├── UI.tsx               Btn · Card · Badge · Input · Tabs · StepWizard · etc.
│   │   ├── Layout.tsx           Sidebar · Topbar · AppShell
│   │   └── NotificationPanel.tsx Rich notification panel with actionable items
│   ├── context/
│   │   ├── AuthContext.tsx      JWT auth state, login/logout
│   │   └── ThemeContext.tsx     Dark/Light theme toggle
│   ├── services/
│   │   ├── api.ts               All FastAPI endpoint calls (Axios)
│   │   └── supabase.ts          Supabase client
│   ├── types/
│   │   └── index.ts             All TypeScript types/interfaces
│   ├── styles/
│   │   └── globals.css          CSS variables, dark/light theme, scrollbar
│   ├── App.tsx                  Router + auth guards
│   └── main.tsx                 Entry point
├── .env.example
├── package.json
├── tsconfig.json
└── vite.config.ts
```

## API Integration

All backend calls go through `src/services/api.ts`. The `ApiService` class:
- Attaches JWT from `localStorage` on every request
- Redirects to `/login` on 401
- Proxies `/api/*` to `VITE_API_BASE_URL` in dev

## Authentication Flow

1. User enters email + password → POST `/auth/send-otp`
2. Backend sends OTP to email
3. User enters OTP → POST `/auth/verify-otp`
4. Backend returns JWT token + user object
5. Token stored in `localStorage` as `sa_token`
6. All subsequent requests attach `Authorization: Bearer <token>`

## FastAPI Expected Endpoints

See `src/services/api.ts` for the full list. Key endpoints:
- `POST /auth/send-otp` · `POST /auth/verify-otp` · `GET /auth/me`
- `GET /cases` · `POST /cases` · `GET /cases/:id`
- `POST /evidence/upload` · `POST /evidence/:id/verify`
- `POST /ai/detect` · `POST /ai/bns/classify` · `POST /ai/ocr`
- `GET /audit` · `GET /notifications`

## Supabase Usage

Supabase client is initialized in `src/services/supabase.ts`.
Currently used for file storage (evidence uploads) and real-time notifications.
The `api.ts` handles all CRUD via FastAPI — Supabase is a secondary integration.
