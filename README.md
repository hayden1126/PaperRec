# PaperRec: Academic Paper Recommendation via Personalized PageRank

**Course:** MATH UN2015 - Linear Algebra & Probability, Columbia University  
**Topic:** Markov Chains and Eigenvectors/Eigenvalues in Network Analysis

## Project Overview

This project is a recommendation engine that addresses the "cold-start" problem in academic literature review. Rather than relying on keyword-based searches, the system dynamically constructs a localized citation network (an ego-network) centered around a single user-provided "seed" paper.

By modeling the citation graph as a Markov chain and applying Personalized PageRank, the system identifies the most structurally relevant papers within a specific sub-discipline. Supporting evaluation code verifies convergence behavior against theory and measures ranking stability under the damping parameter.

## Setup & Execution

### Prerequisites
* Python 3.12+
* A network connection (the pipeline queries the [Semantic Scholar API](https://www.semanticscholar.org/product/api))
* Optional: `S2_API_KEY` environment variable to lift the public-API rate limit

### Installation
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Running the recommender
```bash
# Use the default seed (set in config.py)
python main.py

# Specify a seed paper by Semantic Scholar ID
python main.py --seed <paper_id>

# Adjust BFS parameters
python main.py --seed <paper_id> --max-depth 3 --max-branching 30
```

The pipeline scrapes the citation network, computes PageRank, and prints a formatted reading list. Results are saved to `output/<timestamp>/` as `edges.csv`, `ranked_output.csv`, and `seed.txt`.

### Generating paper figures
```bash
python make_figures.py --run-dir output/<timestamp>
```

Produces `fig1_convergence.pdf` (power-iteration convergence with theoretical overlay) and `fig2_damping.pdf` (Pearson correlation heatmap across damping values) in the run directory. Also prints the top-N overlap between PPR rankings and raw citation count, used as a baseline comparison.

## The Mathematical Engine

The core of this project relies on applied linear algebra and probability:

1. **The Adjacency Matrix ($A$):** Citation relationships are modeled as a directed graph stored in an $N \times N$ sparse adjacency matrix, where $A_{ij} = 1$ if paper $j$ cites paper $i$.
2. **The Transition Probability Matrix ($P$):** $A$ is column-normalized so that each column sums to 1, representing the probability of a researcher navigating from one paper to another. Columns corresponding to dangling nodes (papers with no outgoing citations in the network) are redirected to the seed, following the *strongly preferential* PageRank convention (Langville & Meyer 2004).
3. **The Personalized PageRank System:** A teleportation vector $\mathbf{e}_s$ (all weight on the seed) and a damping factor $d = 0.85$ bias the random walk toward the seed. The steady-state vector $\mathbf{v}$ is obtained by solving the linear system directly:
   $$(I - dP)\mathbf{v} = (1 - d)\mathbf{e}_s$$
4. **The Steady-State Distribution ($\mathbf{v}$):** Because $P$ is column-stochastic, the solution $\mathbf{v}$ satisfies $\mathbf{1}^T \mathbf{v} = 1$ by construction. No post-normalization is required.

## Architecture

The project is split into five modules:

### `main.py` — Entry Point & Scraper
* Orchestrates the full pipeline: BFS network scraping, PageRank computation, metadata resolution, and output formatting.
* Wraps the Semantic Scholar API client with rate limiting and a configurable branching cap per node.
* Resolves external seed IDs (e.g., `ARXIV:1706.03762`) to internal Semantic Scholar paper IDs and writes the resolved ID to `seed.txt` in the run directory.

### `math_engine.py` — Linear Algebra & PageRank
* Maps paper IDs to integer indices and constructs a sparse adjacency matrix via `scipy.sparse.coo_matrix`.
* Builds the transition matrix $P$: column-normalizes the adjacency matrix, then redirects dangling columns to the seed via a rank-one sparse update so $P$ is column-stochastic.
* Solves the PPR linear system $(I - dP)\mathbf{v} = (1 - d)\mathbf{e}_s$ using `scipy.sparse.linalg.spsolve`.
* Returns the top-N paper IDs and their stationary-distribution scores.

### `evaluation.py` — Convergence and Sensitivity Analysis
* `power_iteration`: iterates $v_{k+1} = dPv_k + (1-d)\mathbf{e}_s$ and records the per-iteration $L^1$ residual, used to verify geometric convergence at rate $d$.
* `damping_sweep`: computes the PPR vector across a range of damping values and returns the pairwise Pearson correlation matrix between score vectors, used to quantify ranking stability.

### `make_figures.py` — Paper Figures
* Loads a completed run directory, runs the two evaluation methods, and saves two PDF figures (semi-log convergence plot, Pearson correlation heatmap).
* Prints the top-N overlap between PPR rankings and raw citation-count rankings as a baseline comparison.

### `config.py` — Configuration
* Shared constants: seed paper ID, BFS depth/branching, damping factor, API rate limiting, top-N count, and output file names.

## Pipeline Walkthrough

### Step 1: Scrape (`main.py`)

1. Read the seed ID from `--seed` (or `config.SEED_ID`). Resolve it to an internal Semantic Scholar ID via the API.
2. Run BFS from the seed with `MAX_DEPTH = 2` and `MAX_BRANCHING = 50`:
   - For each node, fetch both its **references** (outgoing edges) and **citations** (incoming edges), capped at the branching limit.
   - Enqueue newly discovered papers, tracking visited nodes to avoid cycles.
3. Stream edges to `output/<timestamp>/edges.csv` as `Source,Target` pairs. Write the resolved seed ID to `seed.txt` in the same directory.

### Step 2: Rank (`math_engine.py`)

1. Load `edges.csv`, drop invalid rows and self-loops, and assign each unique paper ID a contiguous integer index ($0$ to $N-1$).
2. Build a sparse $N \times N$ adjacency matrix, column-normalize it, and redirect dangling columns to the seed so $P$ is column-stochastic.
3. Solve $(I - dP)\mathbf{v} = (1 - d)\mathbf{e}_s$ via `spsolve`. The solution $\mathbf{v}$ sums to $1$ by construction.
4. Return the top-20 paper IDs and scores to `main.py`, which writes `ranked_output.csv`.

### Step 3: Display (`main.py`)

1. Batch-fetch metadata (title, authors, year, abstract, venue) for the top-ranked papers via `semanticscholar.get_papers()`.
2. Print a formatted reading list to the terminal.

### Step 4: Evaluate (`make_figures.py`, optional)

1. Run power iteration at the default damping to produce a convergence trace.
2. Run a damping sweep across $\{0.50, 0.60, 0.70, 0.80, 0.85, 0.90, 0.95, 0.99\}$ to produce a stability heatmap.
3. Compute the top-N overlap between PPR and raw citation-count rankings.
4. Save figures to the run directory and print the overlap to stdout.

## Known Challenges & Mitigations

* **Memory:** A depth-2 citation network can yield $N > 10{,}000$ nodes (a 100M-entry dense matrix). This is handled entirely with `scipy.sparse` data structures (`coo_matrix`, `csr_matrix`).
* **Dangling Nodes:** Papers with zero outbound citations in the scraped network are handled by redirecting their transition columns to the seed (strongly preferential PageRank convention, Langville & Meyer 2004). This keeps $P$ column-stochastic and preserves the random-walk interpretation of $\mathbf{v}$.
* **API Rate Limits:** The Semantic Scholar public API allows ~1 request/second without a key. The client enforces a 1.1-second sleep between calls (0.1 seconds if `S2_API_KEY` is set) and a 30-second timeout per request.
