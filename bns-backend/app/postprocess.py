# app/postprocess.py
"""
Law-aware post-processing & reranking layer (final).
Returns BNS-shaped output: {"bns":[{"section_id","name","meaning"}], "crime_type": "..."}

If the post-processing finds nothing, falls back to top retrieval hits and looks up titles/description.
"""
import re
from typing import List, Dict, Any, Optional
import logging
from collections import defaultdict

logger = logging.getLogger("bns-postprocess")
logger.setLevel(logging.INFO)

# Simple metrics counters (in-memory); main.py may scrape via /metrics
_METRICS = defaultdict(int)

def inc_metric(k: str, n: int = 1):
    _METRICS[k] += n

def get_metrics_snapshot() -> Dict[str, int]:
    return dict(_METRICS)

# --- regexes & tokens ---
AGE_RE = re.compile(r'(\b\d{1,3}\b)\s*(?:years?|yrs?)\b', flags=re.I)
NEG_INJURY_PHRASES = re.compile(r'\b(no (one|person) (was )?(injured|hurt)|no injuries|no harm|no assault|no violence)\b', flags=re.I)
NO_WEAPON_PHRASES = re.compile(r'\b(no (weapon|weapons)|unarmed|no arms)\b', flags=re.I)
WEAPON_WORDS = re.compile(r'\b(knife|gun|pistol|weapon|iron rod|sword|machete|scissor|bat|gunshot|firearm|stabbing)\b', flags=re.I)
VIOLENCE_WORDS = re.compile(r'\b(assault|stabbed|shot|beaten|killed|murder|attack|hurt|injured|violence|attackers|threatened)\b', flags=re.I)
CHILD_WORDS = re.compile(r'\b(child|minor|boy|girl|under\s*\d{1,2})\b', flags=re.I)

KIDNAPPING_KEYWORDS = ["kidnap", "kidnapping", "hostage", "ransom", "detain", "detained", "abduct", "abduction", "held captive", "kept in detention"]

PROPERTY_KEYWORDS = ["steal", "stole", "stolen", "television", "tv", "laptop", "entered", "break", "broke in", "break-in", "break in", "unlocked", "burglary", "house", "dwelling", "home","took","shoplift","snatch","snatching"]

# Cluster map & thresholds (tune these with validation)
CLUSTER_MAP = {
    "property": set(["303(2)","305","304","312","306","308","319","336","318","305"]),
    "violent": set(["100","101","102","103(1)","103(2)","105","109","110","116","117(1)","117(2)","309(2)","310(2)"]),
    "sexual": set(["65(1)","65(2)","67","70(2)","71","74","75","76","77","78"]),
    "kidnapping": set(["137(1)","137(2)","138","140(1)","140(2)","140(3)","140(4)"]),
    "fraud": set(["316(1)","316(2)","318","319","336"])
}
SECTION_TO_CLUSTER = {}
for c, sset in CLUSTER_MAP.items():
    for sid in sset:
        SECTION_TO_CLUSTER[sid] = c

CLUSTER_THRESHOLDS = {
    "default": 0.60,
    "violent": 0.80,
    "sexual": 0.99,
    "murder": 0.85,
    "fraud": 0.60,
    "kidnapping": 0.70
}
RAG_HIT_MIN_SCORE = 0.55
CLUSTER_BOOST_ALPHA = 0.6

NUM_WORD_MAP = {"one":1,"two":2,"three":3,"four":4,"five":5,"six":6,"seven":7,"eight":8,"nine":9,"ten":10}

def _contains_keywords(facts_lower: str, keywords: List[str]) -> bool:
    for kw in keywords:
        if not kw:
            continue
        if kw.lower() in facts_lower:
            return True
    return False

def extract_basic_attrs(text: str) -> Dict[str, Optional[Any]]:
    attrs = {"victim_age": None, "victim_gender": None, "num_offenders": None, "weapon_used": None}
    if not text:
        return attrs
    m = AGE_RE.search(text)
    if m:
        try:
            age = int(m.group(1))
            if 0 < age < 120:
                attrs["victim_age"] = age
        except: pass
    mnum = re.search(r'\b(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\b(?:\s+(?:persons|people|men|women|accused|offenders|perpetrators))', text, flags=re.I)
    if mnum:
        w = mnum.group(1)
        if w.isdigit():
            attrs["num_offenders"] = int(w)
        else:
            attrs["num_offenders"] = NUM_WORD_MAP.get(w.lower())
    if WEAPON_WORDS.search(text):
        attrs["weapon_used"] = True
    low = text.lower()
    if re.search(r'\b(woman|female|she|her|daughter|wife)\b', low):
        attrs["victim_gender"] = "female"
    elif re.search(r'\b(man|male|he|him|his|son|husband)\b', low):
        attrs["victim_gender"] = "male"
    return attrs

def build_meta_map(sections_meta: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    meta_map = {}
    if sections_meta:
        for m in sections_meta:
            sid = str(m.get("id",""))
            # prefer explicit 'text' or 'description' for body; 'title' may be missing
            text_field = m.get("text") or m.get("description") or ""
            meta_map[sid] = {"text": text_field, "keywords": m.get("keywords", []) or [], "title": m.get("title") or (text_field[:80] if text_field else sid)}
    else:
        try:
            from .bns import BNS_SECTION_DETAILS
            for sid, info in BNS_SECTION_DETAILS.items():
                kws = info.get("keywords", []) or []
                meta_map[str(sid)] = {"text": " ".join([info.get("title",""), info.get("description","")]), "keywords": kws, "title": info.get("title")}
        except Exception:
            meta_map = {}
    return meta_map

def _normalize_raw_sections(raw_sections: Any) -> List[tuple]:
    """
    Accept different shapes for raw model 'sections' and return list of (sid, score, evidence)
    raw_sections might be:
      - list of tuples: [(sid, score, evidence), ...]
      - list of dicts: [{"section_id":..., "score":..., "evidence":...}, ...]
      - list of lists similar to tuples
    """
    out = []
    if not raw_sections:
        return out
    for item in raw_sections:
        if isinstance(item, (list, tuple)):
            if len(item) >= 2:
                sid = str(item[0])
                score = float(item[1]) if item[1] is not None else 0.0
                evidence = item[2] if len(item) >= 3 else ""
                out.append((sid, score, evidence or ""))
        elif isinstance(item, dict):
            sid = str(item.get("section_id") or item.get("id") or item.get("section") or "")
            try:
                score = float(item.get("score", 0.0))
            except Exception:
                score = 0.0
            evidence = item.get("evidence") or item.get("text") or item.get("description") or ""
            out.append((sid, score, evidence))
        else:
            # unknown type - ignore
            continue
    return out

def post_process_predictions(
    raw_result: Dict[str, Any],
    facts: str,
    sections_meta: Optional[List[Dict[str, Any]]] = None,
    victim_age: Optional[int] = None,
    victim_gender: Optional[str] = None,
    num_offenders: Optional[int] = None,
    weapon_used: Optional[bool] = None,
    min_score: Optional[float] = None
) -> Dict[str, Any]:
    facts = (facts or "").strip()
    facts_lower = facts.lower()
    inferred = extract_basic_attrs(facts)
    victim_age = victim_age or inferred.get("victim_age")
    victim_gender = victim_gender or inferred.get("victim_gender")
    num_offenders = num_offenders or inferred.get("num_offenders")
    inferred_weapon = inferred.get("weapon_used", False)

    # Weapon override logic + metric
    if weapon_used is None:
        weapon_used = inferred_weapon
    else:
        if weapon_used and (NEG_INJURY_PHRASES.search(facts) or NO_WEAPON_PHRASES.search(facts)):
            logger.info("weapon_used overridden False due to explicit 'no injury/no weapon' in facts.")
            inc_metric("weapon_override_count")
            weapon_used = False

    clarifications = []
    if victim_gender is None:
        clarifications.append({"field":"victim_gender","question":"Is the victim male, female, other, or unknown?"})
    if victim_age is None:
        clarifications.append({"field":"victim_age","question":"Approx. age of victim (years)?"})
    if num_offenders is None:
        clarifications.append({"field":"num_offenders","question":"How many offenders (estimate)?"})

    meta_map = build_meta_map(sections_meta)

    # robust retrieval_hits extraction
    raw_retrieval = raw_result.get("raw_retrieval") or {}
    retrieval_hits = []
    if isinstance(raw_retrieval, dict):
        retrieval_hits = raw_retrieval.get("hits", []) or raw_retrieval.get("results", []) or []
    elif isinstance(raw_retrieval, list):
        retrieval_hits = raw_retrieval
    # also accept top-level 'raw_hits'
    retrieval_hits = retrieval_hits or raw_result.get("raw_hits", []) or []

    # build rag score map from retrieval hits
    retrieval_score_map = {}
    for h in retrieval_hits:
        try:
            sid = str(h.get("section_id") or h.get("id") or "")
            score = float(h.get("score", 0.0))
            retrieval_score_map[sid] = max(retrieval_score_map.get(sid, 0.0), score)
        except Exception:
            continue

    property_indicator = _contains_keywords(facts_lower, PROPERTY_KEYWORDS)

    candidates = []
    # normalize raw model sections to list of tuples (sid, score, evidence)
    raw_sections = _normalize_raw_sections(raw_result.get("sections", []))

    for sid, score, evidence in raw_sections:
        try:
            sc = float(score)
        except:
            continue
        global_min = min_score if min_score is not None else CLUSTER_THRESHOLDS["default"]
        rag_score = retrieval_score_map.get(sid, 0.0)

        # RAG + score guard
        if rag_score < RAG_HIT_MIN_SCORE and sc < (global_min + 0.15):
            logger.debug(f"Dropping {sid} because rag_score {rag_score} < {RAG_HIT_MIN_SCORE} and model sc {sc} < {global_min + 0.15}")
            continue

        meta = meta_map.get(sid, {})
        kw_list = meta.get("keywords", []) if meta else []
        if kw_list and rag_score < 0.7 and not _contains_keywords(facts_lower, kw_list):
            logger.debug(f"Dropping {sid} due to keywords mismatch and low rag_score.")
            continue

        cluster = SECTION_TO_CLUSTER.get(sid, "default")

        # property vs kidnapping guard
        if property_indicator and cluster == "kidnapping":
            if not _contains_keywords(facts_lower, KIDNAPPING_KEYWORDS):
                if sc < 0.95 and rag_score < 0.9:
                    inc_metric("kidnap_blocked_by_property")
                    logger.debug(f"Blocking kidnapping {sid} due to property indicator and lack of kidnapping tokens.")
                    continue

        # violent cluster rules
        if cluster == "violent":
            is_murder_section = sid in ("100","101","102")
            if is_murder_section:
                if sc < CLUSTER_THRESHOLDS["murder"]:
                    inc_metric("murder_dropped_by_threshold")
                    continue
                if not (VIOLENCE_WORDS.search(facts) or weapon_used or ("dead" in facts_lower or "died" in facts_lower)):
                    inc_metric("murder_dropped_no_violence")
                    continue
            else:
                if sc < CLUSTER_THRESHOLDS["violent"]:
                    inc_metric("violent_dropped_by_threshold")
                    continue

        # sexual cluster rules
        if cluster == "sexual":
            needs_child = bool(CHILD_WORDS.search(meta.get("text","") or "")) or False
            if needs_child and (victim_age is None or victim_age >= 18):
                inc_metric("sexual_child_dropped")
                continue
            if "woman" in (meta.get("text","") or "").lower() or "female" in (meta.get("text","") or "").lower():
                if victim_gender is None:
                    inc_metric("sexual_dropped_gender_unknown")
                    continue
                if victim_gender.lower() not in ("female","woman","f"):
                    inc_metric("sexual_dropped_gender_mismatch")
                    continue
            if sc < 0.90 and not VIOLENCE_WORDS.search(facts):
                inc_metric("sexual_dropped_low_score")
                continue

        if cluster == "property":
            if sc < CLUSTER_THRESHOLDS["default"]:
                continue

        if cluster == "kidnapping":
            if sc < CLUSTER_THRESHOLDS["kidnapping"]:
                continue

        # weapon meta check
        meta_text = (meta.get("text","") or "").lower()
        if ("weapon" in meta_text or "knife" in meta_text or "gun" in meta_text) and not weapon_used and NO_WEAPON_PHRASES.search(facts):
            inc_metric("weapon_meta_blocked")
            continue

        candidates.append({"section_id": sid, "score": sc, "evidence": evidence, "cluster": cluster, "rag_score": rag_score, "meta_keywords": kw_list})

    # If nothing survived -> fallback to retrieval hits (BNS shape)
    if not candidates:
        fallback = []
        top_hits = retrieval_hits[:10] if isinstance(retrieval_hits, list) else []
        for h in top_hits:
            sid = str(h.get("section_id") or h.get("id") or "")
            meaning = h.get("text", "") or h.get("description", "") or ""
            name = None

            # prefer sections_meta if provided (description -> title fallback)
            if sections_meta:
                for m in sections_meta:
                    if str(m.get("id")) == sid:
                        name = m.get("title") or (m.get("text", "")[:80]) or (m.get("description","")[:80])
                        meaning = (m.get("text", "") or m.get("description",""))[:400]
                        break

            # fall back to app.bns if available for friendly title/description
            try:
                from .bns import BNS_SECTION_DETAILS
                info = BNS_SECTION_DETAILS.get(sid, {})
                name = name or info.get("title")
                meaning = meaning or info.get("description") or info.get("title","")
            except Exception:
                pass

            fallback.append({"section_id": sid or "unknown", "name": name or sid or "unknown", "meaning": meaning or ""})

        crime_type_val = raw_result.get("crime_type", "unknown")
        if crime_type_val is None or str(crime_type_val).strip() == "":
            crime_type_val = "unknown"
        logger.info("postprocess: no candidates -> returning fallback top retrieval hits count=%d", len(fallback))
        return {"bns": fallback, "crime_type": crime_type_val, "clarifications": clarifications}

    # cluster stats
    cluster_scores = {}; cluster_counts = {}
    for c in candidates:
        cl = c["cluster"]; cluster_scores.setdefault(cl, 0.0); cluster_counts.setdefault(cl, 0); cluster_scores[cl]+=c["score"]; cluster_counts[cl]+=1
    cluster_mean = {cl: (cluster_scores[cl]/cluster_counts[cl]) for cl in cluster_scores}
    global_mean = sum([c["score"] for c in candidates]) / len(candidates)

    boosted_candidates = []
    for c in candidates:
        cl = c["cluster"]; cm = cluster_mean.get(cl, global_mean)
        cluster_delta = (cm - global_mean) / (global_mean + 1e-8)
        boost = 1.0 + CLUSTER_BOOST_ALPHA * cluster_delta
        boost = max(0.6, min(1.6, boost))
        new_score = c["score"] * boost

        # property-priority damping
        if property_indicator and cl != "property":
            if new_score < 0.95 and c["rag_score"] < 0.9:
                inc_metric("non_property_damped_by_property")
                new_score = new_score * 0.4

        if c.get("meta_keywords") and _contains_keywords(facts_lower, c["meta_keywords"]):
            new_score = min(0.9999, new_score + 0.03)

        new_score = float(max(0.0, min(0.9999, new_score)))
        boosted_candidates.append({**c, "boosted_score": new_score})

    # final pruning
    final = []
    for c in boosted_candidates:
        sid = c["section_id"]; bsc = c["boosted_score"]; cl = c["cluster"]
        if cl == "violent":
            if bsc < CLUSTER_THRESHOLDS["violent"]:
                inc_metric("violent_final_pruned")
                continue
        elif cl == "sexual":
            if bsc < 0.90:
                inc_metric("sexual_final_pruned")
                continue
        elif cl == "kidnapping":
            if bsc < CLUSTER_THRESHOLDS["kidnapping"]:
                inc_metric("kidnapping_final_pruned")
                continue
        else:
            if bsc < CLUSTER_THRESHOLDS["default"]:
                inc_metric("default_final_pruned")
                continue

        if c["rag_score"] < RAG_HIT_MIN_SCORE and not _contains_keywords(facts_lower, c.get("meta_keywords", [])):
            if c["boosted_score"] < 0.95:
                inc_metric("pruned_low_rag_and_no_kw")
                continue

        final.append({"section_id": sid, "score": round(c["boosted_score"], 6), "evidence": c.get("evidence",""), "cluster": cl})

    dedup = []
    seen = set()
    for s in sorted(final, key=lambda x: -x["score"]):
        if s["section_id"] in seen: continue
        seen.add(s["section_id"])
        dedup.append({"section_id": s["section_id"], "score": s["score"], "evidence": s["evidence"]})

    if not dedup:
        prop_candidates = [c for c in boosted_candidates if c["cluster"]=="property"]
        prop_sorted = sorted(prop_candidates, key=lambda x: -x["boosted_score"])[:5]
        dedup = [{"section_id": c["section_id"], "score": round(c["boosted_score"],6), "evidence": c.get("evidence","")} for c in prop_sorted]

    # convert dedup into BNS-shaped output (include title/description lookup)
    bns_out = []
    for s in dedup:
        sid = str(s["section_id"])
        name = None
        meaning = s.get("evidence", "") or ""
        if sections_meta:
            for meta in sections_meta:
                if str(meta.get("id")) == sid:
                    name = meta.get("title") or (meta.get("text","")[:80]) or (meta.get("description","")[:80])
                    meaning = (meta.get("text","") or meta.get("description",""))[:400]
                    break
        try:
            from .bns import BNS_SECTION_DETAILS
            info = BNS_SECTION_DETAILS.get(sid, {})
            name = name or info.get("title")
            meaning = meaning or info.get("description") or info.get("title","")
        except Exception:
            pass
        bns_out.append({"section_id": sid, "name": name or sid, "meaning": meaning or ""})

    crime_type_val = raw_result.get("crime_type", "unknown")
    if crime_type_val is None or str(crime_type_val).strip() == "":
        crime_type_val = "unknown"

    logger.info("postprocess: returning %d bns entries; crime_type=%s", len(bns_out), str(crime_type_val))
    return {"bns": bns_out, "crime_type": crime_type_val, "clarifications": clarifications}
