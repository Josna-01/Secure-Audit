# app/multilabel_classifier.py
"""
Multi-Label BNS Legal Classification & Explainability Engine.
Performs full-narrative discourse analysis, dense semantic RAG matching,
statutory element verification, independent multi-label scoring,
and natural language XAI explanation generation.
"""

import os
import re
import logging
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import torch
from sentence_transformers import SentenceTransformer

from .bns import BNS_SECTION_DETAILS

logger = logging.getLogger("bns-multilabel-classifier")
logger.setLevel(logging.INFO)

# Sentence splitting regex respecting common abbreviations
SENTENCE_SPLIT_REGEX = re.compile(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?|\!|\n)\s+')

# Category classification mapping
CRIME_CATEGORIES = {
    "100": "Offences Affecting Life (Homicide/Murder)",
    "101": "Offences Affecting Life (Homicide/Murder)",
    "102": "Offences Affecting Life (Homicide/Murder)",
    "103(1)": "Offences Affecting Life (Homicide/Murder)",
    "103(2)": "Offences Affecting Life (Mob Lynching)",
    "104": "Offences Affecting Life (Homicide/Murder)",
    "105": "Offences Affecting Life (Culpable Homicide)",
    "106(1)": "Offences Affecting Life (Negligence/Rash Act)",
    "107": "Offences Affecting Life (Abetment of Suicide)",
    "108": "Offences Affecting Life (Abetment of Suicide)",
    "109": "Inchoate Offences (Attempt to Murder)",
    "110": "Inchoate Offences (Attempt to Culpable Homicide)",
    "111": "Organized Crime",
    "112": "Petty Organized Crime",
    "113": "Terrorist Acts",
    "114": "Offences Affecting the Body (Hurt)",
    "115(1)": "Offences Affecting the Body (Hurt)",
    "115(2)": "Offences Affecting the Body (Voluntarily Causing Hurt)",
    "116": "Offences Affecting the Body (Grievous Hurt)",
    "117(1)": "Offences Affecting the Body (Grievous Hurt)",
    "117(2)": "Offences Affecting the Body (Grievous Hurt)",
    "117(3)": "Offences Affecting the Body (Grievous Hurt)",
    "117(4)": "Offences Affecting the Body (Grievous Hurt by Mob)",
    "118(1)": "Offences Affecting the Body (Hurt with Dangerous Weapons)",
    "118(2)": "Offences Affecting the Body (Grievous Hurt with Weapons)",
    "124(1)": "Offences Affecting the Body (Acid Attack)",
    "124(2)": "Offences Affecting the Body (Attempted Acid Attack)",
    "125": "Offences Affecting Life or Personal Safety",
    "63": "Offences Against Women & Children (Sexual Offences)",
    "64": "Offences Against Women & Children (Rape)",
    "65(1)": "Offences Against Women & Children (Rape on Minor)",
    "65(2)": "Offences Against Women & Children (Rape on Child)",
    "66": "Offences Against Women & Children (Punishment for Rape)",
    "67": "Offences Against Women & Children (Gang Rape)",
    "68": "Offences Against Women & Children (Gang Rape)",
    "69": "Offences Against Women (Deceitful Promise)",
    "70(1)": "Offences Against Women (Gang Rape)",
    "70(2)": "Offences Against Women (Gang Rape of Minor)",
    "71": "Offences Against Women (Repeat Offence)",
    "74": "Offences Against Women (Outraging Modesty)",
    "75": "Offences Against Women (Sexual Harassment)",
    "76": "Offences Against Women (Assault with Intent to Disrobe)",
    "77": "Offences Against Women (Voyeurism)",
    "78": "Offences Against Women (Stalking)",
    "79": "Offences Against Women (Word/Gesture Insulting Modesty)",
    "80": "Offences Against Women (Dowry Death)",
    "85": "Offences Against Women (Cruelty by Husband/Relatives)",
    "86": "Offences Against Women (Cruelty Definition)",
    "137(1)": "Offences Against Personal Liberty (Kidnapping)",
    "137(1)(b)": "Offences Against Personal Liberty (Kidnapping Minor)",
    "137(2)": "Offences Against Personal Liberty (Kidnapping from India)",
    "138": "Offences Against Personal Liberty (Abduction)",
    "139": "Offences Against Personal Liberty (Kidnapping for Begging)",
    "140(1)": "Offences Against Personal Liberty (Kidnapping with Murder Intent)",
    "140(2)": "Offences Against Personal Liberty (Kidnapping for Ransom)",
    "140(3)": "Offences Against Personal Liberty (Wrongful Confinement)",
    "140(4)": "Offences Against Personal Liberty (Kidnapping for Grievous Hurt)",
    "143": "Human Trafficking",
    "144": "Exploitation of Trafficked Person",
    "303(2)": "Offences Against Property (Theft / Snatching)",
    "304": "Offences Against Property (Theft by Clerk/Servant)",
    "305": "Offences Against Property (Theft in Dwelling House)",
    "306": "Offences Against Property (Robbery)",
    "308": "Offences Against Property (Extortion)",
    "309": "Offences Against Property (Extortion by Threat of Death)",
    "309(2)": "Offences Against Property (Robbery with Grievous Hurt)",
    "310(2)": "Offences Against Property (Dacoity)",
    "311": "Offences Against Property (Preparation for Dacoity)",
    "312": "Offences Against Property (Belonging to Gang of Dacoits)",
    "316(1)": "Offences Against Property (Criminal Breach of Trust)",
    "316(2)": "Offences Against Property (Punishment for CBT)",
    "318": "Offences Against Property (Cheating / Fraud)",
    "318(4)": "Offences Against Property (Cyber & Financial Fraud)",
    "319": "Offences Against Property (Cheating by Personation)",
    "324": "Offences Against Property (Mischief / Damage)",
    "324(2)": "Offences Against Property (Mischief Causing Loss)",
    "324(4)": "Offences Against Property (Mischief by Fire / Arson)",
    "324(5)": "Offences Against Property (Mischief to Public Property)",
    "329(1)": "Offences Against Property (Criminal Trespass)",
    "329(3)": "Offences Against Property (House-Trespass)",
    "331(1)": "Offences Against Property (House-Breaking)",
    "336": "Offences Relating to Documents (Forgery)",
    "338": "Offences Relating to Documents (Forgery of Valuable Security)",
    "340": "Offences Relating to Documents (Forged Electronic Record)",
    "351": "Criminal Intimidation & Insult (Threats)",
    "352": "Criminal Intimidation & Insult (Breach of Peace)",
    "189(1)": "Offences Against Public Tranquillity (Unlawful Assembly)",
    "189(2)": "Offences Against Public Tranquillity (Rioting)",
    "190": "Offences Against Public Tranquillity (Common Object in Assembly)",
    "191(1)": "Offences Against Public Tranquillity (Armed Rioting)",
    "281": "Offences Affecting Public Safety (Rash Driving)",
    "3(5)": "General Exceptions & Joint Liability (Common Intention)",
    "61(1)": "Conspiracy (Criminal Conspiracy Definition)",
    "61(2)": "Conspiracy (Punishment for Criminal Conspiracy)",
    "45": "Abetment (Abetment of Offence)",
    "49": "Abetment (Punishment for Abetment)"
}

class MultiLabelBNSClassifier:
    """
    Intelligent multi-label BNS classification engine.
    Reads complete FIR narrative, evaluates statutory definitions across multiple legal dimensions,
    and returns all applicable BNS sections with calibrated confidence scores and explainable rationale.
    """

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2", device: Optional[str] = None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"Initializing MultiLabelBNSClassifier with {model_name} on {self.device}")
        
        self.encoder = SentenceTransformer(model_name, device=self.device)
        self.sections_dict = BNS_SECTION_DETAILS
        self.section_keys = list(self.sections_dict.keys())
        
        # Build comprehensive statutory corpus text for each section
        self.section_texts = []
        for sid in self.section_keys:
            info = self.sections_dict[sid]
            title = info.get("title", "")
            desc = info.get("description", "")
            elements = " ".join(info.get("legal_elements", []))
            keywords = " ".join(info.get("keywords", []))
            combined = f"{title}. {desc}. Elements: {elements}. Keywords: {keywords}"
            self.section_texts.append(combined)

        # Precompute section embeddings
        logger.info(f"Pre-encoding {len(self.section_texts)} BNS section statutory profiles...")
        self.section_embeddings = self.encoder.encode(
            self.section_texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False
        )
        logger.info("Statutory profile embeddings precomputed successfully.")

    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into clean, non-empty sentences."""
        if not text:
            return []
        raw_sentences = SENTENCE_SPLIT_REGEX.split(text.strip())
        cleaned = []
        for s in raw_sentences:
            s_clean = s.strip()
            if "\n" in s_clean:
                lines = [l.strip() for l in s_clean.split("\n") if l.strip()]
                cleaned.extend(lines)
            elif len(s_clean) > 5:
                cleaned.append(s_clean)
        return cleaned if cleaned else [text.strip()]

    def _match_legal_elements(self, facts: str, section_id: str) -> Tuple[float, List[str], List[str]]:
        """
        Evaluate statutory elements, actus reus, and key legal markers for a given section.
        Returns: (element_score, matched_keywords, triggering_reasons)
        """
        facts_lower = facts.lower()
        info = self.sections_dict.get(section_id, {})
        keywords = info.get("keywords", [])
        
        matched_kw = [kw for kw in keywords if kw and kw.lower() in facts_lower]
        
        element_matches = 0
        triggering_reasons = []

        # Count accused numbers
        has_mob_size = bool(re.search(r'\b(five|six|seven|eight|nine|ten|[5-9]|\d{2,})\s*(persons|people|men|women|accused|attackers|assailants|rioters|members|individuals)\b', facts_lower))
        has_multiple_accused = bool(re.search(r'\b(two|three|four|five|six|seven|eight|nine|ten|[2-9]|\d{2,})\s*(persons|people|men|women|accused|attackers|assailants|rioters|members|individuals)\b', facts_lower)) or bool(re.search(r'\b(multiple accused|co-accused|accomplices|acting in concert|jointly|together|along with (his|her|their) associates|two bike-borne|three bike-borne)\b', facts_lower))
        
        # 1. Joint Liability / Common Intention (3(5)) & Conspiracy (61)
        if section_id == "3(5)":
            if has_multiple_accused or len(matched_kw) >= 1:
                element_matches += 3
                triggering_reasons.append("FIR documents multiple accused persons acting jointly in furtherance of common intention")
            else:
                return 0.0, [], []
        elif section_id.startswith("61"):
            conspiracy_match = bool(re.search(r'\b(conspiracy|conspired|secret agreement|hatched a conspiracy|planned jointly|plotted)\b', facts_lower))
            if conspiracy_match or len(matched_kw) >= 1:
                element_matches += 3
                triggering_reasons.append("FIR records criminal conspiracy and advance agreement to commit an offence")

        # 2. Criminal Intimidation & Insult (351, 352)
        elif section_id == "351":
            threat_match = bool(re.search(
                r'\b(threat|threaten|threatened|threatening|kill you|shoot you|finish you|dire consequences|warned him|put in fear|intimidation|menacing|brandishing weapon|threat of death|threat to kill|threat of arrest)\b',
                facts_lower
            ))
            if threat_match or len(matched_kw) >= 1:
                element_matches += 3
                triggering_reasons.append("FIR contains explicit verbal or physical threats of injury, death, or harm")
        elif section_id == "352":
            insult_match = bool(re.search(r'\b(insult|abusive insults|provoke a fight|provoke breach of peace|hurled abuses|foul language to provoke)\b', facts_lower))
            if insult_match or len(matched_kw) >= 1:
                element_matches += 3
                triggering_reasons.append("Intentional insult intended or known to be likely to provoke breach of the peace")

        # 3. Mischief / Property Damage (324, 324(2), 324(4), 324(5))
        elif section_id.startswith("324"):
            is_arson = section_id == "324(4)"
            is_public_prop = section_id == "324(5)"
            
            arson_match = bool(re.search(r'\b(fire|arson|set fire|set on fire|burnt|burned|burning|petrol bomb|poured petrol|inflammable|explosive)\b', facts_lower))
            public_prop_match = bool(re.search(r'\b(public property|bus|train|station|road|bridge|electricity|telecom|government property|infrastructure|police vehicle|public bus)\b', facts_lower))
            damage_match = bool(re.search(
                r'\b(damage|damaged|destroy|destroyed|destruction|vandalism|vandalized|smashed|broke|broken|breakage|ruined|shattered|crushed|loss to property|damaged vehicle|smashed windows|destroy the standing|poured petrol)\b',
                facts_lower
            ))
            
            if is_arson:
                if arson_match:
                    element_matches += 4
                    triggering_reasons.append("FIR reports property destruction by fire or explosive substance (arson)")
                else:
                    return 0.0, [], []
            elif is_public_prop:
                if public_prop_match and damage_match:
                    element_matches += 4
                    triggering_reasons.append("FIR reports damage inflicted upon public property or essential infrastructure")
                elif not damage_match:
                    return 0.0, [], []
            else:
                if damage_match or arson_match or len(matched_kw) >= 1:
                    element_matches += 3
                    triggering_reasons.append("FIR details intentional damage, vandalism, or destruction of property")

        # 4. Voluntarily Causing Hurt / Grievous Hurt / Weapons (114, 115, 116, 117, 118)
        elif section_id in ("114", "115(1)", "115(2)", "116", "117(1)", "117(2)", "117(3)", "117(4)", "118(1)", "118(2)"):
            hurt_match = bool(re.search(
                r'\b(beat|beaten|assault|assaulted|struck|hit|punched|kicked|injury|injuries|bleeding|fracture|wound|hospital|attacked|inflicted pain|abrasive injuries|hematoma|black eyes)\b',
                facts_lower
            ))
            weapon_match = bool(re.search(
                r'\b(iron rod|knife|dagger|sword|lathi|stick|wooden stick|firearm|gun|pistol|sharp weapon|bludgeon|machete|heavy object|blunt weapon|heavy stone)\b',
                facts_lower
            ))
            is_weapon_sec = section_id.startswith("118")
            is_grievous = section_id.startswith("117")

            if is_weapon_sec:
                if (hurt_match or "assault" in facts_lower) and weapon_match:
                    element_matches += 4
                    triggering_reasons.append("FIR reports physical assault executed using dangerous or lethal weapons")
                elif not weapon_match:
                    return 0.0, [], []
            elif is_grievous:
                grievous_words = bool(re.search(r'\b(fracture|grievous|severe|hospitalized|icu|head injury|broken bone|permanent damage|deep cut|stab wound|skull fracture)\b', facts_lower))
                if hurt_match and (grievous_words or weapon_match):
                    element_matches += 3
                    triggering_reasons.append("FIR reports serious/grievous bodily injury or medical hospitalization")
            else:
                if hurt_match:
                    element_matches += 3
                    triggering_reasons.append("FIR describes physical assault resulting in bodily hurt and pain")

        # 5. Acid Attack (124(1), 124(2))
        elif section_id in ("124(1)", "124(2)"):
            acid_match = bool(re.search(r'\b(acid|corrosive substance|chemical burn|disfigurement|threw corrosive|acid-attack|bottle of acid)\b', facts_lower))
            if acid_match:
                element_matches += 4
                triggering_reasons.append("FIR reports acid attack or attempt to throw corrosive substance causing injury/disfigurement")
            else:
                return 0.0, [], []

        # 6. Theft / Snatching / Robbery / Dacoity (303(2), 304, 305, 306, 309(2), 310(2), 112)
        elif section_id in ("303(2)", "304", "305", "306", "309(2)", "310(2)", "111", "112"):
            theft_part = bool(re.search(r'\b(stole|stolen|theft|took away|snatched|snatching|snatch|robbed|robbery|looted|demanded money|extorted|cash|jewellery|gold|purse|mobile|wallet|pickpocket|pickpockets|slitting bags)\b', facts_lower))
            force_part = bool(re.search(r'\b(force|violence|weapon|knife|gun|assault|beat|threatened|fear of death|held at gunpoint|injured|pushed|fell on the road|gunpoint)\b', facts_lower))
            
            if section_id == "310(2)":
                if theft_part and force_part and has_mob_size:
                    element_matches += 4
                    triggering_reasons.append("Dacoity: robbery committed jointly by five or more persons")
                else:
                    return 0.0, [], []
            elif section_id in ("306", "309(2)"):
                if theft_part and force_part:
                    element_matches += 4
                    triggering_reasons.append("Robbery: theft or extortion committed with voluntary infliction of hurt or instant fear of violence")
                else:
                    return 0.0, [], []
            elif section_id in ("111", "112"):
                syndicate_match = bool(re.search(r'\b(organized|syndicate|gang of pickpockets|continuing unlawful activity|organized theft)\b', facts_lower))
                if syndicate_match and theft_part:
                    element_matches += 3
                    triggering_reasons.append("Petty organized crime: continuous theft/snatching executed by organized syndicate")
                else:
                    return 0.0, [], []
            else:
                if theft_part:
                    element_matches += 3
                    triggering_reasons.append("Theft / Snatching: dishonest taking of movable property without consent")

        # 7. Extortion (308, 309)
        elif section_id in ("308", "309"):
            extortion_match = bool(re.search(r'\b(extortion|extort|extortionists|extortion money|demanded ransom|demanded protection money|threatened to harm unless|hafta|protection fee|forced to sign|forced to pay|forced under threat of instant death|sign blank cheques)\b', facts_lower))
            if extortion_match or len(matched_kw) >= 1:
                element_matches += 4
                triggering_reasons.append("Perpetrators intentionally put victim in fear of injury to dishonestly extract money, property, or valuable security")

        # 8. House-Trespass & House-Breaking & Criminal Trespass (329(1), 329(3), 331(1), 305)
        elif section_id in ("329(1)", "329(3)", "331(1)", "305"):
            trespass_match = bool(re.search(r'\b(broke open|broke lock|broke into|forced entry|entered house|entered residence|trespassed|trespassing|entered.*private|entered.*without authorization|shattered door|climbed wall|night break-in|dwelling)\b', facts_lower))
            if trespass_match or len(matched_kw) >= 1:
                element_matches += 3
                triggering_reasons.append("Unlawful forced entry, house-breaking, or criminal trespass into property")

        # 9. Rioting / Unlawful Assembly (189(1), 189(2), 190, 191(1))
        elif section_id.startswith("189") or section_id in ("190", "191(1)"):
            mob_match = bool(re.search(r'\b(mob|riot|rioting|violent crowd|clash|stone pelting|unlawful assembly|vandalizing crowd|armed mob|over twenty persons)\b', facts_lower))
            if mob_match or len(matched_kw) >= 1:
                element_matches += 3
                triggering_reasons.append("Offence committed by a violent assembly or mob of five or more persons with common object")
            else:
                return 0.0, [], []

        # 10. Murder / Attempt to Murder / Homicide (100, 101, 102, 103(1), 103(2), 105, 109, 110)
        elif section_id in ("100", "101", "102", "103(1)", "103(2)", "105", "109", "110"):
            is_lynching = section_id == "103(2)"
            is_attempt = section_id in ("109", "110")
            is_actual_murder = section_id in ("100", "101", "102", "103(1)", "105")

            death_occurred = bool(re.search(r'\b(dead|death|died|killed|murdered|succumbed to injuries|post-mortem|dead body|fatal wounds|died on the spot)\b', facts_lower))
            attempt_match = bool(re.search(r'\b(attempt to murder|attempted to kill|with intent to commit murder|fired two gunshots|tried to shoot|slit throat|stabbed in chest|tried to kill|fired at him|survived the attack)\b', facts_lower))
            hate_mob = bool(re.search(r'\b(mob lynching|lynched|caste|religion|communal attack|lynch mob|on grounds of his religion)\b', facts_lower))

            if is_lynching:
                if death_occurred and (hate_mob or has_mob_size):
                    element_matches += 4
                    triggering_reasons.append("Mob lynching resulting in death motivated by identity/caste/religion")
                else:
                    return 0.0, [], []
            elif is_attempt:
                if attempt_match:
                    element_matches += 4
                    triggering_reasons.append("Attempt to murder: act executed with knowledge/intention that it would cause death")
                else:
                    return 0.0, [], []
            elif is_actual_murder:
                if death_occurred:
                    element_matches += 4
                    triggering_reasons.append("Culpable homicide amounting to murder resulting in death of the victim")
                else:
                    return 0.0, [], []

        # 11. Cyber & Financial Fraud / Cheating / Forgery / Impersonation (318, 318(4), 319, 336, 338, 340, 316(1), 316(2))
        elif section_id in ("318", "318(4)", "319", "336", "338", "340", "316(1)", "316(2)"):
            fraud_match = bool(re.search(r'\b(cheat|cheated|cheating|fraud|fraudulent|scam|online transaction|fake documents|forged|forgery|phishing|crypto|misappropriated|breach of trust|embezzled|induced to transfer|bogus investment|fraudulently transfer|personated|impersonating|fake police|fake badge|fake uniform)\b', facts_lower))
            is_forgery = section_id in ("336", "338", "340")
            is_impersonation = section_id == "319"
            is_cbt = section_id.startswith("316")

            if is_forgery:
                forgery_words = bool(re.search(r'\b(forged|forgery|fabricated|altered|fake receipts|forged signatures|bogus document|forged will)\b', facts_lower))
                if forgery_words:
                    element_matches += 4
                    triggering_reasons.append("Forgery: making or altering false documents, valuable security, or electronic records")
                else:
                    return 0.0, [], []
            elif is_impersonation:
                impers_words = bool(re.search(r'\b(personated|impersonating|impersonated|pretended to be|fake officer|fake police|false identity)\b', facts_lower))
                if impers_words or fraud_match:
                    element_matches += 3
                    triggering_reasons.append("Cheating by personation: pretending to be someone else or representing a false character")
            elif is_cbt:
                cbt_words = bool(re.search(r'\b(entrusted|breach of trust|misappropriated|diverting corporate funds|accountant|employee)\b', facts_lower))
                if cbt_words:
                    element_matches += 4
                    triggering_reasons.append("Criminal breach of trust: dishonest misappropriation of property entrusted to perpetrator")
            else:
                if fraud_match or len(matched_kw) >= 1:
                    element_matches += 3
                    triggering_reasons.append("Cheating and dishonest inducement to deliver property or money")

        # 12. Domestic Cruelty / Dowry / Suicide Abetment (80, 85, 86, 107, 108, 45, 49)
        elif section_id in ("80", "85", "86", "107", "108", "45", "49"):
            domestic_match = bool(re.search(r'\b(husband|in-laws|mother-in-law|father-in-law|dowry|matrimonial home|cruelty|harassment for dowry|domestic abuse|tortured by husband)\b', facts_lower))
            suicide_match = bool(re.search(r'\b(suicide|commit suicide|hanged|hanging|suicide note|instigation|abetted suicide|driven to suicide)\b', facts_lower))
            is_suicide = section_id in ("107", "108", "45", "49")
            is_dowry_death = section_id == "80"

            if is_dowry_death:
                dowry_death_match = bool(re.search(r'\b(died under abnormal|burn circumstances|dowry death|within.*years of marriage)\b', facts_lower))
                if dowry_death_match and domestic_match:
                    element_matches += 4
                    triggering_reasons.append("Dowry death: death of woman within seven years of marriage under abnormal circumstances related to dowry harassment")
                else:
                    return 0.0, [], []
            elif is_suicide:
                if suicide_match:
                    element_matches += 4
                    triggering_reasons.append("Abetment of suicide: continuous instigation or aiding that directly drove victim to commit suicide")
                else:
                    return 0.0, [], []
            else:
                if domestic_match:
                    element_matches += 4
                    triggering_reasons.append("Matrimonial cruelty and unlawful harassment of woman by husband or relatives")

        # 13. Offences Against Women & Modesty (64, 69, 74, 75, 76, 77, 78, 79)
        elif section_id in ("64", "69", "74", "75", "76", "77", "78", "79"):
            modesty_match = bool(re.search(r'\b(modesty|stalk|stalked|stalking|followed|vulgar gesture|sexual harassment|sexual favour|obscene|disrobe|false promise to marry|deceitful promise)\b', facts_lower))
            if modesty_match:
                element_matches += 4
                triggering_reasons.append("Offence against women: assault to outrage modesty, stalking, sexual harassment, or deceitful promise")
            else:
                return 0.0, [], []

        # 14. Kidnapping / Abduction / Confinement (137, 138, 140)
        elif section_id.startswith("137") or section_id.startswith("140") or section_id == "138":
            kidnap_match = bool(re.search(r'\b(kidnap|kidnapped|kidnapping|abduct|abducted|abduction|taken away forcibly|hostage|confined|locked.*in.*godown|ransom demand|missing child)\b', facts_lower))
            if kidnap_match or len(matched_kw) >= 1:
                element_matches += 4
                triggering_reasons.append("Forcible abduction, unlawful detention, kidnapping, or wrongful confinement")

        # 15. Rash Driving & Endangering Safety (281, 125)
        elif section_id in ("281", "125"):
            driving_match = bool(re.search(r'\b(rash driving|reckless driving|speeding car|speeding truck|hit and run|over-speeding|rammed into|negligent driving|endanger human life|personal safety)\b', facts_lower))
            if driving_match or len(matched_kw) >= 1:
                element_matches += 4
                triggering_reasons.append("Vehicle operated on public way in a rash or negligent manner endangering human safety")

        # General keyword credit
        kw_ratio = len(matched_kw) / max(1, len(keywords))
        score = min(1.0, (element_matches * 0.25) + (kw_ratio * 0.35))
        
        return score, matched_kw, triggering_reasons

    def _generate_explanation(
        self,
        section_id: str,
        title: str,
        trigger_sentences: List[str],
        matched_kw: List[str],
        reasons: List[str]
    ) -> str:
        """Generate a coherent, human-readable legal explanation from FIR evidence."""
        if reasons:
            main_reason = reasons[0]
        else:
            main_reason = f"the factual narrative strongly satisfies the statutory ingredients of {title}"

        if trigger_sentences:
            best_snippet = trigger_sentences[0].strip().rstrip('.')
            if len(best_snippet) > 120:
                best_snippet = best_snippet[:117] + "..."
            explanation = f"Detected {title} (BNS {section_id}) because {main_reason}. Key evidence: \"{best_snippet}\"."
        else:
            explanation = f"Detected {title} (BNS {section_id}) because {main_reason}."

        if matched_kw:
            top_kws = ", ".join(matched_kw[:4])
            explanation += f" Corroborating legal markers detected: {top_kws}."

        return explanation

    def classify_multilabel(
        self,
        facts: str,
        threshold: float = 0.35,
        top_k: int = 15,
        title: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main multi-label inference method.
        Reads full FIR text, segments sentences, computes dense RAG similarities,
        applies legal element scoring, and ranks all qualifying BNS sections.
        """
        facts = (facts or "").strip()
        if not facts or len(facts) < 10:
            return {
                "bns": [],
                "crime_type": "Unknown",
                "crime_categories": [],
                "total_sections": 0,
                "threshold_applied": threshold
            }

        sentences = self._split_into_sentences(facts)
        
        # 1. Encode full document & sentences
        doc_embedding = self.encoder.encode([facts], convert_to_numpy=True, normalize_embeddings=True)[0]
        sent_embeddings = self.encoder.encode(sentences, convert_to_numpy=True, normalize_embeddings=True)

        # 2. Dense similarity matrices
        doc_sims = np.dot(self.section_embeddings, doc_embedding)
        sent_sims = np.dot(sent_embeddings, self.section_embeddings.T)

        predictions = []
        detected_categories = set()

        for idx, sid in enumerate(self.section_keys):
            info = self.sections_dict[sid]
            sec_title = info.get("title", f"Section {sid}")
            sec_desc = info.get("description", "")
            sec_severity = info.get("severity", "medium")
            sec_cognizable = info.get("cognizable", True)
            sec_bailable = info.get("bailable", True)
            sec_punishment = info.get("punishment", {})
            sec_elements = info.get("legal_elements", [])

            # Semantic similarities
            d_sim = float(doc_sims[idx])
            s_sims = sent_sims[:, idx]
            max_s_sim = float(np.max(s_sims)) if len(s_sims) > 0 else 0.0
            
            # Find triggering sentences (top 2 highest matching sentences)
            top_sent_indices = np.argsort(-s_sims)[:2]
            trigger_sentences = [sentences[i] for i in top_sent_indices if s_sims[i] >= 0.15]

            # Statutory element matching
            element_score, matched_kw, reasons = self._match_legal_elements(facts, sid)

            # Strict guard: if element_score is 0 for sections requiring specific physical elements
            if element_score <= 0.0 and not matched_kw:
                continue

            # Combined multi-factor calibrated confidence score
            # Formula: 0.40 * MaxSentenceSim + 0.25 * DocSim + 0.35 * ElementScore + bonus
            raw_score = (0.40 * max_s_sim) + (0.25 * d_sim) + (0.35 * element_score)
            
            if reasons:
                raw_score += 0.15
            elif matched_kw:
                raw_score += min(0.10, len(matched_kw) * 0.03)

            # Map to calibrated confidence [0.0, 0.99]
            calibrated_score = float(1.0 / (1.0 + np.exp(-7.0 * (raw_score - 0.40))))
            calibrated_score = round(max(0.01, min(0.99, calibrated_score)), 4)

            # Check threshold
            if calibrated_score >= threshold:
                explanation = self._generate_explanation(sid, sec_title, trigger_sentences, matched_kw, reasons)
                category = CRIME_CATEGORIES.get(sid, info.get("crime", "General Offence"))
                detected_categories.add(category)

                punishment_str = ""
                if isinstance(sec_punishment, dict):
                    p_min = sec_punishment.get("min", "")
                    p_max = sec_punishment.get("max", "")
                    p_fine = sec_punishment.get("fine", "")
                    punishment_str = f"Min: {p_min}, Max: {p_max} ({p_fine})".strip()

                predictions.append({
                    "section_id": sid,
                    "title": sec_title,
                    "name": sec_title,
                    "confidence": calibrated_score,
                    "confidence_percent": f"{round(calibrated_score * 100)}%",
                    "score": calibrated_score,
                    "severity": sec_severity,
                    "cognizable": sec_cognizable,
                    "bailable": sec_bailable,
                    "category": category,
                    "description": sec_desc,
                    "meaning": sec_desc,
                    "legal_elements": sec_elements,
                    "punishment": punishment_str or sec_punishment,
                    "explanation": explanation,
                    "trigger_sentences": trigger_sentences if trigger_sentences else [facts[:200]],
                    "matched_keywords": matched_kw
                })

        # Sort all predictions by confidence descending
        predictions.sort(key=lambda x: x["confidence"], reverse=True)

        # Truncate to top_k
        final_predictions = predictions[:top_k]

        # Primary crime type summary
        primary_crime_type = "Multi-Offence Incident"
        if final_predictions:
            primary_crime_type = final_predictions[0]["category"]

        return {
            "bns": final_predictions,
            "sections": final_predictions,
            "crime_type": primary_crime_type,
            "crime_categories": list(detected_categories),
            "total_sections": len(final_predictions),
            "threshold_applied": threshold
        }
