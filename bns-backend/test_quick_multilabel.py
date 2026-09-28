import sys
import os
sys.path.insert(0, ".")

from app.multilabel_classifier import MultiLabelBNSClassifier

classifier = MultiLabelBNSClassifier()
test_fir = (
    "On 12th August at around 10:30 PM, the complainant Rajesh Kumar was returning home when "
    "three accused individuals intercepted his motorcycle near the market. The three accused persons "
    "acting in furtherance of common intention assaulted the complainant by beating him with an iron rod "
    "and punched him repeatedly, causing bleeding injuries on his head and arms. The accused brandished "
    "a sharp knife and threatened to kill him if he shouted. They forcibly snatched his gold chain and wallet "
    "containing Rs 15,000 cash. Before fleeing the spot on their two-wheelers, the accused intentionally "
    "smashed the headlight and petrol tank of the complainant's motorcycle, causing heavy damage to the vehicle."
)

result = classifier.classify_multilabel(test_fir, threshold=0.35)
print(f"Total detected sections: {result['total_sections']}")
print(f"Primary Crime Category: {result['crime_type']}")
print("-" * 70)
for sec in result["bns"]:
    print(f"-> BNS {sec['section_id']}: {sec['title']}")
    print(f"   Confidence: {sec['confidence_percent']} ({sec['confidence']}) | Category: {sec['category']}")
    print(f"   Explanation: {sec['explanation']}")
    print(f"   Triggers: {sec['trigger_sentences']}")
    print()
