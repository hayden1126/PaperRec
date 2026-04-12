# PaperRec: Academic Paper Recommendation via Personalized PageRank

**Course:** MATH UN2015 - Linear Algebra & Probability, Columbia University  
**Topic:** Markov Chains and Eigenvectors/Eigenvalues in Network Analysis

## Project Overview

This project is a recommendation engine that addresses the "cold-start" problem in academic literature review. Rather than relying on keyword-based searches, the system dynamically constructs a localized citation network (an ego-network) centered around a single user-provided "seed" paper.

By modeling the citation graph as a Markov chain and applying Personalized PageRank, the system identifies the most structurally relevant papers within a specific sub-discipline.

## Setup & Execution

### Prerequisites
* Python 3.12+
* A network connection (the pipeline queries the [Semantic Scholar API](https://www.semanticscholar.org/product/api))

### Installation
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Running
```bash
# Use the default seed (Attention Is All You Need)
python main.py

# Specify a seed paper by Semantic Scholar ID
python main.py --seed <paper_id>

# Adjust BFS parameters
python main.py --seed <paper_id> --max-depth 3 --max-branching 30
```

The pipeline scrapes the citation network, computes PageRank, and prints a formatted reading list. Results are saved to `output/<timestamp>/` as `edges.csv` and `ranked_output.csv`.

## The Mathematical Engine

The core of this project relies on applied linear algebra and probability:

1. **The Adjacency Matrix ($A$):** Citation relationships are modeled as a directed graph stored in an $N \times N$ sparse adjacency matrix, where $A_{ij} = 1$ if paper $j$ cites paper $i$.
2. **The Transition Probability Matrix ($P$):** $A$ is column-normalized so that each column sums to 1, representing the probability of a researcher navigating from one paper to another.
3. **The Personalized PageRank System:** To handle dangling nodes (papers with zero outbound citations) and to bias results toward the seed, a teleportation vector $\mathbf{e}_s$ (all weight on the seed) and a damping factor $d = 0.85$ are introduced. The steady-state vector $\mathbf{v}$ is obtained by solving the linear system directly:
   $$(I - dP)\mathbf{v} = (1 - d)\mathbf{e}_s$$
4. **The Steady-State Distribution ($\mathbf{v}$):** The resulting vector $\mathbf{v}$, normalized to sum to 1, assigns each paper a score representing its structural relevance to the seed.

## Architecture

The project is split into three modules:

### `main.py` — Entry Point & Scraper
* Orchestrates the full pipeline: BFS network scraping, PageRank computation, metadata resolution, and output formatting.
* Wraps the Semantic Scholar API client with rate limiting (~1 req/s) and a configurable branching cap per node.
* Resolves external seed IDs (e.g., `ARXIV:1706.03762`) to internal Semantic Scholar paper IDs before traversal.

### `math_engine.py` — Linear Algebra & PageRank
* Maps paper IDs to integer indices and constructs a sparse adjacency matrix via `scipy.sparse.coo_matrix`.
* Column-normalizes the adjacency matrix into the transition probability matrix $P$.
* Solves the PPR linear system $(I - dP)\mathbf{v} = (1 - d)\mathbf{e}_s$ using `scipy.sparse.linalg.spsolve`.
* Returns the top-$N$ paper IDs and their steady-state scores.

### `config.py` — Configuration
* Shared constants: seed paper ID, BFS depth/branching, damping factor, API rate limiting, top-$N$ count, and output file names.

## Pipeline Walkthrough

### Step 1: Scrape (`main.py`)

1. Read the seed ID from `--seed` (or `config.SEED_ID`). Resolve it to an internal Semantic Scholar ID via the API.
2. Run BFS from the seed with `MAX_DEPTH = 2` and `MAX_BRANCHING = 50`:
   - For each node, fetch both its **references** (outgoing edges) and **citations** (incoming edges), capped at the branching limit.
   - Enqueue newly discovered papers, tracking visited nodes to avoid cycles.
3. Stream edges to `output/<timestamp>/edges.csv` as `Source,Target` pairs.

### Step 2: Rank (`math_engine.py`)

1. Load `edges.csv`, drop invalid rows and self-loops, and assign each unique paper ID a contiguous integer index ($0$ to $N-1$).
2. Build a sparse $N \times N$ adjacency matrix and column-normalize it into the transition matrix $P$.
3. Solve $(I - dP)\mathbf{v} = (1 - d)\mathbf{e}_s$ via `spsolve`. Normalize $\mathbf{v}$ to a probability distribution.
4. Return the top-20 paper IDs and scores to `main.py`, which writes `ranked_output.csv`.

### Step 3: Display (`main.py`)

1. Batch-fetch metadata (title, authors, year, abstract, venue) for the top-ranked papers via `semanticscholar.get_papers()`.
2. Print a formatted reading list to the terminal.

## Known Challenges & Mitigations

* **Memory:** A depth-2 citation network can yield $N > 10{,}000$ nodes (a 100M-entry dense matrix). This is handled entirely with `scipy.sparse` data structures (`coo_matrix`, `csr_matrix`).
* **Dangling Nodes:** Papers with zero outbound citations are probability sinks. The damping factor ($d = 0.85$) and teleportation vector guarantee convergence by redistributing probability back to the seed.
* **API Rate Limits:** The Semantic Scholar public API allows ~1 request/second. The client enforces a 1.1-second sleep between calls and a 30-second timeout per request.