# Secure Audit — 3D Photogrammetry Overall Pipeline Performance Summary

## Executive Summary & Empirical Quality Baseline

This comprehensive research evaluation synthesizes empirical performance metrics across all **26 reconstruction trials** in the Secure Audit photogrammetry pipeline. The primary report focuses on overarching system stability, keyframe selection efficiency, Structure-from-Motion (SfM) geometric precision, Multi-View Stereo (MVS) point cloud density, Poisson mesh complexity, and end-to-end processing throughput.

> [!NOTE]
> **Inclusion Criteria:** All historical job workspaces present in the photogrammetry repository ($N = 26$).  
> **Exclusion Criteria:** Failed and incomplete runs excluded from dense surface geometry and mesh distributions; itemized separately in failure audit.

---

## 1. Pipeline Reliability & Success Breakdown

| Metric | Count / Value | Proportion | Description |
| :--- | :--- | :--- | :--- |
| **Total Reconstruction Runs** | **26** | 100.0% | Total experimental runs recorded across test datasets |
| **Successful Runs** | **20** | **76.92%** | Full pipeline completed with dense point cloud & 3D GLB export |
| **Failed Runs** | 3 | 11.54% | Terminated due to insufficient feature matches or textureless surfaces |
| **Incomplete / Aborted Runs** | 3 | 11.54% | Pipeline stopped prior to dense point cloud generation |

---

## 2. Keyframe Selection & Camera Pose Registration

| Stage / Metric | Total Volume | Mean per Run | Median per Run | Std Dev | Min – Max |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Candidate Frames Extracted** | 1,892 | — | — | — | — |
| **Keyframes Selected** | 960 | — | — | — | — |
| **Camera Frames Registered** | 732 | — | — | — | — |
| **Per-Job Registration Rate (%)** | — | **71.2%** | **100.0%** | ±39.56% | 6.67% – 100.0% |
| **Weighted Overall Registration Rate** | **76.25%** | *(Total Registered / Total Selected Frames)* | — | — | — |

---

## 3. Structure-from-Motion (SfM) Geometric Accuracy

| Geometric Parameter | Aggregate Measurement | Distribution (Across Runs) | Research Significance |
| :--- | :--- | :--- | :--- |
| **Global Observation-Weighted Error** | **0.8756 px** | Weighted across all 1,996,707 observations | Primary benchmark metric (Sub-pixel accuracy $< 1.0\text{ px}$) |
| **Mean Per-Job Reprojection Error** | **0.7942 px** | Median: **0.8369 px** (±0.2305 px) | Unweighted average across valid reconstruction runs |
| **Reprojection Error Range** | Min: **0.4919 px** | Max: **1.3228 px** | Confirms high geometric stability |
| **Total Triangulated Sparse Points** | **362,233 points** | Mean: 14,489 · Median: 4,006 | Initial 3D feature landmark density |

---

## 4. Dense Point Cloud Reconstruction & Outlier Filtering

*(Calculated across successful reconstruction runs)*

| Pipeline Entity | Total Pipeline Volume | Mean per Run | Median per Run | Std Dev | Min – Max |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Fused MVS Dense Points** | 15,861,223 pts | 793,061 | 649,017 | ±1,000,147 | 25,402 – 4,914,409 |
| **Cleaned Points (Post-SOR)** | 12,800,584 pts | 640,029 | 298,479 | ±1,010,756 | 24,784 – 4,889,173 |
| **Statistical Outliers Removed** | 3,060,639 pts | 153,031 | 4,294 | ±295,967 | 617 – 748,098 |
| **Point Cloud Reduction Ratio (%)** | — | **16.02%** | **1.4%** | ±29.8% | 0.51% – 75.65% |

---

## 5. 3D Surface Mesh Complexity & Export Specifications

*(Calculated across $N = 5$ mesh-reconstructed runs)*

| Metric | Total Aggregate | Mean per Run | Median per Run | Min – Max |
| :--- | :--- | :--- | :--- | :--- |
| **Mesh Vertices** | 1,402,717 vtx | 280,543 | 175,085 | 88,917 – 788,505 |
| **Mesh Triangles (Faces)** | 2,792,519 faces | 558,503 | 349,999 | 177,403 – 1,565,118 |
| **Exported GLB File Size** | 200.35 MB (Total) | **10.02 MB** | **8.22 MB** | 1.69 MB – 18.12 MB |
| **End-to-End Processing Time** | — | **31.29 min** (1877s) | **26.02 min** (1561s) | 2.6 – 107.73 min |

---

## 6. Individual Job Traceability Table

For full experimental auditability, individual test run parameters are preserved below:

| Job ID (Short) | Outcome Status | Video Resolution | Video FPS | Extracted Frames | Selected Keyframes | Registered Frames | Registration Rate (%) | Sparse 3D Points | Mean Reprojection Error (px) | SfM Observations | Dense Points (Fused) | Dense Points (Cleaned) | Points Removed (Count) | Points Removed (%) | Mesh Vertices | Mesh Triangles | GLB Size (MB) | Duration (Seconds) | Duration (Minutes) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0882dd2e-b60... | Successful | 1920x1080 | 60.00 | 30 | 30 | 30.00 | 100.00 | 12529.00 | 0.49 | 41633.00 | 460395.00 | 456070.00 | 4325.00 | 0.94 | — | — | 5.33 | 1066.00 | 17.77 |
| 1be1db93-32b... | Successful | 1920x1080 | 60.00 | 15 | 15 | 6.00 | 40.00 | 313.00 | 0.49 | 986.00 | 25408.00 | 24791.00 | 617.00 | 2.43 | — | — | 1.69 | 175.20 | 2.92 |
| 213a5f7f-cff... | Failed | 1920x1080 | 60.00 | 30 | 30 | 2.00 | 6.67 | 65.00 | 1.14 | 130.00 | — | — | — | — | — | — | — | 26.40 | 0.44 |
| 2ceb59c7-f76... | Successful | 848x478 | 30.00 | 130 | 30 | 27.00 | 90.00 | 4006.00 | 0.77 | 13839.00 | 258622.00 | 254951.00 | 3671.00 | 1.42 | — | — | 16.98 | 732.20 | 12.20 |
| 3bea6f4a-21d... | Incomplete | 478x850 | 30.00 | 134 | 60 | 60.00 | 100.00 | 35109.00 | 0.88 | 237893.00 | — | — | — | — | — | — | — | — | — |
| 52dc2afa-c79... | Incomplete | 478x850 | 30.00 | 134 | 60 | 60.00 | 100.00 | 35108.00 | 0.88 | 237905.00 | — | — | — | — | — | — | — | — | — |
| 54ea72fb-95d... | Failed | 1920x1080 | 60.00 | 30 | 30 | 2.00 | 6.67 | 65.00 | 1.14 | 130.00 | — | — | — | — | — | — | — | 80.90 | 1.35 |
| 54f0cecd-0b1... | Successful | 478x850 | 30.00 | 134 | 60 | 60.00 | 100.00 | 35115.00 | 0.88 | 237900.00 | 984200.00 | 240574.00 | 743626.00 | 75.56 | 175126.00 | 349999.00 | 13.36 | 1892.20 | 31.54 |
| 59d0f8e1-40a... | Successful | 1920x1080 | 60.00 | 15 | 15 | 6.00 | 40.00 | 313.00 | 0.49 | 986.00 | 25402.00 | 24784.00 | 618.00 | 2.43 | — | — | 1.69 | 156.00 | 2.60 |
| 5f7f37ad-a46... | Incomplete | 1920x1080 | 60.00 | 30 | 30 | 2.00 | 6.67 | 44.00 | 0.90 | 88.00 | — | — | — | — | — | — | — | — | — |
| 6b41c4db-a6e... | Successful | 1920x1080 | 60.00 | 30 | 30 | 30.00 | 100.00 | 13956.00 | 0.52 | 47820.00 | 842136.00 | 837639.00 | 4497.00 | 0.53 | — | — | 6.73 | 1932.90 | 32.22 |
| 932aa89e-ff6... | Successful | 478x850 | 30.00 | 134 | 60 | 60.00 | 100.00 | 35108.00 | 0.88 | 237875.00 | 982921.00 | 240153.00 | 742768.00 | 75.57 | 788505.00 | 1565118.00 | 13.35 | 2356.60 | 39.28 |
| 9f80404e-eec... | Successful | 848x478 | 30.00 | 130 | 30 | 27.00 | 90.00 | 3959.00 | 0.77 | 13694.00 | 259351.00 | 255466.00 | 3885.00 | 1.50 | — | — | 16.84 | 727.70 | 12.13 |
| a1502efa-e32... | Successful | 1920x1080 | 60.00 | 30 | 30 | 30.00 | 100.00 | 13880.00 | 0.52 | 47537.00 | 838083.00 | 833149.00 | 4934.00 | 0.59 | — | — | 6.39 | 2207.50 | 36.79 |
| a66f9e2c-890... | Successful | 1920x1080 | 60.00 | 30 | 30 | 2.00 | 6.67 | 44.00 | 0.90 | 88.00 | 840879.00 | 836615.00 | 4264.00 | 0.51 | — | — | 7.52 | 1956.50 | 32.61 |
| a70ee121-75e... | Failed | 1920x1080 | 60.00 | 30 | 30 | — | — | — | — | — | — | — | — | — | — | — | — | 27.60 | 0.46 |
| b67dc62a-590... | Successful | 848x478 | 30.00 | 118 | 30 | 30.00 | 100.00 | 3617.00 | 0.84 | 19157.00 | 346315.00 | 341492.00 | 4823.00 | 1.39 | — | — | 18.12 | 1230.50 | 20.51 |
| c199a911-ac5... | Successful | 848x478 | 30.00 | 130 | 30 | 27.00 | 90.00 | 3886.00 | 0.76 | 13423.00 | 255564.00 | 251725.00 | 3839.00 | 1.50 | — | — | 16.36 | 727.10 | 12.12 |
| c48923a4-0fe... | Successful | 1920x1080 | 60.00 | 30 | 30 | 30.00 | 100.00 | 13837.00 | 0.52 | 47485.00 | 842639.00 | 838277.00 | 4362.00 | 0.52 | — | — | 8.92 | 3520.50 | 58.67 |
| c60021db-fcf... | Successful | 478x850 | 30.00 | 134 | 60 | 60.00 | 100.00 | 35108.00 | 0.88 | 237905.00 | 984847.00 | 239793.00 | 745054.00 | 75.65 | 175084.00 | 349999.00 | 13.36 | 4862.70 | 81.05 |
| c785cb3f-8f5... | Successful | 848x478 | 30.00 | 130 | 30 | 27.00 | 90.00 | 3973.00 | 0.77 | 13754.00 | 250407.00 | 246842.00 | 3565.00 | 1.42 | — | — | 16.66 | 731.10 | 12.19 |
| cd8e0485-2e2... | Successful | 1920x1080 | 60.00 | 30 | 30 | 2.00 | 6.67 | 65.00 | 1.14 | 130.00 | 462280.00 | 458180.00 | 4100.00 | 0.89 | — | — | 5.25 | 842.60 | 14.04 |
| e1017786-5cd... | Successful | 1920x1080 | 60.00 | 30 | 30 | 2.00 | 6.67 | 64.00 | 1.32 | 128.00 | 462278.00 | 458178.00 | 4100.00 | 0.89 | — | — | 5.25 | 857.60 | 14.29 |
| eba1fb33-13b... | Successful | 1920x1080 | 60.00 | 30 | 30 | 30.00 | 100.00 | 13943.00 | 0.52 | 47702.00 | 835754.00 | 831497.00 | 4257.00 | 0.51 | — | — | 6.41 | 2195.50 | 36.59 |
| ee1023f6-43b... | Successful | 478x850 | 30.00 | 134 | 60 | 60.00 | 100.00 | 35105.00 | 0.88 | 237906.00 | 989333.00 | 241235.00 | 748098.00 | 75.62 | 175085.00 | 350000.00 | 13.36 | 2907.60 | 48.46 |
| max_quality_... | Successful | N/A | N/A | 60 | 60 | 60.00 | 100.00 | 63021.00 | 0.56 | 260613.00 | 4914409.00 | 4889173.00 | 25236.00 | 0.51 | 88917.00 | 177403.00 | 6.78 | 6463.91 | 107.73 |

---

## 7. Integrity & Reference Calibration Notice

- **Geometric Scale & Reference Note:** The reprojection error (px) and point density metrics presented above are computed directly from the camera ray intersections and dense stereo matching residuals. Metric dimension evaluations (MAE/MAPE in cm) require reference ground-truth object dimensions captured with calibrated physical markers.
- **Auditing Guarantee:** All metrics represent actual unadulterated execution telemetry extracted from COLMAP binary databases, Open3D point clouds, and database timestamps.

*Generated automatically by the Secure Audit Photogrammetry Research Evaluation Engine.*