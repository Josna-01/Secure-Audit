import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, ConnectionPatch
import matplotlib.lines as mlines

# Set up the figure with high DPI for IEEE publication
fig, ax = plt.subplots(figsize=(12, 18), dpi=300)
ax.set_xlim(0, 10)
ax.set_ylim(0, 30)
ax.axis('off')

# Define colors
color_input = '#D3D3D3'  # Gray
color_bert = '#ADD8E6'   # Light Blue
color_rag = '#FFB366'    # Orange
color_fusion = '#90EE90' # Light Green
color_darkgreen = '#228B22' # Dark Green
color_teal = '#20B2AA'   # Teal
color_purple = '#DDA0DD' # Purple/Lavender
color_pink = '#FFB6C1'   # Pink
color_yellow = '#FFEB99' # Yellow
color_red = '#FF6B6B'    # Red
color_blue = '#6B9BD1'   # Blue
color_output = '#98FB98' # Green

def create_box(ax, x, y, width, height, text, color, fontsize=9, 
               fontweight='normal', linestyle='-', linewidth=1.5):
    """Create a rounded rectangle box with text"""
    box = FancyBboxPatch((x - width/2, y - height/2), width, height,
                         boxstyle="round,pad=0.05", 
                         edgecolor='black', facecolor=color,
                         linestyle=linestyle, linewidth=linewidth,
                         transform=ax.transData, zorder=2)
    ax.add_patch(box)
    ax.text(x, y, text, ha='center', va='center', fontsize=fontsize,
            fontweight=fontweight, fontfamily='sans-serif', zorder=3,
            wrap=True)
    return box

def create_arrow(ax, x1, y1, x2, y2, label='', labelpos='mid'):
    """Create an arrow between two points"""
    arrow = FancyArrowPatch((x1, y1), (x2, y2),
                           arrowstyle='->', mutation_scale=20,
                           linewidth=2, color='black', zorder=1)
    ax.add_patch(arrow)
    if label:
        mid_x, mid_y = (x1 + x2) / 2, (y1 + y2) / 2
        ax.text(mid_x + 0.3, mid_y, label, fontsize=7, 
                style='italic', color='darkred')

# Vertical positions (from top to bottom)
y_pos = 29

# 1. Input Layer
create_box(ax, 5, y_pos, 3, 0.6, 'Crime Complaint Text', color_input, fontsize=10, fontweight='bold')
create_arrow(ax, 5, y_pos - 0.3, 5, y_pos - 0.8)
y_pos -= 1.5

# 2. Dual Encoding Layer - Title
ax.text(5, y_pos + 0.3, 'Dual Encoding Layer', ha='center', fontsize=10, 
        fontweight='bold', style='italic')

# LEFT PATH - BERT
x_left = 2.5
y_bert = y_pos
create_box(ax, x_left, y_bert, 2.2, 0.8, 
           'Legal-BERT Encoder\n(nlpaueb/legal-bert-\nbase-uncased)', 
           color_bert, fontsize=8)
create_arrow(ax, x_left, y_bert - 0.4, x_left, y_bert - 0.9)

y_bert -= 1.3
create_box(ax, x_left, y_bert, 2.2, 0.5, 
           'CLS Token\nEmbedding (768-dim)', 
           color_bert, fontsize=8)

# RIGHT PATH - RAG
x_right = 7.5
y_rag = y_pos
create_box(ax, x_right, y_rag, 2.2, 0.6, 
           'BNS Knowledge Base\n(57 Sections)', 
           color_rag, fontsize=8)
create_arrow(ax, x_right, y_rag - 0.3, x_right, y_rag - 0.7)

y_rag -= 1.0
create_box(ax, x_right, y_rag, 2.2, 0.7, 
           'Sentence Transformer\n(all-MiniLM-L6-v2,\n384-dim)', 
           color_rag, fontsize=7)
create_arrow(ax, x_right, y_rag - 0.35, x_right, y_rag - 0.7)

y_rag -= 1.0
create_box(ax, x_right, y_rag, 2.2, 0.5, 
           'FAISS Index\n(Cosine Similarity)', 
           color_rag, fontsize=8)
create_arrow(ax, x_right, y_rag - 0.25, x_right, y_rag - 0.6)

y_rag -= 0.9
create_box(ax, x_right, y_rag, 2.2, 0.5, 
           'Top-K Retrieval\n(k=20)', 
           color_rag, fontsize=8)
create_arrow(ax, x_right, y_rag - 0.25, x_right, y_rag - 0.6)

y_rag -= 0.9
create_box(ax, x_right, y_rag, 2.2, 0.5, 
           'RAG Scores\n(57 dims)', 
           color_rag, fontsize=8)
ax.text(x_right + 1.3, y_rag, 'Scaled\nby 10×', fontsize=7, 
        style='italic', color='darkred', ha='left')

# 3. Feature Fusion
y_fusion = y_rag - 1.2
create_arrow(ax, x_left, y_bert - 0.25, x_left, y_fusion + 0.4)
create_arrow(ax, x_right, y_rag - 0.25, x_right, y_fusion + 0.4)
create_arrow(ax, x_left, y_fusion + 0.4, 5, y_fusion + 0.4)
create_arrow(ax, x_right, y_fusion + 0.4, 5, y_fusion + 0.4)

create_box(ax, 5, y_fusion, 4, 0.7, 
           'Concatenate [BERT ⊕ Scaled RAG]\n→ 825-dim Combined Features', 
           color_fusion, fontsize=8, fontweight='bold')
create_arrow(ax, 5, y_fusion - 0.35, 5, y_fusion - 0.7)

# 4. Case Encoder
y_encoder = y_fusion - 1.3
create_box(ax, 5, y_encoder, 4, 0.7, 
           'Linear(825→512) + LayerNorm\n+ ReLU + Dropout(0.3)', 
           color_fusion, fontsize=8)
create_arrow(ax, 5, y_encoder - 0.35, 5, y_encoder - 0.7)

y_projected = y_encoder - 1.1
create_box(ax, 5, y_projected, 3.5, 0.5, 
           'Projected Case Features\n(512 dims)', 
           color_fusion, fontsize=8)

# 5. Split into TWO BRANCHES
y_branch = y_projected - 1.0
create_arrow(ax, 5, y_projected - 0.25, x_left, y_branch)
create_arrow(ax, 5, y_projected - 0.25, x_right, y_branch)

# LEFT BRANCH - Attention
y_att = y_branch
create_box(ax, x_left, y_att, 2.5, 0.7, 
           'Multi-Head Attention\n(Case-Level, 4 heads)', 
           color_teal, fontsize=8)
create_arrow(ax, x_left, y_att - 0.35, x_left, y_att - 0.7)

y_att -= 1.1
create_box(ax, x_left, y_att, 2.5, 0.5, 
           'Case Representation\n(512 dims)', 
           color_teal, fontsize=8)

# RIGHT BRANCH - GNN
y_gnn = y_branch
create_box(ax, x_right, y_gnn, 2.5, 0.7, 
           'Graph Construction:\n57 BNS Section Nodes\n(384-dim)', 
           color_purple, fontsize=7)
create_arrow(ax, x_right, y_gnn - 0.35, x_right, y_gnn - 0.7)

y_gnn -= 1.0
create_box(ax, x_right, y_gnn, 2.5, 0.6, 
           'GATConv(384→256×4)\n→ ELU', 
           color_purple, fontsize=8)
create_arrow(ax, x_right, y_gnn - 0.3, x_right, y_gnn - 0.65)

y_gnn -= 0.95
create_box(ax, x_right, y_gnn, 2.5, 0.5, 
           'GATConv(1024→256×4)', 
           color_purple, fontsize=8)
create_arrow(ax, x_right, y_gnn - 0.25, x_right, y_gnn - 0.6)

y_gnn -= 0.85
create_box(ax, x_right, y_gnn, 2.5, 0.5, 
           'Global Pooling\n(Mean & Max)', 
           color_purple, fontsize=8)
create_arrow(ax, x_right, y_gnn - 0.25, x_right, y_gnn - 0.6)

y_gnn -= 0.9
create_box(ax, x_right, y_gnn, 2.5, 0.5, 
           'Graph-Level Features\n(1024 dims)', 
           color_purple, fontsize=8)

# 6. Cross-Attention
y_cross = min(y_att, y_gnn) - 1.2
create_arrow(ax, x_left, y_att - 0.25, x_left, y_cross + 0.5)
create_arrow(ax, x_right, y_gnn - 0.25, x_right, y_cross + 0.5)
create_arrow(ax, x_left, y_cross + 0.5, 5, y_cross + 0.5)
create_arrow(ax, x_right, y_cross + 0.5, 5, y_cross + 0.5)

create_box(ax, 5, y_cross, 4.5, 0.7, 
           'Cross-Attention:\nCase Features (Q) ↔ Graph Features (K,V)', 
           color_pink, fontsize=8, fontweight='bold')
create_arrow(ax, 5, y_cross - 0.35, 5, y_cross - 0.7)

y_attended = y_cross - 1.1
create_box(ax, 5, y_attended, 3.5, 0.5, 
           'Attended Features\n(512 dims)', 
           color_pink, fontsize=8)
create_arrow(ax, 5, y_attended - 0.25, 5, y_attended - 0.6)

# 7. Feature Fusion
y_final_fusion = y_attended - 1.0
create_box(ax, 5, y_final_fusion, 4.5, 0.6, 
           'Case Features (512) ⊕ Graph Features (1024)\n→ 1536-dim', 
           color_darkgreen, fontsize=8, fontweight='bold')
create_arrow(ax, 5, y_final_fusion - 0.3, 5, y_final_fusion - 0.65)

# 8. Shared Base Layer
y_shared = y_final_fusion - 1.1
create_box(ax, 5, y_shared, 4.5, 0.7, 
           'Shared Base Layer:\nLinear(1536→1536) + LayerNorm\n+ ReLU + Dropout(0.3)', 
           color_yellow, fontsize=8, fontweight='bold')

# 9. Split into TWO OUTPUT HEADS
y_output = y_shared - 1.2
create_arrow(ax, 5, y_shared - 0.35, x_left, y_output)
create_arrow(ax, 5, y_shared - 0.35, x_right, y_output)

# LEFT OUTPUT - Section Classification
create_box(ax, x_left, y_output, 2.5, 0.9, 
           'Section Classification\nHead\n57 Expert Classifiers:\nLinear(1536→1)\nSigmoid Activation', 
           color_red, fontsize=7, fontweight='bold')
create_arrow(ax, x_left, y_output - 0.45, x_left, y_output - 0.8)

y_out_left = y_output - 1.2
create_box(ax, x_left, y_out_left, 2.5, 0.5, 
           'Multi-Label\nSection Predictions', 
           color_red, fontsize=8)

# RIGHT OUTPUT - Crime Type Classification
create_box(ax, x_right, y_output, 2.5, 0.8, 
           'Crime Type\nClassification Head\nLinear(1536→13)\nSoftmax Activation', 
           color_blue, fontsize=7, fontweight='bold')
create_arrow(ax, x_right, y_output - 0.4, x_right, y_output - 0.75)

y_out_right = y_output - 1.15
create_box(ax, x_right, y_out_right, 2.5, 0.5, 
           'Single-Label\nCrime Type Prediction', 
           color_blue, fontsize=8)

# 10. Final Output
y_final = y_out_left - 1.0
create_arrow(ax, x_left, y_out_left - 0.25, x_left, y_final + 0.3)
create_arrow(ax, x_right, y_out_right - 0.25, x_right, y_final + 0.3)
create_arrow(ax, x_left, y_final + 0.3, 5, y_final + 0.3)
create_arrow(ax, x_right, y_final + 0.3, 5, y_final + 0.3)

create_box(ax, 5, y_final, 4, 0.6, 
           'Predicted Legal Sections +\nPredicted Crime Type', 
           color_output, fontsize=9, fontweight='bold')

# Add annotation boxes for loss and optimizer
ax.text(1, 2, 'Loss Function:\nAsymmetric Loss\n(γ_neg=4, γ_pos=1)', 
        fontsize=7, bbox=dict(boxstyle='round', facecolor='lightyellow', 
        edgecolor='black', linewidth=1))

ax.text(7.5, 2, 'Optimizer:\nAdamW\n(lr=1e-4, wd=0.01)', 
        fontsize=7, bbox=dict(boxstyle='round', facecolor='lightyellow', 
        edgecolor='black', linewidth=1))

# Add title
ax.text(5, 30, 'RAG-HGAT Architecture:\nHybrid Retrieval-Augmented Graph Attention Network', 
        ha='center', fontsize=12, fontweight='bold', 
        bbox=dict(boxstyle='round', facecolor='lightgray', alpha=0.3))

plt.tight_layout()
plt.savefig('RAG_HGAT_Architecture_IEEE.png', dpi=300, bbox_inches='tight', 
            facecolor='white', edgecolor='none')
print("Diagram saved as 'RAG_HGAT_Architecture_IEEE.png'")
plt.show()
