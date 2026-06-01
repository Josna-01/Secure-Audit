# app/model_wrapper.py
import os
import json
import numpy as np
import logging
import faiss
import torch
from transformers import AutoTokenizer, AutoModel
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any, Optional
import pickle
from .hgat_model import RAGLCHGATModel

# optional cluster mapping used by reranker (postprocess exposes SECTION_TO_CLUSTER)
try:
    from .postprocess import SECTION_TO_CLUSTER
except Exception:
    SECTION_TO_CLUSTER = {}

logger = logging.getLogger("bns-model-wrapper")
logger.setLevel(logging.INFO)


class RAGHGATWrapper:
    """
    Full wrapper: BERT CLS + retrieval + HGAT model + optional lightweight reranker
    """

    def __init__(self, model_dir: str):
        self.model_dir = model_dir
        logger.info(f"Initializing model wrapper with model_dir={model_dir}")
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"Using device: {self.device}")

        # --- BERT CLS encoder
        self.bert_name = os.getenv("LEGAL_BERT_NAME", "nlpaueb/legal-bert-base-uncased")
        self.tokenizer = AutoTokenizer.from_pretrained(self.bert_name)
        self.bert = AutoModel.from_pretrained(self.bert_name).to(self.device)
        self.bert.eval()

        # --- sentence-transformer for retrieval embeddings
        self.sent_model_name = os.getenv("SENT_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        self.sent_encoder = SentenceTransformer(self.sent_model_name)
        try:
            # try to set target device for sentence-transformers
            self.sent_encoder._target_device = str(self.device)
        except Exception:
            pass

        # --- load faiss / embeddings / meta
        faiss_path = os.path.join(model_dir, "faiss.index")
        emb_path = os.path.join(model_dir, "section_embeddings.npy")
        meta_path = os.path.join(model_dir, "sections_meta.json")

        self.faiss_index = None
        self.section_embeddings = None
        self.sections_meta = []

        # load index or embeddings
        if os.path.exists(faiss_path):
            try:
                self.faiss_index = faiss.read_index(faiss_path)
                logger.info(f"Loaded FAISS index from {faiss_path}")
            except Exception as e:
                logger.exception(f"Failed to read FAISS index: {e}")
                self.faiss_index = None
        elif os.path.exists(emb_path):
            try:
                self.section_embeddings = np.load(emb_path)
                logger.info(f"Loaded section_embeddings.npy shape={self.section_embeddings.shape}")
            except Exception as e:
                logger.exception(f"Failed to load section_embeddings.npy: {e}")
                self.section_embeddings = None
        else:
            logger.warning("No FAISS index or embeddings found; retrieval disabled.")

        # load sections_meta and normalize to expected fields: id, text, title (optional), keywords (optional)
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as fh:
                    raw_meta = json.load(fh)
                norm_meta = []
                for m in raw_meta:
                    sid = m.get("id") or m.get("section_id") or m.get("section") or ""
                    text = m.get("text") or m.get("description") or ""
                    title = m.get("title") or (text[:80] if text else None)
                    kws = m.get("keywords") or []
                    norm_meta.append({"id": sid, "text": text, "title": title, "keywords": kws})
                self.sections_meta = norm_meta
                logger.info(f"Loaded sections_meta.json ({len(self.sections_meta)} entries).")
            except Exception as e:
                logger.exception(f"Failed to load sections_meta.json: {e}")
                self.sections_meta = []
        else:
            # fallback to app.bns if available
            try:
                from .bns import BNS_SECTION_DETAILS
                meta_list = []
                for sid, info in BNS_SECTION_DETAILS.items():
                    txt = " ".join([info.get("title", ""), info.get("description", "")] + info.get("keywords", []))
                    title = info.get("title") or (txt[:80] if txt else None)
                    meta_list.append({"id": sid, "text": txt, "title": title, "keywords": info.get("keywords", [])})
                self.sections_meta = meta_list
                logger.info("Built sections_meta from fallback BNS_SECTION_DETAILS.")
            except Exception:
                logger.warning("No sections_meta.json and no bns fallback; sections_meta is empty.")

        # --- node features (section embeddings) for HGAT if available
        sec_tensor = None
        if os.path.exists(emb_path):
            try:
                sec_embs = np.load(emb_path)
                sec_tensor = torch.tensor(sec_embs, dtype=torch.float32)
                logger.info("Prepared section node features tensor.")
            except Exception as e:
                logger.exception(f"Failed to prepare section node features: {e}")
                sec_tensor = None

        # --- cooccurrence edges (optional)
        edge_index = None
        cooccur_path = os.path.join(model_dir, "cooccur_edge_index.pt")
        if os.path.exists(cooccur_path):
            try:
                edge_index = torch.load(cooccur_path, map_location=self.device)
                logger.info("Loaded cooccur_edge_index.pt")
            except Exception as e:
                logger.exception(f"Failed to load cooccur_edge_index.pt: {e}")
                edge_index = None

        # --- instantiate model (constructor signature expects these kwargs)
        try:
            num_sections = len(self.sections_meta) if self.sections_meta else 57
            self.model = RAGLCHGATModel(
                num_sections=num_sections,
                section_node_features=sec_tensor,
                edge_index=edge_index,
                device=self.device
            )
            logger.info("RAGLCHGATModel instantiated.")
        except Exception as e:
            logger.exception(f"Failed to instantiate RAGLCHGATModel: {e}")
            self.model = None

        # --- load checkpoint with safer fallback
        weights_path = os.path.join(model_dir, "best_rag_hgat_model.pth")
        if os.path.exists(weights_path) and self.model is not None:
            logger.info(f"Attempting to load checkpoint from {weights_path}")
            checkpoint = None
            try:
                checkpoint = torch.load(weights_path, map_location=self.device)
            except Exception as e1:
                logger.warning(f"Default torch.load failed: {e1}")
                try:
                    logger.warning("Retrying torch.load(weights_only=False). Only use with trusted checkpoints.")
                    checkpoint = torch.load(weights_path, map_location=self.device, weights_only=False)
                except Exception as e2:
                    logger.exception(f"Second torch.load attempt failed: {e2}")
                    checkpoint = None

            if checkpoint is not None:
                state = checkpoint
                if isinstance(checkpoint, dict):
                    for cand in ("state_dict", "model_state_dict", "model"):
                        if cand in checkpoint:
                            state = checkpoint[cand]
                            break
                if isinstance(state, dict):
                    cleaned = {k.replace("module.", ""): v for k, v in state.items()}
                    try:
                        self.model.load_state_dict(cleaned)
                        logger.info("Loaded state_dict into HGAT model (cleaned keys).")
                    except Exception as e:
                        logger.exception(f"Clean load failed: {e}")
                        try:
                            self.model.load_state_dict(state)
                            logger.info("Loaded raw state into HGAT model.")
                        except Exception as e2:
                            logger.exception(f"Raw load failed: {e2}")
                            self.model = None
                else:
                    logger.warning("Checkpoint did not contain a state dict; skipping model load.")
                    self.model = None

            if self.model is not None:
                try:
                    self.model.to(self.device)
                    self.model.eval()
                except Exception as e:
                    logger.exception(f"Failed to move model to device: {e}")
        else:
            if not os.path.exists(weights_path):
                logger.warning("No checkpoint found; running in retrieval-only/fallback mode.")
            else:
                logger.warning("Checkpoint exists but HGAT model object is None; skipping load.")

        # --- sigmoid/softmax helpers
        self.sigmoid = torch.nn.Sigmoid()
        self.softmax = torch.nn.Softmax(dim=-1)

        # --- reranker (optional)
        self.reranker = None
        self.reranker_cfg = None
        self._load_reranker()

    # --- reranker utilities ---
    def _load_reranker(self):
        path = os.path.join(self.model_dir, "reranker.pkl")
        cfg_path = os.path.join(self.model_dir, "reranker_config.json")
        try:
            if os.path.exists(path):
                with open(path, "rb") as fh:
                    self.reranker = pickle.load(fh)
                    logger.info(f"Loaded reranker from {path}")
            if os.path.exists(cfg_path):
                with open(cfg_path, "r", encoding="utf-8") as fh:
                    self.reranker_cfg = json.load(fh)
                    logger.info("Loaded reranker config")
        except Exception as e:
            logger.exception(f"Failed to load reranker: {e}")
            self.reranker = None
            self.reranker_cfg = None

    def _encode_for_reranker(self, facts: str, top_k: int = 20):
        """Return (cls_emb_numpy, rag_vector_numpy or None, retrieval_hits list)"""
        tok = self.tokenizer(facts, truncation=True, padding="max_length", max_length=512, return_tensors="pt")
        tok = {k: v.to(self.device) for k, v in tok.items()}
        with torch.no_grad():
            bert_out = self.bert(**tok)
            cls_emb_t = bert_out.last_hidden_state[:, 0, :]  # (1, H)
        cls_emb = cls_emb_t.squeeze(0).cpu().numpy()

        hits = self.retrieve(facts, top_k=top_k)
        rag_vector = None
        if self.sections_meta and isinstance(self.sections_meta, list):
            vect = np.zeros(len(self.sections_meta), dtype=np.float32)
            for h in hits:
                sid = str(h["section_id"])
                score = float(h["score"])
                for idx, meta in enumerate(self.sections_meta):
                    if str(meta.get("id")) == sid:
                        vect[idx] = max(vect[idx], score * 10.0)
                        break
            rag_vector = vect
        return cls_emb, rag_vector, hits

    def _apply_reranker(self, candidates: List[Dict[str, Any]], cls_emb: np.ndarray, rag_vector: Optional[np.ndarray], raw_retrieval: List[Dict[str, Any]]):
        """
        candidates: list of dicts with keys: section_id, score (model score), evidence, rag_score
        returns list sorted by combined score (reranker + model)
        """
        if not candidates:
            return []

        # fallback sort if no reranker
        if self.reranker is None:
            return sorted(candidates, key=lambda x: (float(x.get("score", 0.0)), float(x.get("rag_score", 0.0))), reverse=True)

        feats = []
        for c in candidates:
            model_score = float(c.get("score", 0.0))
            rag_score = float(c.get("rag_score", 0.0))
            cls_mean = float(np.mean(cls_emb)) if cls_emb is not None else 0.0
            rag_mean = float(np.mean(rag_vector)) if rag_vector is not None else 0.0

            cluster = SECTION_TO_CLUSTER.get(str(c.get("section_id")), "default")
            cluster_vec = []
            if self.reranker_cfg and "clusters" in self.reranker_cfg:
                for cl in self.reranker_cfg["clusters"]:
                    cluster_vec.append(1.0 if cl == cluster else 0.0)

            feat = [cls_mean, rag_mean, model_score, rag_score] + cluster_vec
            feats.append(feat)

        X = np.array(feats, dtype=np.float32)
        try:
            if hasattr(self.reranker, "predict_proba"):
                scores = self.reranker.predict_proba(X)[:, 1]
            else:
                scores = self.reranker.predict(X)
        except Exception as e:
            logger.exception(f"Reranker predict failed: {e}")
            return sorted(candidates, key=lambda x: x["score"], reverse=True)

        alpha = float(self.reranker_cfg.get("alpha", 0.7)) if self.reranker_cfg else 0.7
        for c, s in zip(candidates, scores):
            c["reranker_score"] = float(s)
            c["combined_score"] = alpha * float(s) + (1.0 - alpha) * float(c.get("score", 0.0))

        return sorted(candidates, key=lambda x: x["combined_score"], reverse=True)

    # --- retrieval ---
    def retrieve(self, query_text: str, top_k: int = 20) -> List[Dict[str, Any]]:
        q_emb = self.sent_encoder.encode([query_text], convert_to_numpy=True)
        # FAISS branch
        if self.faiss_index is not None:
            D, I = self.faiss_index.search(q_emb.astype("float32"), top_k)
            hits = []
            for dist, idx in zip(D[0], I[0]):
                if idx < 0:
                    continue
                meta = self.sections_meta[idx] if idx < len(self.sections_meta) else {"id": str(idx), "text": ""}
                # convert distance to similarity approx
                text_field = meta.get("text") or meta.get("description") or ""
                hits.append({"section_id": meta.get("id", str(idx)), "score": float(1.0 - dist), "text": text_field})
            return hits
        elif self.section_embeddings is not None:
            en = self.section_embeddings
            qn = q_emb / np.linalg.norm(q_emb, axis=1, keepdims=True)
            en_norm = en / np.linalg.norm(en, axis=1, keepdims=True)
            sims = (en_norm @ qn.T).squeeze()
            idxs = np.argsort(-sims)[:top_k]
            hits = []
            for idx in idxs:
                meta = self.sections_meta[idx] if idx < len(self.sections_meta) else {"id": str(idx), "text": ""}
                text_field = meta.get("text") or meta.get("description") or ""
                hits.append({"section_id": meta.get("id", str(idx)), "score": float(sims[idx]), "text": text_field})
            return hits
        else:
            logger.warning("Retrieval requested but no index/embeddings found.")
            return []

    # --- full predict pipeline (with reranker integrated) ---
    def predict(self, facts: str, title: str = None, top_k: int = 20) -> Dict[str, Any]:
        # CLS embedding
        tok = self.tokenizer(facts, truncation=True, padding="max_length", max_length=512, return_tensors="pt")
        tok = {k: v.to(self.device) for k, v in tok.items()}
        with torch.no_grad():
            bert_out = self.bert(**tok)
            cls_emb = bert_out.last_hidden_state[:, 0, :]

        # Retrieval
        retrieval_hits = self.retrieve(query_text=facts, top_k=top_k)
        rag_scores_map = {}
        for h in retrieval_hits:
            sid = str(h["section_id"])
            s = float(h["score"])
            rag_scores_map[sid] = max(rag_scores_map.get(sid, 0.0), s)

        # Build rag_vector aligned to sections_meta order
        rag_vector = None
        if self.sections_meta and isinstance(self.sections_meta, list):
            vect = np.zeros(len(self.sections_meta), dtype=np.float32)
            for idx, meta in enumerate(self.sections_meta):
                sid = str(meta.get("id"))
                if sid in rag_scores_map:
                    vect[idx] = rag_scores_map[sid] * 10.0
            rag_vector = torch.tensor(vect).unsqueeze(0).to(self.device)

        # Compose features (CLS + rag_vector)
        if rag_vector is not None:
            try:
                features = torch.cat([cls_emb.float(), rag_vector.float()], dim=1)
            except Exception:
                # different dims? fallback to cls only
                features = cls_emb.float()
        else:
            features = cls_emb.float()

        # If no trained model, fallback to retrieval
        if self.model is None:
            predicted_sections = [(h["section_id"], h["score"], h.get("text","")[:400]) for h in retrieval_hits[:5]]
            logger.info("PREDICT (retrieval-only) returning sections=%d retrieval_hits=%d", len(predicted_sections), len(retrieval_hits))
            return {"sections": predicted_sections, "crime_type": "unknown", "raw_retrieval": {"hits": retrieval_hits}}

        # Run model (assumes infer_from_features wrapper available)
        with torch.no_grad():
            outputs = self.model.infer_from_features(features)
            section_logits = outputs.get("section_logits")  # (1, num_sections)
            crime_logits = outputs.get("crime_logits")  # (1, num_crime_types)

            if section_logits is None or crime_logits is None:
                logger.warning("Model outputs missing logits; falling back to retrieval.")
                predicted_sections = [(h["section_id"], h["score"], h.get("text","")[:400]) for h in retrieval_hits[:5]]
                return {"sections": predicted_sections, "crime_type": "unknown", "raw_retrieval": {"hits": retrieval_hits}}

            section_probs = self.sigmoid(section_logits).squeeze(0).cpu().numpy().tolist()
            crime_prob = self.softmax(crime_logits).squeeze(0).cpu().numpy()
            crime_idx = int(np.argmax(crime_prob))

            # map high-prob sections using threshold (0.5 default)
            candidate_list = []
            for idx, prob in enumerate(section_probs):
                try:
                    if prob >= 0.5:
                        sid = (self.sections_meta[idx].get("id") if idx < len(self.sections_meta) else str(idx)) or str(idx)
                        evidence = (self.sections_meta[idx].get("text", "") if idx < len(self.sections_meta) else "")[:400]
                        rag_score = rag_scores_map.get(str(sid), 0.0)
                        candidate_list.append({"section_id": str(sid), "score": float(prob), "evidence": evidence, "rag_score": float(rag_score)})
                except Exception:
                    continue

            # if no positive sections, provide top retrieval hits as soft fallback
            if not candidate_list:
                predicted_sections = [(h["section_id"], h["score"], h.get("text","")[:400]) for h in retrieval_hits[:5]]
                logger.info("PREDICT (model empty) returning retrieval-only sections=%d retrieval_hits=%d", len(predicted_sections), len(retrieval_hits))
                # map crime_idx to label if crime_map exists
                crime_label = "unknown"
                try:
                    crime_map_path = os.path.join(self.model_dir, "crime_map.json")
                    if os.path.exists(crime_map_path):
                        with open(crime_map_path, "r", encoding="utf-8") as fh:
                            crime_map = json.load(fh)
                        crime_label = crime_map.get(str(crime_idx), "unknown")
                except Exception:
                    crime_label = "unknown"
                return {"sections": predicted_sections, "crime_type": crime_label, "raw_retrieval": {"hits": retrieval_hits}}

            # Reranker: build cls_emb and rag_vector numpy and apply
            cls_emb_npy = cls_emb.squeeze(0).cpu().numpy()
            rag_vector_npy = None
            if rag_vector is not None:
                rag_vector_npy = rag_vector.squeeze(0).cpu().numpy()

            reranked = self._apply_reranker(candidate_list, cls_emb_npy, rag_vector_npy, retrieval_hits)

            # Return sections as list of tuples (section_id, score, evidence)
            out_sections = []
            for r in reranked:
                score = r.get("combined_score", r.get("score", 0.0))
                out_sections.append((r["section_id"], float(score), r.get("evidence", "")))

            logger.info("PREDICT returning sections=%d retrieval_hits=%d", len(out_sections), len(retrieval_hits))

            # crime label mapping (map numeric -> human label if crime_map.json exists)
            crime_label = "unknown"
            try:
                crime_map_path = os.path.join(self.model_dir, "crime_map.json")
                if os.path.exists(crime_map_path):
                    with open(crime_map_path, "r", encoding="utf-8") as fh:
                        crime_map = json.load(fh)
                    crime_label = crime_map.get(str(crime_idx), str(crime_idx))
                else:
                    crime_label = str(crime_idx)
            except Exception:
                crime_label = str(crime_idx)

            return {"sections": out_sections, "crime_type": crime_label, "raw_retrieval": {"hits": retrieval_hits}}
