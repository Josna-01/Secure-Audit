import pandas as pd
import numpy as np
import ast
from collections import Counter

# Load and analyze dataset
df = pd.read_csv('enhanced_bns_dataset_6693_cases_20251023_170413.csv')

print('=== DATASET ANALYSIS ===')
print(f'Total samples: {len(df)}')
print(f'Columns: {list(df.columns)}')
print()

# Check for missing values
print('=== MISSING VALUES ===')
print(df.isnull().sum())
print()

# Analyze text length distribution
df['facts_length'] = df['facts'].str.len()
print('=== TEXT LENGTH ANALYSIS ===')
print(f'Average facts length: {df["facts_length"].mean():.0f} characters')
print(f'Min facts length: {df["facts_length"].min()}')
print(f'Max facts length: {df["facts_length"].max()}')
print(f'Median facts length: {df["facts_length"].median():.0f}')
print()

# Analyze crime type distribution
print('=== CRIME TYPE DISTRIBUTION ===')
crime_counts = df['crime_type'].value_counts()
print(crime_counts)
print()

# Analyze BNS sections
def parse_bns_sections(section_str):
    try:
        sections = ast.literal_eval(section_str)
        return [s for s in sections if s not in ['N/A - NDPS Act applies', 'No BNS mapping']]
    except:
        return []

df['bns_sections'] = df['mapped_bns_sections_fixed'].apply(parse_bns_sections)
df = df[df['bns_sections'].apply(len) > 0].reset_index(drop=True)

print('=== BNS SECTIONS ANALYSIS ===')
all_sections = [s for sections in df['bns_sections'] for s in sections]
unique_sections = list(set(all_sections))
print(f'Total unique BNS sections: {len(unique_sections)}')
print(f'Average sections per case: {np.mean([len(sections) for sections in df["bns_sections"]]):.2f}')

# Section frequency
section_counts = Counter(all_sections)
print(f'Most common sections: {section_counts.most_common(10)}')
print(f'Least common sections: {section_counts.most_common()[-10:]}')
print()

# Check for class imbalance
print('=== CLASS IMBALANCE ANALYSIS ===')
section_freq = dict(section_counts)
total_cases = len(df)
for section, count in sorted(section_freq.items(), key=lambda x: x[1], reverse=True)[:10]:
    percentage = (count / total_cases) * 100
    print(f'{section}: {count} cases ({percentage:.1f}%)')

# Check for very rare classes
rare_sections = [(s, c) for s, c in section_freq.items() if c < 10]
print(f'\nRare sections (< 10 cases): {len(rare_sections)}')
for section, count in rare_sections[:5]:
    print(f'{section}: {count} cases')

# Analyze text quality
print('\n=== TEXT QUALITY ANALYSIS ===')
# Check for very short texts
short_texts = df[df['facts_length'] < 100]
print(f'Very short texts (< 100 chars): {len(short_texts)} ({len(short_texts)/len(df)*100:.1f}%)')

# Check for very long texts
long_texts = df[df['facts_length'] > 2000]
print(f'Very long texts (> 2000 chars): {len(long_texts)} ({len(long_texts)/len(df)*100:.1f}%)')

# Sample some texts to check quality
print('\n=== SAMPLE TEXTS ===')
for i in range(3):
    print(f'\nSample {i+1}:')
    print(f'Length: {df.iloc[i]["facts_length"]} chars')
    print(f'Text: {df.iloc[i]["facts"][:200]}...')
    print(f'BNS sections: {df.iloc[i]["bns_sections"]}')
