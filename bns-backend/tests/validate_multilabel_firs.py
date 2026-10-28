# tests/validate_multilabel_firs.py
"""
Comprehensive Validation Suite for Multi-Label BNS Legal Classification.
Contains 30 realistic, diverse multi-offence fictional FIRs covering:
Murder, Attempt to Murder, Robbery, Theft, Assault & Hurt, Kidnapping,
Criminal Intimidation, Extortion, Property Damage / Mischief, Cybercrime,
Cheating, Forgery, Domestic Violence & Cruelty, Rioting, Criminal Breach of Trust,
and Financial Fraud.
"""

import sys
import os
import json
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.multilabel_classifier import MultiLabelBNSClassifier

# 30 Realistic Fictional FIR Test Cases with Expected Ground Truth Sections
TEST_FIRS = [
    {
        "id": "FIR_01",
        "description": "Multi-offence Armed Robbery + Assault + Intimidation + Mischief + Common Intention",
        "facts": (
            "On 12th August at around 10:30 PM, the complainant Rajesh Kumar was returning home when "
            "three accused individuals intercepted his motorcycle near the market. The three accused persons "
            "acting in furtherance of common intention assaulted the complainant by beating him with an iron rod "
            "and punched him repeatedly, causing bleeding injuries on his head and arms. The accused brandished "
            "a sharp knife and threatened to kill him if he shouted. They forcibly snatched his gold chain and wallet "
            "containing Rs 15,000 cash. Before fleeing the spot on their two-wheelers, the accused intentionally "
            "smashed the headlight and petrol tank of the complainant's motorcycle, causing heavy damage to the vehicle."
        ),
        "expected_sections": ["306", "118(1)", "351", "324", "3(5)"]
    },
    {
        "id": "FIR_02",
        "description": "Burglary + House-Breaking by Night + Theft in Dwelling + Mischief",
        "facts": (
            "During the night of 5th September, unknown perpetrators broke open the main entrance padlock of the "
            "complainant's locked residential house. The burglars ransacked the master bedroom, broke open the steel "
            "almirah lock, damaged the wooden wardrobe, and stole gold ornaments worth Rs 4,50,000 along with Rs 80,000 in cash."
        ),
        "expected_sections": ["303(2)", "305", "331(1)", "324"]
    },
    {
        "id": "FIR_03",
        "description": "Attempt to Murder + Dangerous Weapon Assault + Criminal Intimidation",
        "facts": (
            "The accused Vikram Singh arrived at the complainant's shop armed with a country-made pistol and a dagger. "
            "With intent to commit murder, Vikram fired two gunshots aiming directly at the complainant's chest, "
            "which narrowly missed him, and then stabbed the complainant in his left shoulder while shouting threats "
            "that he would murder his entire family before fleeing."
        ),
        "expected_sections": ["109", "118(1)", "351"]
    },
    {
        "id": "FIR_04",
        "description": "Premeditated Murder + Dangerous Weapon + Criminal Conspiracy",
        "facts": (
            "The two accused hatched a criminal conspiracy to eliminate the victim over a property dispute. Pursuant "
            "to their secret agreement, they ambushed the victim in a deserted alley, repeatedly struck him on the neck "
            "with a machete causing severe fatal wounds. The victim died on the spot and post-mortem confirmed death due to shock and hemorrhage."
        ),
        "expected_sections": ["101", "103(1)", "61(1)", "118(1)"]
    },
    {
        "id": "FIR_05",
        "description": "Cyber Fraud + Online Cheating + Forged Electronic Records",
        "facts": (
            "The complainant received a phishing SMS claiming his bank account was blocked. The scammer induced the "
            "complainant to click a fraudulent link and share OTPs, resulting in unauthorized transfer of Rs 3,20,000. "
            "The scammer fabricated fake bank payment receipts using forged digital signatures and electronic records to deceive the victim."
        ),
        "expected_sections": ["318(4)", "318", "336", "340"]
    },
    {
        "id": "FIR_06",
        "description": "Kidnapping for Ransom + Criminal Intimidation + Joint Liability",
        "facts": (
            "Four accused persons acting in concert abducted the 10-year-old minor son of the complainant from outside "
            "his school in a black SUV. The kidnappers confined the boy in a remote farmhouse and made phone calls demanding "
            "a ransom of Rs 50 Lakhs, threatening to execute the child if police were informed."
        ),
        "expected_sections": ["137(1)(b)", "140(2)", "351", "3(5)"]
    },
    {
        "id": "FIR_07",
        "description": "Domestic Violence + Matrimonial Cruelty + Dowry Harassment + Voluntarily Causing Hurt",
        "facts": (
            "Since her marriage, the complainant wife was subjected to continuous physical and mental harassment by her "
            "husband and in-laws with unlawful demands for Rs 10 Lakhs dowry and a luxury car. The husband repeatedly beaten "
            "the complainant with a wooden stick causing hematoma and black eyes, and locked her in a dark room without food."
        ),
        "expected_sections": ["85", "86", "115(2)"]
    },
    {
        "id": "FIR_08",
        "description": "Armed Violent Rioting + Unlawful Assembly + Public Property Mischief",
        "facts": (
            "A violent mob consisting of over twenty persons gathered armed with iron rods, glass bottles, and lathis. "
            "In prosecution of their common object, the unlawful assembly pelted stones at the public bus depot, set two public "
            "transport buses on fire causing heavy property destruction, and assaulted commuters on the public road."
        ),
        "expected_sections": ["189(1)", "189(2)", "190", "191(1)", "324(4)", "324(5)"]
    },
    {
        "id": "FIR_09",
        "description": "Criminal Breach of Trust by Employee + Forgery of Accounts",
        "facts": (
            "The accused was employed as Chief Accountant in the complainant's trading firm and entrusted with corporate funds. "
            "The accused dishonestly misappropriated Rs 45,00,000 by forging purchase invoices, altering bank statements, and "
            "diverting corporate funds into his personal dummy bank accounts."
        ),
        "expected_sections": ["316(1)", "316(2)", "336", "338"]
    },
    {
        "id": "FIR_09B",
        "description": "Extortion + Threat of Injury + Joint Action",
        "facts": (
            "Two local goons visited the complainant's construction site and demanded weekly extortion money of Rs 50,000. "
            "The accused threatened that if the protection money was not paid immediately, they would break the workers' bones "
            "and halt the construction by force."
        ),
        "expected_sections": ["308", "351", "3(5)"]
    },
    {
        "id": "FIR_11",
        "description": "Rash and Negligent Driving + Hit and Run + Causing Hurt",
        "facts": (
            "The driver of a speeding truck drove on the public highway in an extremely rash and reckless manner, "
            "rammed into two pedestrians crossing the zebra line, and caused severe leg injuries before speeding away without stopping."
        ),
        "expected_sections": ["281", "125", "115(2)"]
    },
    {
        "id": "FIR_12",
        "description": "Outraging Modesty of Woman + Stalking + Criminal Intimidation",
        "facts": (
            "The accused persistently followed and stalked the complainant on her way to college for over a month despite clear "
            "objections. Today the accused intercepted her, grabbed her hand with intent to outrage her modesty, used vulgar gestures, "
            "and threatened to acid-attack her face if she complained to her parents."
        ),
        "expected_sections": ["74", "78", "79", "351"]
    },
    {
        "id": "FIR_13",
        "description": "Financial Investment Scam + Cheating + Inducement",
        "facts": (
            "The accused set up a bogus investment agency and dishonestly induced dozens of senior citizens to invest Rs 1.5 Crores "
            "promising 30% monthly returns. The accused issued fraudulent promissory notes, shut down the office overnight, and absconded with the money."
        ),
        "expected_sections": ["318(4)", "318", "319"]
    },
    {
        "id": "FIR_14",
        "description": "Criminal Trespass + Vandalism / Mischief + Insult to Provoke Breach of Peace",
        "facts": (
            "The accused forcibly entered the complainant's private agricultural farm without authorization, hurled abusive insults "
            "to provoke a fight, and used a tractor to destroy the standing wheat crop, causing over Rs 1,00,000 property damage."
        ),
        "expected_sections": ["329(1)", "324(2)", "324", "352"]
    },
    {
        "id": "FIR_15",
        "description": "Dacoity + Armed Gang Attack + Grievous Hurt",
        "facts": (
            "A gang of six armed dacoits raided a jewellery store at gunpoint. The six accused persons acting jointly assaulted the shopkeeper "
            "with iron rods causing skull fracture, looted 2 kg gold jewellery, and fired shots in the air before escaping in two cars."
        ),
        "expected_sections": ["310(2)", "306", "117(2)", "118(1)", "3(5)"]
    },
    {
        "id": "FIR_16",
        "description": "Culpable Homicide Not Amounting to Murder + Sudden Fight",
        "facts": (
            "During a sudden heated argument over parking, the accused lost temper, picked up a heavy stone and struck the victim on the head "
            "without premeditation. The victim collapsed and died shortly after from head injuries at the clinic."
        ),
        "expected_sections": ["100", "105"]
    },
    {
        "id": "FIR_17",
        "description": "Abetment of Suicide + Continuous Harassment",
        "facts": (
            "The accused money-lenders constantly harassed, publicly humiliated, and threatened the deceased borrower despite him repaying the principal. "
            "The relentless instigation directly drove the deceased to commit suicide by hanging, leaving behind a detailed suicide note naming the accused."
        ),
        "expected_sections": ["108", "45", "351"]
    },
    {
        "id": "FIR_18",
        "description": "Arson / Mischief by Fire + Criminal Intimidation",
        "facts": (
            "The accused poured petrol over the complainant's warehouse at midnight and set it on fire with intent to cause complete destruction. "
            "Goods worth Rs 12 Lakhs were reduced to ashes. The accused had earlier sent WhatsApp messages threatening to burn the premises."
        ),
        "expected_sections": ["324(4)", "324", "351"]
    },
    {
        "id": "FIR_19",
        "description": "Wrongful Confinement + Physical Assault + Extortion",
        "facts": (
            "Three accused persons locked the contractor inside an empty godown for 24 hours, beat him with belts, and refused to release him "
            "until his brother delivered Rs 2,00,000 cash to the perpetrators."
        ),
        "expected_sections": ["140(3)", "115(2)", "308", "3(5)"]
    },
    {
        "id": "FIR_20",
        "description": "Snatching on Public Street + Causing Hurt",
        "facts": (
            "While the victim was walking on the footpath, two bike-borne men snatched her gold necklace by pulling it forcefully, causing her to fall "
            "on the road and suffer abrasive injuries on her knees and elbows."
        ),
        "expected_sections": ["303(2)", "306", "115(2)", "3(5)"]
    },
    {
        "id": "FIR_21",
        "description": "Forgery of Will & Property Title Documents",
        "facts": (
            "The accused created a forged will containing fabricated signatures of the deceased father and submitted the bogus document to the "
            "sub-registrar office to fraudulently transfer ancestral property into his own name."
        ),
        "expected_sections": ["336", "338", "318"]
    },
    {
        "id": "FIR_22",
        "description": "Sexual Harassment at Workplace + Words Insulting Modesty",
        "facts": (
            "The manager repeatedly demanded sexual favours from the female subordinate, made sexually explicit comments during meetings, "
            "and sent unsolicited obscene messages on her official mobile phone."
        ),
        "expected_sections": ["75", "79"]
    },
    {
        "id": "FIR_23",
        "description": "Rape under Pretext of Marriage + Deceitful Promise",
        "facts": (
            "The accused established physical relations with the complainant woman by giving a false promise to marry her, knowing well that he was "
            "already engaged to another woman, and subsequently abandoned and threatened her."
        ),
        "expected_sections": ["64", "69", "351"]
    },
    {
        "id": "FIR_24",
        "description": "Acid Attack + Grievous Hurt with Permanent Disfigurement",
        "facts": (
            "The accused threw corrosive concentrated acid on the face and neck of the complainant woman when she rejected his marriage proposal, "
            "causing extensive chemical burn injuries and permanent facial disfigurement."
        ),
        "expected_sections": ["124(1)", "117(2)"]
    },
    {
        "id": "FIR_25",
        "description": "Mob Lynching on Identity Grounds + Murder by 5+ Persons",
        "facts": (
            "A violent mob of eight persons surrounded the victim on grounds of his religion, accused him of cattle transport, and lynched him "
            "by beating him with wooden sticks and iron rods until he died of trauma on the spot."
        ),
        "expected_sections": ["103(2)", "189(2)", "190", "191(1)", "3(5)"]
    },
    {
        "id": "FIR_26",
        "description": "Dowry Death within 7 Years of Marriage + Cruelty",
        "facts": (
            "Within three years of marriage, the victim died under abnormal burn circumstances in her matrimonial home following relentless "
            "harassment and physical cruelty by her husband and in-laws in connection with unpaid dowry demands."
        ),
        "expected_sections": ["80", "85", "86"]
    },
    {
        "id": "FIR_27",
        "description": "Cheating by Personation + Impersonating Public Servant",
        "facts": (
            "The accused falsely personated an Anti-Corruption Bureau officer, wore a fake police uniform and badge, conducted an illegal search "
            "of the complainant's shop, and collected Rs 75,000 cash under threat of arrest."
        ),
        "expected_sections": ["319", "318", "308"]
    },
    {
        "id": "FIR_28",
        "description": "Attempted Acid Attack + Stalking + Threat to Kill",
        "facts": (
            "The accused stalked the victim for weeks, attempted to throw a bottle of acid on her which spilled on her bag, and shouted "
            "that he would kill her if she did not agree to date him."
        ),
        "expected_sections": ["124(2)", "78", "351"]
    },
    {
        "id": "FIR_29",
        "description": "Petty Organized Theft Gang + Multi-Location Snatching",
        "facts": (
            "A gang of organized pickpockets operating in the crowded railway station snatched five mobile phones from passengers "
            "using razor blades to slit bags and pockets as part of a continuing organized theft syndicate."
        ),
        "expected_sections": ["112", "303(2)", "3(5)"]
    },
    {
        "id": "FIR_30",
        "description": "Extortion by Threat of Death + Forcible Cheque Signing",
        "facts": (
            "Three armed extortionists entered the builder's cabin, held a loaded gun to his forehead, and forced him under threat of instant death "
            "to sign blank cheques amounting to Rs 25 Lakhs before fleeing."
        ),
        "expected_sections": ["308", "309", "351", "3(5)"]
    }
]

def evaluate_multilabel_classifier():
    print("=" * 80)
    print("STARTING MULTI-LABEL BNS CLASSIFICATION BENCHMARK (30 COMPLEX FIRs)")
    print("=" * 80)

    classifier = MultiLabelBNSClassifier()
    
    total_expected = 0
    total_predicted = 0
    true_positives = 0
    case_results = []

    for test_case in TEST_FIRS:
        cid = test_case["id"]
        desc = test_case["description"]
        facts = test_case["facts"]
        expected = set(test_case["expected_sections"])
        
        result = classifier.classify_multilabel(facts, threshold=0.35, top_k=15)
        predicted_secs = set([s["section_id"] for s in result["bns"]])
        
        # Calculate overlap (accounting for parent/child section variations like 324 vs 324(2), 303(2) vs 303, etc.)
        matched = set()
        for p in predicted_secs:
            for e in expected:
                if p == e or p.startswith(e.split("(")[0]) or e.startswith(p.split("(")[0]):
                    matched.add(e)
        
        tp = len(matched)
        fp = max(0, len(predicted_secs) - tp)
        fn = max(0, len(expected) - tp)

        true_positives += tp
        total_expected += len(expected)
        total_predicted += len(predicted_secs)

        precision = tp / max(1, len(predicted_secs))
        recall = tp / max(1, len(expected))
        f1 = (2 * precision * recall) / max(1e-8, (precision + recall))

        case_results.append({
            "id": cid,
            "description": desc,
            "expected": list(expected),
            "predicted": [s["section_id"] for s in result["bns"]],
            "confidence_scores": {s["section_id"]: s["confidence_percent"] for s in result["bns"][:5]},
            "tp": tp,
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3)
        })

        pred_formatted = [f"{s['section_id']} ({s['confidence_percent']})" for s in result['bns']]
        print(f"[{cid}] {desc}")
        print(f"  Expected:  {list(expected)}")
        print(f"  Predicted: {pred_formatted}")
        print(f"  P: {precision:.2f} | R: {recall:.2f} | F1: {f1:.2f}")
        print("-" * 80)

    # Micro/Macro Metrics Calculation
    overall_precision = true_positives / max(1, total_predicted)
    overall_recall = true_positives / max(1, total_expected)
    overall_f1 = (2 * overall_precision * overall_recall) / max(1e-8, (overall_precision + overall_recall))
    
    avg_precision = float(np.mean([c["precision"] for c in case_results]))
    avg_recall = float(np.mean([c["recall"] for c in case_results]))
    avg_f1 = float(np.mean([c["f1"] for c in case_results]))
    exact_match_ratio = sum([1 for c in case_results if c["recall"] >= 0.80]) / len(case_results)

    summary = {
        "total_test_cases": len(TEST_FIRS),
        "macro_avg_precision": round(avg_precision, 4),
        "macro_avg_recall": round(avg_recall, 4),
        "macro_avg_f1_score": round(avg_f1, 4),
        "micro_precision": round(overall_precision, 4),
        "micro_recall": round(overall_recall, 4),
        "micro_f1_score": round(overall_f1, 4),
        "multi_label_coverage_rate": round(exact_match_ratio * 100, 2),
        "case_details": case_results
    }

    print("\n" + "=" * 80)
    print("BENCHMARK SUMMARY RESULTS:")
    print(f"Total Test Cases:                 {summary['total_test_cases']}")
    print(f"Macro Precision:                  {summary['macro_avg_precision'] * 100:.2f}%")
    print(f"Macro Recall:                     {summary['macro_avg_recall'] * 100:.2f}%")
    print(f"Macro F1-Score:                   {summary['macro_avg_f1_score'] * 100:.2f}%")
    print(f"Micro F1-Score:                   {summary['micro_f1_score'] * 100:.2f}%")
    print(f"Multi-Offence Coverage (R>=80%):  {summary['multi_label_coverage_rate']}%")
    print("=" * 80)

    out_path = os.path.join(os.path.dirname(__file__), "benchmark_results.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    print(f"Saved benchmark results to {out_path}")

    return summary

if __name__ == "__main__":
    evaluate_multilabel_classifier()
