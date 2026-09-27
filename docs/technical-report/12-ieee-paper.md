# Secure Audit: Multilingual Hybrid OCR, Graph-Attention Statutory Classification, and Blockchain-Anchored Integrity for Digital Evidence

*Draft manuscript in IEEE conference style. Author block, affiliations and the related-work survey of domain-specific systems are to be completed by the authors. Every quantitative result below is traceable to Chapters 2–7 of this report.*

---

**Abstract**—Police investigations in India handle documentary evidence that mixes English with several Indic scripts, arrives as degraded photographs or scans, and must remain verifiably unaltered from collection to trial. We present the evidence pipeline of *Secure Audit*, comprising three subsystems.
(i) A script-aware hybrid optical character recognition (OCR) pipeline. PaddleOCR performs orientation correction, text detection and primary recognition. Low-confidence lines are re-read concurrently by competing language recognisers, and lines in scripts where Tesseract is measurably more accurate are re-recognised by Tesseract from rectified line crops, with explicit repair rules for engine-specific failure modes.
(ii) A retrieval-augmented heterogeneous graph attention classifier, with a legal rule layer, that maps First Information Report (FIR) narratives to sections of the Bharatiya Nyaya Sanhita (BNS), 2023.
(iii) An Ethereum smart-contract registry that anchors the SHA-256 digest of every evidence file at upload time, verifies files against the on-chain digest, cross-checks the database copy, and records a chain of custody.
On nine synthetic test pages covering six languages under five degradations, the hybrid OCR achieves a mean character error rate (CER) of 1.18 %, against 4.45 % for PaddleOCR alone and 4.17 % for Tesseract alone. Kannada CER falls from 23.4 % to 0.91 %, and mixed-script pages from 3.08 % to 0.08 %. The integrity module detects content modification, file deletion and database-hash tampering in all end-to-end tests, at 509 737 gas per registration and 142 733 gas per verification. We also report the limitations found during reverse engineering, including open contract access, a deployed classifier running in retrieval-only mode, and a retrieval-score inversion defect.

**Index Terms**—Optical character recognition, Indic scripts, multilingual OCR, digital evidence, chain of custody, blockchain, smart contracts, SHA-256, graph attention networks, legal text classification, Bharatiya Nyaya Sanhita.

---

## I. Introduction

Digital-evidence management systems must satisfy two requirements that are usually solved separately: making documentary evidence *usable* (searchable, readable across languages, mapped to statute) and keeping it *trustworthy* (demonstrably unaltered, with an auditable custody history). In the Indian context both are complicated by linguistic diversity. A single FIR routinely mixes English with Hindi, Kannada, Telugu, Tamil or Malayalam, sometimes within one line, and documents are often captured as low-resolution photographs or photocopies. In addition, the Bharatiya Nyaya Sanhita (BNS), 2023 [20] replaced the Indian Penal Code on 1 July 2024, which requires investigators to cite new statutory sections.

This paper describes, as implemented and measured, three subsystems of the Secure Audit platform:

1. **Hybrid multilingual OCR.** Off-the-shelf engines have complementary strengths. On our test set, PaddleOCR [1] reads Tamil with 1.8 % CER but Kannada with 23.4 %, while Tesseract [2] reads Kannada with 4.0 % CER but degrades sharply on skewed or low-resolution English (up to 64 %). We combine them per text line, using recognition confidence discounted by script consistency as the arbitration signal.
2. **Statutory classification.** A retrieval-augmented model encodes the FIR with Legal-BERT [10], retrieves candidate sections by dense similarity [11], [12], and propagates information over a graph of sections with graph attention [13] before multi-label prediction. A rule layer enforces legal preconditions.
3. **Ledger-anchored integrity.** Evidence digests [17] are registered in an Ethereum smart contract [19] before an upload is committed. Verification uses the contract's own comparison result and detects divergence between the database and the ledger.

**Contributions.**
- **(C1)** A per-line hybrid OCR arbitration scheme (Eqs. 1–3) with concurrent competitive re-recognition and four repair rules (dropped digits, dropped embedded script, missing word spacing, upside-down lines).
- **(C2)** Conditional preprocessing in which each enhancement is gated by a measured image statistic.
- **(C3)** A geometric layout reconstruction that recovers paragraphs, lists and tables from detector polygons.
- **(C4)** An evidence-integrity protocol with explicit *Missing*, *Unregistered* and *database-mismatch* outcomes.
- **(C5)** A candid evaluation that separates measured results from reported and placeholder figures.

## II. Background and Related Work

**OCR.** Modern OCR pipelines separate text detection (e.g. differentiable binarisation, DBNet [3]) from sequence recognition (CRNN with CTC [4] and successors). PP-OCR [1] packages lightweight detectors and recognisers for many languages; Tesseract [2] uses LSTM recognition with page-layout analysis. Classical preprocessing includes Otsu thresholding [5], contrast-limited adaptive histogram equalisation (CLAHE) [6], noise estimation [7] and non-local-means denoising [8]. OCR quality is conventionally measured by edit distance [9].

**Legal text classification.** Domain-adapted transformers such as Legal-BERT [10] improve legal NLP. Sentence embeddings [11] with approximate nearest-neighbour search [12] support retrieval augmentation [16]. Graph attention networks [13] and multi-head attention [14] model relations among labels. The asymmetric loss [15] addresses positive–negative imbalance in multi-label learning.

**Blockchain for integrity.** Hash-linked ledgers [18] and smart-contract platforms [19] provide append-only records. Merkle trees [22] enable compact membership proofs. EIP-155 [23] binds transactions to a chain identifier.

*The authors should extend this section with a survey of prior evidence-management and blockchain chain-of-custody systems. No such systems are cited here, to avoid unverified attributions.*

## III. System Architecture

The platform consists of a FastAPI backend, a separate BNS inference service, a Ganache Ethereum node hosting the `EvidenceRegistry` contract, PostgreSQL (Supabase), object storage and a React client (Fig. 1 in Chapter 1). Evidence upload computes $h=\mathrm{SHA256}(F)$, stores $F$, and registers $h$ on-chain within the same database transaction. An evidence row therefore never exists without a mined registration. OCR operates on stored evidence and persists page-wise results. BNS classification operates on the case narrative. All three modules write to a common audit log.

## IV. Hybrid Multilingual OCR

### A. Input and preprocessing
Inputs are sniffed by content (PDF magic bytes, image decoders), bounded in size and page count, and normalised (EXIF orientation, 16-bit stretch, alpha flattening). PDFs are rasterised page by page at $s=\max(1,\min(300/72,\,2560/L_{pt}))$.

Each enhancement is conditional:
- **Denoising:** $\hat\sigma > 8$, where $\hat\sigma$ is Immerkær's estimate [7] restricted to pixels below the 80th gradient percentile;
- **Upscaling:** longest side $L<1600$, by $\min(1600/L,3)$;
- **CLAHE:** $\operatorname{median}(I) - P_{0.2}(I) < 100$;
- **Deskew:** by projection profile,

$$\theta^* = \arg\max_{\theta\in[-45^\circ,45^\circ]}\operatorname{Var}_r\Bigl[\textstyle\sum_c B_\theta(r,c)\Bigr],$$

applied only if $|\theta^*|\ge0.3^\circ$ and the variance improves by at least 15 %.

Quarter-turn rotation is resolved by a document-orientation classifier. The text-line orientation classifier is disabled because it labelled all upright Devanagari lines as inverted on our data; per-line inversion is instead tested by re-recognition.

### B. Detection and primary recognition
A lightweight DB-style detector produces quadrilaterals. Each line crop is rectified by the homography mapping its quadrilateral to an axis-aligned rectangle, then recognised by the primary language's recogniser.

### C. Competitive re-recognition
For line text $t$ with confidence $c$ read by the model of language $\ell$, let $n_s(t)$ count characters of script $s$ and $N(t)=\sum_s n_s(t)$. We define the native-script ratio and reading score

$$\nu_\ell(t)=\frac{n_{S(\ell)}(t)+[\ell\neq\mathrm{en}]\,n_{\mathrm{latin}}(t)}{N(t)},\qquad R(t,c,\ell)=c\,\bigl(0.5+0.5\,\nu_\ell(t)\bigr). \tag{1}$$

Lines with $R<0.93$ are re-read concurrently by every other candidate language. A reading $(t',c',\ell')$ replaces the incumbent when its own-script ratio satisfies $\rho_{\ell'}(t') = n_{S(\ell')}(t')/N(t') \ge 0.2$, it contains at least three letters of $S(\ell')$ (for $\ell'\ne$ en), and

$$R(t',c',\ell') > R(t,c,\ell)+0.02\ \ \lor\ \ \mathrm{AddsMissing}(t,t',c',\ell'), \tag{2}$$

where $\mathrm{AddsMissing}$ holds when $t'$ agrees with $t$ on Latin characters (Ratcliff–Obershelp similarity [24] ≥ 0.8), adds at least two letters of the missing script, and $c'\ge0.7$. This recovers bilingual labels such as "District (जिला)" that a confident English reading silently drops. If any alternate language wins a line, all remaining lines are also compared against it.

### D. Tesseract refinement and repair rules
Lines assigned to Kannada or Malayalam (Malayalam has no PaddleOCR model) are re-recognised by Tesseract with the combined model `<lang>+eng`. All such crops of a page are stacked into one image, scaled to a 64-pixel line height, and read in a single process invocation; words are mapped back to crops by vertical position. A Tesseract reading is accepted if its confidence is ≥ 0.3 and its own-script ratio is ≥ 0.5.

Because Tesseract was observed to drop leading "1" digits on real FIR typefaces, digit runs $D(\cdot)$ of the Tesseract and PaddleOCR readings are aligned, and a Tesseract run $d$ is replaced by the PaddleOCR run $d'$ when

$$|d'|>|d| \ \wedge\ d' \text{ ends with } d. \tag{3}$$

Further repairs:
- Indic digit zero after a letter of the same script is mapped to the anusvara;
- legacy Malayalam chillu sequences are mapped to atomic code points;
- word spacing is restored for space-poor recognisers by splitting crops at blank columns wider than $\max(0.22h,\,2\cdot\mathrm{median\ gap})$.

### E. Layout and confidence
Boxes are de-skewed by the median line angle and grouped into rows by vertical overlap with the row's *median* band, which resists tall handwriting boxes. Rows are split into cells at gaps $\ge\max(2.5\tilde w_{char},1.2\tilde h)$. Runs of at least three multi-cell rows with at least two recurrent columns are emitted as tables. Page and document confidence are character-weighted means $C=\sum_j |t_j|c_j/\sum_j|t_j|$. Languages are reported when their script share is ≥ 5 % or they contribute at least 20 characters.

## V. BNS Section Classification

The FIR text is encoded as the Legal-BERT [10] CLS vector $h\in\mathbb{R}^{768}$ (≤ 512 tokens) and as a MiniLM sentence vector $q\in\mathbb{R}^{384}$ [11]. Candidate sections are retrieved from an exact inner-product index [12] over $N$ unit-norm section embeddings, and retrieval scores $r$ are appended to $h$. A case encoder maps $[h;r]$ to $c\in\mathbb{R}^{384}$. Section nodes, initialised with their embeddings, pass through two 4-head GAT layers [13] (4 × 256 dimensions each). Their projection serves as keys and values for a 4-head cross-attention [14] with query $c$. The concatenation of $c$, the attended vector, and mean- and max-pooled node states ($\mathbb{R}^{2816}$) feeds a shared 1536-unit layer, then $N$ independent sigmoid section experts and a 13-way softmax crime head.

Training on 10 000 template-generated cases (57 sections, 13 crime types; 70/15/15 stratified split) minimised

$$\mathcal{L}=0.85\,\mathcal{L}_{\mathrm{ASL}}(\gamma^{+}=2,\gamma^{-}=2,m=0.05)+0.15\,\mathcal{L}_{\mathrm{CE}} \tag{4}$$

with AdamW, plateau learning-rate decay, gradient clipping and early stopping. A rule layer then enforces offence-cluster thresholds and factual preconditions: murder requires violence cues; child-specific sections require a minor; female-specific sections require a female victim; property facts suppress kidnapping. It applies a bounded cluster-consistency boost $b=\operatorname{clip}(1+0.6(\bar s_c-\bar s)/\bar s,\,0.6,\,1.6)$.

## VI. Blockchain Evidence Integrity

The `EvidenceRegistry` contract (Solidity 0.8.28) maps an evidence identifier to $(\text{case},\ \text{file name},\ h,\ \text{uploader},\ \text{timestamp})$ and an append-only custody list. Registration rejects duplicates. Verification emits `EvidenceVerified(isMatch)` with $\mathrm{isMatch}=[\mathrm{keccak256}(h_{chain})=\mathrm{keccak256}(h_{given})]$.

Server-side verification computes $h_F=\mathrm{SHA256}(F_{stored})$, obtains the contract's verdict from the transaction receipt, appends a VERIFIED custody entry, and evaluates

$$\mathrm{Verified}\iff h_F=h_{chain},\qquad \mathrm{DBIntact}\iff h_{db}=h_{chain}. \tag{5}$$

Absent files yield *Missing* (HTTP 404) and absent registrations yield *Unregistered* (HTTP 409), each with an audit entry. A storage outage leaves the status unchanged. Under second-preimage resistance, a modified file passes with probability $2^{-256}$.

## VII. Experimental Evaluation

### A. Setup
Intel Core i5-1335U (12 threads), 15.7 GB RAM, CPU inference (PaddlePaddle 3.1 with MKL-DNN; the integrated GPU is not supported), PaddleOCR 3.7, Tesseract 5.4 (`tessdata_best`), Ganache 7.9.2.

The OCR corpus consists of nine synthetic pages rendered with complex-script shaping (English, dense English, Hindi, Kannada, Telugu, Tamil, Malayalam, and two mixed pages with a list and a table). Each page is evaluated under five conditions: clean, ×0.4 resolution, blur + noise (σ=20), 3° skew, and simulated photograph (perspective, illumination gradient, JPEG quality 55). CER is computed after NFC normalisation and whitespace collapsing.

### B. OCR accuracy

**TABLE I. Mean CER (%) over five degradations**

| Document | PaddleOCR | Tesseract (best) | Hybrid |
|---|---|---|---|
| English | 0.00 | 0.00 | 0.00 |
| English, dense | 0.38 | 9.17 | 0.38 |
| Hindi | 1.50 | 0.00 | 1.50 |
| Kannada | 23.43 | 4.00 | 0.91 |
| Telugu | 4.89 | 4.24 | 4.78 |
| Tamil | 1.76 | 5.91 | 1.76 |
| Malayalam | — | 10.16 | 0.65 |
| Mixed (EN+HI+KN) | 3.08 | 1.08 | 0.08 |
| Mixed (EN+TA+TE) | 0.59 | 3.00 | 0.59 |
| **Mean** | 4.45* | 4.17 | **1.18** |

\*Eight documents; PaddleOCR has no Malayalam model.

Hindi is intentionally left on PaddleOCR despite Tesseract's lower synthetic CER, because on a real FIR Tesseract dropped leading digits in times and section numbers ("17:30" → "7:30", "154" → "54"). With automatic language detection over six languages, both mixed pages were labelled correctly (`en+hi+kn`, `en+ta+te`).

### C. OCR latency

**TABLE II. Latency, warm models (seconds per page)**

| Configuration | Time |
|---|---|
| Default PaddleOCR 3.7 models (v6 medium), 4-line English page | ≈ 32 |
| Mobile models (chosen), same page | ≈ 2.5 |
| MKL-DNN versus plain CPU: detection / recognition | 0.43 / 3.25 vs 1.61 / 12.83 |
| Trilingual FIR page, 18 lines (hybrid) | 14–17 |
| Noisy photocopy, 71 lines: sequential vs concurrent re-recognition | 37.1 vs 25.2 |

### D. Integrity

**TABLE III. Gas consumption (Ganache)**

| Transaction | Gas |
|---|---|
| `registerEvidence` (production-length identifiers) | 509 737 |
| `verifyEvidence` + `addCustodyRecord` | 38 075 + 104 658 |

End-to-end tests passed 17/17. Unmodified files verified; modified and replaced files were flagged *Tampered*; a deleted file produced *Missing*; an unregistered item produced *Unregistered*; an altered database hash was reported with $\mathrm{DBIntact}=\text{false}$ while the file still verified. A single-bit change to a 31 965-byte evidence image altered on average 127.85 of 256 digest bits (σ = 8.21, 1000 trials), consistent with the avalanche expectation of $128\pm8$.

### E. BNS classification (reported)
The training notebook reports, on the 1500-case synthetic test split: section Hamming accuracy 0.9988, exact match 0.9527, micro-F1 0.9871, macro-F1 0.9840; crime-type accuracy 0.9927.

These figures measure fit to a template generator, not field performance. The deployed service did not run this model: no checkpoint is deployed, and the served label space (83 sections) differs from the trained one (57). The repository's ablation table contains placeholder values for all but the full model and is therefore not reported.

## VIII. Security Analysis

The integrity guarantee reduces to SHA-256 second-preimage resistance *given a trustworthy ledger record*. Reverse engineering identified conditions that weaken that premise:
- the contract has no access control, and the development node uses a publicly known deterministic key;
- an application endpoint accepts caller-supplied digests for registration;
- the development chain is in-memory;
- evidence objects are served from public storage URLs.

A client-supplied-hash *verification* endpoint that previously could set an evidence item to *Verified* was changed so that only server-side re-hashing alters status. Transaction replay across chains is prevented by nonces and EIP-155 chain binding [23]. No large-language-model components exist, so prompt-injection risks do not apply.

## IX. Limitations and Threats to Validity

1. The OCR corpus is synthetic, small, and uses one typeface per script. Handwriting, stamps and photocopy artefacts are under-represented. A real 450×645-pixel photocopy with ≈5-pixel Kannada labels remained unreadable.
2. PDF text layers and page-level perspective correction are not used.
3. Runtime is CPU-bound (≈15 s for a trilingual page) and there is no asynchronous job model.
4. The deployed BNS service runs in retrieval-only mode and converts inner-product similarity $s$ into $1-s$. This inverts the scores consumed by the rule layer, which on a burglary narrative discarded the top-ranked "theft in dwelling house" section. No confidence is exposed to users.
5. The blockchain is a single-node private network, and derived artefacts (OCR text, BNS predictions) are not anchored.

## X. Conclusion and Future Work

Per-line competitive recognition across engines reduced mean CER on multilingual Indian documents from 4.45 % to 1.18 %, with the largest gains on scripts where the primary engine is weak and on mixed-script pages. Anchoring evidence digests on-chain, with explicit handling of missing, unregistered and database-divergent records, makes tampering detectable independently of the application database.

Future work includes:
- role-restricted contract writes and a persistent permissioned network;
- Merkle-batched anchoring [22] of evidence together with OCR and BNS outputs;
- asynchronous page-parallel OCR with GPU acceleration;
- fine-tuned Kannada and Malayalam recognisers;
- correcting the retrieval score and retraining the classifier on the served label space;
- evaluation on real, de-identified FIRs with CER, WER and calibrated classification metrics.

## References

[1] Y. Du, C. Li, R. Guo, X. Yin, W. Liu, J. Zhou, Y. Bai, Z. Yu, Y. Yang, Q. Dang, and H. Wang, "PP-OCR: A practical ultra lightweight OCR system," *arXiv:2009.09941*, 2020.
[2] R. Smith, "An overview of the Tesseract OCR engine," in *Proc. 9th Int. Conf. Document Analysis and Recognition (ICDAR)*, 2007, pp. 629–633.
[3] M. Liao, Z. Wan, C. Yao, K. Chen, and X. Bai, "Real-time scene text detection with differentiable binarization," in *Proc. AAAI Conf. Artificial Intelligence*, 2020.
[4] B. Shi, X. Bai, and C. Yao, "An end-to-end trainable neural network for image-based sequence recognition and its application to scene text recognition," *IEEE Trans. Pattern Anal. Mach. Intell.*, vol. 39, no. 11, pp. 2298–2304, 2017.
[5] N. Otsu, "A threshold selection method from gray-level histograms," *IEEE Trans. Syst., Man, Cybern.*, vol. 9, no. 1, pp. 62–66, 1979.
[6] K. Zuiderveld, "Contrast limited adaptive histogram equalization," in *Graphics Gems IV*, P. S. Heckbert, Ed. Academic Press, 1994, pp. 474–485.
[7] J. Immerkær, "Fast noise variance estimation," *Computer Vision and Image Understanding*, vol. 64, no. 2, pp. 300–302, 1996.
[8] A. Buades, B. Coll, and J.-M. Morel, "A non-local algorithm for image denoising," in *Proc. IEEE Conf. Computer Vision and Pattern Recognition (CVPR)*, 2005, pp. 60–65.
[9] V. I. Levenshtein, "Binary codes capable of correcting deletions, insertions, and reversals," *Soviet Physics Doklady*, vol. 10, no. 8, pp. 707–710, 1966.
[10] I. Chalkidis, M. Fergadiotis, P. Malakasiotis, N. Aletras, and I. Androutsopoulos, "LEGAL-BERT: The muppets straight out of law school," in *Findings of EMNLP*, 2020.
[11] N. Reimers and I. Gurevych, "Sentence-BERT: Sentence embeddings using Siamese BERT-networks," in *Proc. EMNLP-IJCNLP*, 2019.
[12] J. Johnson, M. Douze, and H. Jégou, "Billion-scale similarity search with GPUs," *IEEE Trans. Big Data*, vol. 7, no. 3, pp. 535–547, 2021.
[13] P. Veličković, G. Cucurull, A. Casanova, A. Romero, P. Liò, and Y. Bengio, "Graph attention networks," in *Proc. Int. Conf. Learning Representations (ICLR)*, 2018.
[14] A. Vaswani *et al.*, "Attention is all you need," in *Advances in Neural Information Processing Systems (NeurIPS)*, 2017.
[15] T. Ridnik, E. Ben-Baruch, N. Zamir, A. Noy, I. Friedman, M. Protter, and L. Zelnik-Manor, "Asymmetric loss for multi-label classification," in *Proc. IEEE/CVF Int. Conf. Computer Vision (ICCV)*, 2021.
[16] P. Lewis *et al.*, "Retrieval-augmented generation for knowledge-intensive NLP tasks," in *Advances in Neural Information Processing Systems (NeurIPS)*, 2020.
[17] National Institute of Standards and Technology, "Secure Hash Standard (SHS)," FIPS PUB 180-4, 2015.
[18] S. Nakamoto, "Bitcoin: A peer-to-peer electronic cash system," 2008.
[19] G. Wood, "Ethereum: A secure decentralised generalised transaction ledger," Ethereum Yellow Paper.
[20] The Bharatiya Nyaya Sanhita, 2023 (Act No. 45 of 2023), Government of India.
[21] T.-Y. Lin, P. Goyal, R. Girshick, K. He, and P. Dollár, "Focal loss for dense object detection," in *Proc. IEEE Int. Conf. Computer Vision (ICCV)*, 2017.
[22] R. C. Merkle, "A digital signature based on a conventional encryption function," in *Advances in Cryptology — CRYPTO '87*, LNCS 293, 1988, pp. 369–378.
[23] V. Buterin, "EIP-155: Simple replay attack protection," Ethereum Improvement Proposals, 2016.
[24] J. W. Ratcliff and D. E. Metzener, "Pattern matching: The gestalt approach," *Dr. Dobb's Journal*, July 1988.

*Verify each reference against the publisher's record before submission (page ranges and author lists in particular).*
