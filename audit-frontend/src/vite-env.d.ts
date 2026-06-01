/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_SUPABASE_URL: string
  readonly VITE_SUPABASE_ANON_KEY: string
  readonly VITE_API_BASE_URL: string
  readonly VITE_YOLO_MODEL_PATH?: string
  readonly VITE_FAISS_PATH?: string
  readonly VITE_LEGALBERT_PATH?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
