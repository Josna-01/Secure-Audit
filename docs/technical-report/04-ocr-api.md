# Chapter 4 — OCR API Documentation

All endpoints are served by the main FastAPI application (`backend/app.py`, default `http://<host>:8000`).

## 4.0 Common conventions

| Aspect | Rule | Source |
|---|---|---|
| Authentication | `Authorization: Bearer <JWT>`. HS256, signed with `JWT_SECRET`, 24 h expiry, claims `sub`, `email`, `role`, `name`. | `create_jwt`, `decode_jwt`, `get_current_user_info` |
| Auth errors | 401 "Missing or invalid authorization token." / "Token expired…" / "Invalid token."; 403 if the user is deactivated (`is_active=false` in Supabase `users`) | `get_current_user_info` |
| Authorization | `check_case_access(case_id, user)`: Admin sees all cases. Investigator sees cases where `created_by` equals the user or is NULL; otherwise 403. | `check_case_access` |
| Content type | `application/json` | FastAPI / Pydantic |
| Envelope | `{"success": true, "data": …}`. Errors are FastAPI `{"detail": "…"}`. | — |

The OCR endpoints do **not** check the `run_ai_analysis` permission from `ROLE_PERMISSIONS`; any authenticated user with case access may run OCR.

## 4.1 `POST /ai/ocr/{evidence_id}`

The primary endpoint, used by the frontend (`api.ts::runOCR`). Handler: `run_ai_ocr_by_id` → `run_stored_evidence_ocr`.

**Path parameter**
| Name | Type | Validation |
|---|---|---|
| `evidence_id` | UUID string | must parse as UUID → otherwise 400 "Invalid evidence ID format" |

**Request body** (`OCRRequest`, optional; all fields optional)
| Field | Type | Default | Meaning |
|---|---|---|---|
| `language` | string | `"auto"` | `auto`, one code (`en/eng/english`, `hi/hin`, `kn/kan/ka`, `te/tel`, `ta/tam`, `ml/mal`), or a combination (`eng+hin`, `en,kn`) |
| `force` | bool | `false` | bypass the cache and re-extract |
| `translate` | bool | `false` | also return a translation |
| `target_language` | string | `"en"` | translation target: `en`, `hi`, `kn`, `te`, `ta`, `ml` (or aliases) |
| `evidence_id` | string | — | ignored here (the path parameter is used) |

**Example**
```http
POST /ai/ocr/2b5a9776-76da-4fe6-aa5f-030566aafa2b HTTP/1.1
Authorization: Bearer eyJhbGciOiJIUzI1NiIs…
Content-Type: application/json

{"language": "auto", "translate": true, "target_language": "en"}
```

**Processing** (Chapter 2, Section 2.3): authentication → evidence lookup → case access → language resolution → per-evidence lock → cache check → source retrieval → `extract_document` → `store_ocr_pages` → audit log → optional translation → response.

**Database calls**
- `SELECT` on `evidence` (by id);
- `SELECT` on `cases.created_by` (Investigator access check);
- `SELECT` on `ocr_results` (cache);
- on extraction, a transaction of advisory lock + `DELETE`/`INSERT ocr_results`, then `INSERT audit_logs`;
- on translation, `UPDATE ocr_results.ocr_metadata`.

**Storage interaction:** a `GET` of the Supabase public object URL (streamed, size-capped), or a local file read under `backend/uploads`.

**Success response (200):** see Chapter 2, Section 2.13 for the full structure and field semantics. With `translate=true`, the response adds:
```json
"translated_text": "The first information report\n…",
"translation": {"status": "success", "target_language": "en", "target_language_name": "English",
                "source_languages": ["hi"], "providers": ["mymemory"], "error": null,
                "message": null, "cached": false, "untranslated_passages": 0, "processing_time_ms": "…"},
"pages": [{"…": "…", "translated_text": "…"}]
```

**Error responses**
| HTTP | `detail` (examples) | Cause |
|---|---|---|
| 400 | "Invalid evidence ID format" | bad UUID |
| 400 | "Unsupported OCR language 'french'. Supported languages: en, hi, kn, ml, ta, te, or 'auto'." | `OCRLanguageError` |
| 400 | "Evidence has no file URL" / "Invalid local evidence path" | missing URL / path traversal |
| 401 / 403 | see 4.0 | auth / case access |
| 404 | "Evidence not found" / "Uploaded evidence file was not found" | no row / file missing |
| 413 | "The file exceeds the OCR size limit of 50 MB" / "The PDF has 62 pages; the OCR limit is 50 pages" | `OCRLimitError`, streamed download limit |
| 415 | "Unsupported file type for OCR. Upload an image (PNG, JPEG, WEBP, TIFF, BMP, GIF) or a PDF." | `OCRUnsupportedFileError` |
| 422 | "The evidence file is empty" / "The PDF file is corrupted or incomplete and cannot be opened" / "The PDF is password-protected; upload an unlocked copy" | `OCRInvalidFileError` |
| 500 | "OCR processing failed on every page" / "Failed to save OCR results" / "OCR processing failed unexpectedly" | `OCRProcessingError`, DB failure, unexpected exception |
| 502 | "Unable to retrieve the uploaded evidence file" | storage unreachable |
| 503 | "No OCR model could be loaded. Check the server's PaddleOCR installation." | `OCREngineUnavailableError` |

Translation problems never produce an HTTP error. They appear in `translation.status/error` and are appended to `warnings` as "Translation: …".

**Frontend usage**
- `CaseDetail.tsx` (OCR Analysis tab, "Run OCR Processing" and the viewer's translate action);
- `OtherPages.tsx::OCRPage` (after upload, and the translate action);
- both call through `api.ts::runOCR(evidenceId, language, options)` with a 300 000 ms timeout.

## 4.2 `POST /ai/ocr`

Body-addressed variant, kept for backward compatibility. Handler: `run_ai_ocr_body` → `run_stored_evidence_ocr`.

| Field | Required | Notes |
|---|---|---|
| `evidence_id` | **yes** | missing → 400 "Missing evidence ID" |
| `language`, `force`, `translate`, `target_language` | no | as in 4.1 |

Responses and errors are identical to 4.1. There is no frontend usage in the current code.

## 4.3 `GET /ocr/search?q=<keyword>`

Keyword search across stored OCR text. Handler: `search_ocr`. Frontend: `OtherPages.tsx::OCRPage` "Search Scanned Evidence" tab via `api.ts::searchOCR`.

| Parameter | Validation |
|---|---|
| `q` (query string) | trimmed; empty → `{"success": true, "data": []}`; longer than 200 characters → 400 |

**Database call:** `ocr_results ⋈ evidence ⟕ cases` with `extracted_text ILIKE '%q%' ESCAPE '\'`, newest first. `%`, `_` and `\` in `q` are escaped.

**Response (200)**
```json
{"success": true, "data": [{
  "id": "<evidence uuid>", "file_name": "fir1.jpg", "file_type": "Image",
  "case_id": "<uuid>", "case_title": "OCR Testing – FIR Document", "uploaded_by_name": "…",
  "ocr_matches": [{"page_number": 1, "snippet": "…300 characters around the first match…", "confidence": 0.9599}]
}]}
```

**Authorization behaviour:** `check_case_access` runs for each matching row's case. For an Investigator, one match inside an inaccessible case raises 403 for the **whole** search instead of filtering that result out. This is a functional limitation, and it reveals that matches exist in cases the user cannot access (Chapter 9).

## 4.4 Related endpoint used by the OCR page — `POST /evidence/upload`

Multipart form: `case_id`, `evidence_type`, `description?`, `language?`, `file`. It computes SHA-256, rejects duplicates within the case (409 with `evidence_id`), stores the file, registers it on-chain, and writes the database rows and audit log. The OCR page reuses the evidence ID from a 409 response. Full description: Chapter 7, Section 7.6.

## 4.5 Obsolete OCR route

`GET /ai/bns/case/{case_id}` is not OCR, but it sits in the same code region and returns a constant `{"data": []}` after an access check. The functional BNS read route is `GET /bns/case/{case_id}` (Chapter 6).

## 4.6 Endpoint summary

| Method | Route | Auth | Case check | Writes DB | Audit |
|---|---|---|---|---|---|
| POST | `/ai/ocr/{evidence_id}` | JWT | yes | `ocr_results` | "OCR Extraction" (fresh only) |
| POST | `/ai/ocr` | JWT | yes | `ocr_results` | "OCR Extraction" (fresh only) |
| GET | `/ocr/search` | JWT | per result | no | no |
