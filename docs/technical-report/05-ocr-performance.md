# Chapter 5 — OCR Performance

All figures in this chapter are **[measured]** on the reference machine (README: Intel Core i5-1335U, 12 logical CPUs, 15.7 GB RAM, integrated Intel Iris Xe, Windows 11). Accuracy figures for the final pipeline were produced from repository commit `b7b478c`.

## 5.1 Compute platform: CPU versus GPU

| Aspect | Finding |
|---|---|
| GPU | The only GPU is an Intel Iris Xe (integrated). PaddlePaddle accelerates only NVIDIA CUDA devices, so it is **not usable**. |
| Paddle build | `paddle.device.is_compiled_with_cuda() = False`; device `cpu`. |
| MKL-DNN (oneDNN) | `paddle.base.core.is_compiled_with_mkldnn() = True`. PaddleX's `get_default_run_mode(model, "cpu")` returns `mkldnn` for every model used (detector, all recognisers, orientation classifier), because `ENABLE_MKLDNN_BYDEFAULT = True` and none of them is on `MKLDNN_BLOCKLIST`. |
| CPU threads | PaddleX default `cpu_threads = 10` per predictor. |

### 5.1.1 MKL-DNN speed-up (same page, same models, 3-run means)

| Stage | `mkldnn` run mode | `paddle` run mode | Speed-up |
|---|---|---|---|
| Detection, `PP-OCRv5_mobile_det` (1700×2200 page) | 0.43 s | 1.61 s | 3.7× |
| Recognition, `en_PP-OCRv5_mobile_rec` (26 lines) | 3.25 s | 12.83 s | 3.9× |

## 5.2 Model selection (per-model latency, 1700×700 English page, 4 lines)

| Model | Latency | Output quality |
|---|---|---|
| `PP-LCNet_x1_0_doc_ori` (page orientation) | 0.02 s | — |
| `PP-OCRv6_medium_det` | 5.01 s | 4 boxes |
| `PP-OCRv5_mobile_det` (**chosen**) | **0.63 s** | 4 boxes |
| `PP-OCRv5_server_det` | 9.64 s | 4 boxes |
| `PP-LCNet_x1_0_textline_ori` | 0.06 s | — (disabled; misclassifies Devanagari) |
| `PP-OCRv6_medium_rec` (PaddleOCR's default for `lang="en"`) | 15.47 s | 4/4 lines correct (0.988–1.000) |
| `en_PP-OCRv5_mobile_rec` (**chosen**) | **0.80 s** | 4/4 lines correct (0.987–1.000) |
| `devanagari_PP-OCRv5_mobile_rec` | 0.80 s | English read correctly (≥ 0.973) |
| `ka_PP-OCRv3_mobile_rec` | 0.30 s | English read correctly (≥ 0.986) |

With PaddleOCR 3.7's defaults (v6 medium detector and recogniser), a four-line English page took about 32 s end to end. The mobile models reduce this to about 2.5 s with identical text on the test pages. The English-only dictionary of `en_PP-OCRv5_mobile_rec` also eliminates spurious CJK glyphs; the v6 recogniser emitted "一" on a non-text photograph. The medium detector remains selectable (`OCR_DET_MODEL`) for CUDA hosts.

## 5.3 Accuracy benchmark

### 5.3.1 Protocol
- **Corpus.** Nine synthetic pages rendered with Windows GDI `TextRenderer`, which uses Uniscribe complex-script shaping; Pillow lacked libraqm and mis-shaped Indic conjuncts.

  | Document | Font | Contents |
  |---|---|---|
  | `english` | Arial | 4 lines |
  | `english_dense` | Times New Roman 22 px | 7 lines |
  | `hindi`, `kannada`, `telugu`, `tamil`, `malayalam` | Nirmala UI | 4 lines each |
  | `mixed` | Nirmala UI + Arial | EN/HI/KN FIR page with a numbered list and a 4×3 table (18 lines) |
  | `mixed_south` | Nirmala UI + Arial | EN/TA/TE, 4 lines |

- **Degradations.**

  | Name | Transformation |
  |---|---|
  | clean | none |
  | lowres | ×0.4 area downscale |
  | noisy | Gaussian blur σ=0.8 plus additive Gaussian noise σ=20 |
  | skew3 | 3° rotation |
  | photo | mild perspective warp, a 0.75→1.0 horizontal illumination gradient, JPEG quality 55 |

- **Metric.** CER (Section 2.16.13) after NFC normalisation, removal of `|`, and whitespace collapsing, so layout differences are not counted as errors.
- **Systems.**

  | System | Description |
  |---|---|
  | PaddleOCR-only | this pipeline with a single-language request, before hybrid recognition |
  | Tesseract-only | Tesseract 5.4 `tessdata_best`, `--oem 1 --psm 3`, on both the raw and the preprocessed image; the better of the two is reported as "best" |
  | Final | the committed hybrid pipeline with the document's language set |

### 5.3.2 Results — mean CER (%) over the five degradations

| Document | PaddleOCR-only | Tesseract-only (raw) | Tesseract-only (best of raw/preprocessed) | **Final hybrid** |
|---|---|---|---|---|
| english | 0.00 | 8.85 | 0.00 | **0.00** |
| english_dense | 0.38 | 22.67 | 9.17 | **0.38** |
| hindi | 1.50 | 0.13 | 0.00 | **1.50** † |
| kannada | 23.43 | 4.11 | 4.00 | **0.91** |
| telugu | 4.89 | 4.67 | 4.24 | **4.78** |
| tamil | 1.76 | 16.58 | 5.91 | **1.76** |
| malayalam | — (no model) | 10.49 | 10.16 | **0.65** |
| mixed (en+hi+kn) | 3.08 | 1.42 | 1.08 | **0.08** |
| mixed_south (en+ta+te) | 0.59 | 3.17 | 3.00 | **0.59** |
| **Mean** | 4.45 ‡ | 8.01 | 4.17 | **1.18** |

† Hindi is deliberately left on PaddleOCR. Tesseract's slight synthetic advantage is outweighed by its systematic loss of leading "1" digits on a real FIR (Section 2.7.2).
‡ Over the eight documents that PaddleOCR can read.

### 5.3.3 Final hybrid — CER (%) by degradation

| Document | clean | lowres | noisy | skew3 | photo |
|---|---|---|---|---|---|
| english | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| english_dense | 0.17 | 1.04 | 0.52 | 0.17 | 0.00 |
| hindi | 1.87 | 1.25 | 1.87 | 1.25 | 1.25 |
| kannada | 0.00 | 1.71 | 1.71 | 0.00 | 1.14 |
| telugu | 5.98 | 4.35 | 4.89 | 4.35 | 4.35 |
| tamil | 2.07 | 1.55 | 1.04 | 1.55 | 2.59 |
| malayalam | 0.00 | 0.54 | 1.08 | 0.54 | 1.08 |
| mixed | 0.00 | 0.14 | 0.14 | 0.00 | 0.14 |
| mixed_south | 0.42 | 0.42 | 1.67 | 0.42 | 0.00 |

### 5.3.4 Automatic language detection (`language="auto"`, all six candidate languages)

| Document | Detected label | CER | Time |
|---|---|---|---|
| mixed | `en+hi+kn` (correct) | 0.00 % | 16.1 s |
| mixed_south | `en+ta+te` (correct) | 0.42 % | 6.2 s |

### 5.3.5 Observations
1. **Engine complementarity.** Tesseract collapses on raw skewed or low-resolution input (english_dense lowres 64 % CER raw; tamil skew3 34.7 % raw), whereas PaddleOCR's detector is robust. Tesseract's recognition, on the other hand, is far better for Kannada (4.0 % versus 23.4 %). Feeding Tesseract PaddleOCR's rectified line crops combines both strengths: Kannada falls to 0.91 %, and Malayalam improves from 10.2 % (Tesseract on whole pages) to 0.65 %.
2. **Mixed-script pages benefit most.** Per-line script identification reduces mixed-page CER from 3.08 % to 0.08 %.
3. **Remaining error is concentrated in Telugu (4.8 %),** which is left on PaddleOCR because Tesseract was not clearly better (4.24 % versus 4.89 %).
4. **Threats to validity.** The corpus is synthetic, uses a single typeface per script, and is small (9 pages, 45 runs). Real FIRs contain handwriting, stamps and photocopy artefacts. Figures are indicative of relative engine behaviour, not of field accuracy.

### 5.3.6 Real-document observations (qualitative, no ground truth)

| Sample | Size | Result |
|---|---|---|
| `fir1.jpg` (English + Hindi FIR photo) | 768×1024 | Confidence 0.96; every date, time and IPC section number correct; 10-row "Acts/Sections" table reconstructed; bilingual labels read, e.g. "Day (दिन): Monday", "(धारा 154 दंड प्रक्रिया सहिंता के तहत)"; languages `en+hi`. |
| `fir2.jpg` (Kannada/English FIR photocopy) | 450×645 | English fields readable; Kannada labels ≈5 px tall are unreadable by either engine. A resolution limit that preprocessing cannot overcome. |
| `skewed image ocr.jpg` | 225×225, ≈45° tilt | Correctly deskewed (skew 45.0°) and read at 0.94 confidence; residual letter errors due to ≈5 px text. |

## 5.4 Execution time

### 5.4.1 Per page (final pipeline, warm models)

| Page type | Time |
|---|---|
| English, 4–7 lines | 2.7–3.3 s |
| Hindi / Telugu / Tamil (single language, 4 lines) | 1.7–3.2 s |
| Kannada / Malayalam (Tesseract refinement) | 3.2–6.0 s |
| Trilingual FIR page, 18 lines | 14.4–16.9 s |
| Real FIR photo (1024×768, en+hi, about 60 lines, `auto`) | about 30–45 s |
| Model cold start (first request per language set) | +13–27 s, a one-off per process |

### 5.4.2 Where the time goes (the `fir2.jpg` photocopy, `auto`, 71 lines, warm)

| Stage | Before parallel re-recognition | After |
|---|---|---|
| Detection + primary recognition | 6.6 s | 6.6 s |
| Re-recognition: Paddle Tamil, Paddle Telugu, Tesseract Hindi (at that revision), Tesseract Malayalam, Tesseract Kannada | 30.5 s, sequential | overlapped |
| **Total** | **37.1 s** | **25.2 s** |

On mixed or noisy pages, re-recognition dominates, because many lines fall below the 0.93 recheck threshold and are read with every candidate language.

### 5.4.3 Large documents
Pages are processed sequentially. A 62-page PDF exceeds `OCR_MAX_PDF_PAGES=50` (HTTP 413). Even with the limit raised, it would exceed the frontend's 300 s request timeout (Chapter 2, Section 2.19).

## 5.5 Memory

| Process state | Resident memory observed |
|---|---|
| Backend with OCR models loaded (production process) | ≈1.3 GB |
| Evaluation process with PaddleOCR v6 *medium* models | ≈1.9 GB |
| 62-page PDF run in progress | 0.86 GB (one page resident at a time) |

Models are cached per language, so memory grows with the number of distinct language sets used: one pipeline per primary language plus one recogniser per alternate. PDF pages are rendered lazily, one at a time.

## 5.6 Optimisations implemented

| Optimisation | Location | Effect |
|---|---|---|
| Mobile detector and recognisers instead of v6 medium | `DETECTION_MODEL`, `RECOGNITION_MODELS` | ≈8–20× faster per stage |
| MKL-DNN execution (PaddleX default, verified) | PaddleX runtime | ≈3.7–3.9× |
| Lazy model loading with a per-language cache | `_load_cached` | no repeated loads; fast API start-up |
| Concurrent alternate-language re-recognition | `_rerecognize.read_all` | 37.1 s → 25.2 s on a noisy photocopy |
| Re-recognise only uncertain lines, escalate only on mixed pages | `_rerecognize` | pure-English pages pay no multilingual cost |
| One Tesseract process per language per page (stacked crops) | `tesseract_engine.read_lines` | avoids per-line process start and model load |
| Conditional preprocessing (each step gated by a statistic) | `preprocess_page` | clean pages skip denoising and CLAHE |
| PDF rendered at ≤ OCR resolution, one page at a time | `_open_pdf` | bounded memory, no wasted pixels |
| OCR result cache with language-aware invalidation | `cached_ocr_is_usable` | repeat requests answered in about 0 ms of OCR time |
| Translation LRU cache, stored translations, provider cool-down | `translation_service`, `translate_ocr_result` | no repeated network calls; fast failure |

## 5.7 Limitations
- CPU-only on the reference machine. Throughput of about 1–4 pages/min for mixed or real documents is adequate for interactive single documents, but not for bulk ingestion.
- Global inference lock (`_inference_lock`): PaddleOCR calls are serialised process-wide, so concurrent OCR requests queue.
- No asynchronous job model, so long documents time out at the client.
- The benchmark corpus is synthetic, and the harness is not committed.

## 5.8 Future scope
1. An NVIDIA GPU with `paddlepaddle-gpu` and the v6 medium models, for higher recall on dense small text.
2. A job queue (e.g. Celery or RQ) with page-level parallelism across worker processes and progress reporting.
3. OpenVINO conversion to use the Iris Xe iGPU, which PaddlePaddle cannot.
4. Batching of Paddle re-recognition across pages.
5. A committed benchmark harness with real, annotated FIR pages, CER and WER per script, and regression gates in CI.
