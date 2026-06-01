# BNS Generator - Backend Model

This directory contains the core intelligence engine and API server for the BNS Generator. It hosts the Machine Learning pipeline responsible for predicting Bharatiya Nyaya Sanhita (BNS) sections.

## Technical Overview

The backend is built with **FastAPI** and serves as the bridge between the frontend application and the PyTorch-based inference models.

### Key Components

*   **`app/main.py`**: The entry point for the API. Defines routes (`/predict`, `/health`, `/retrieve`) and manages CORS/Server configuration.
*   **`app/model_wrapper.py`**: A complex wrapper class (`RAGHGATWrapper`) that:
    *   Loads the Legal BERT model.
    *   Manages the FAISS index for fast retrieval.
    *   Runs the Heterogeneous Graph Attention Network (HGAT) for final prediction.
    *   Handles fallback logic (Retrieval-only) if the full model isn't active.
*   **`app/hgat_model.py`**: Defines the GNN architecture.
*   **`model_data/`**: (Expected directory) Stores the trained model weights (`.pth`), FAISS indices, and metadata.

## Architecture

The inference pipeline follows a **Retrieve-and-Rank** strategy enhanced by Graph Neural Networks:

1.  **Fact Encoding**: Incoming text is converted to vector embeddings using `nlpaueb/legal-bert-base-uncased`.
2.  **Semantic Retrieval**: `faiss` or `sentence-transformers` retrieves the top-k most similar legal sections from the database.
3.  **Graph Construction**: The input queries and retrieved sections form nodes in a graph.
4.  **Inference**: The HGAT model propagates information to predict the likelihood of each section applying to the case.
5.  **Reranking**: An optional lightweight classifier refines the final order of results.

## Usage

### Prerequisites
- Python 3.9+
- CUDA-enabled GPU (recommended) or CPU.

### Running the Server
```bash
# Navigate to this directory
cd Backend_Model

# Activate API
uvicorn app.main:app --reload --port 8000
```

### API Endpoints
- `POST /predict`: Main inference endpoint. Requires JSON body with `facts`.
- `POST /retrieve`: Debug endpoint to fetch raw retrieval hits without full model inference.
- `GET /metrics`: Prometheus metrics for monitoring latency and accuracy.
