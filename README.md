# Academic Paper Recommendation System via Personalized PageRank

**Course:** MATH UN2015 - Linear Algebra & Probability, Columbia University  
**Topic:** Markov Chains and Eigenvectors/Eigenvalues in Network Analysis

## Project Overview
This project is a mathematical simulation and recommendation engine designed to solve the "cold-start" problem in academic literature review. Instead of relying on keyword-based searches (which are prone to semantic bias), this system dynamically constructs a localized citation network (an ego-network) centered around a single user-inputted "seed" paper. 

By modeling the literature review process as a random walk on a Markov chain and applying a Personalized PageRank algorithm, the system mathematically identifies and recommends the most structurally authoritative papers within that specific sub-discipline.

## The Mathematical Engine
The core of this project relies on applied linear algebra and probability:

1. **The Adjacency Matrix ($A$):** Citation relationships are modeled as a directed graph. The connections are stored in an $N \times N$ sparse adjacency matrix where $A_{ij} = 1$ if paper $i$ cites paper $j$.
2. **The Transition Probability Matrix ($P$):** $A$ is row-normalized to represent the probability of a researcher navigating from one paper to another. 
3. **The Personalized PageRank Matrix ($M$):** To account for "dangling nodes" (papers with zero outbound citations) and to personalize the network, a teleportation vector ($e_s$) biased strictly toward the seed paper is introduced alongside a damping factor ($d = 0.85$):
   $$M = d P + (1-d) e_s 1^T$$
4. **The Steady-State Distribution ($v$):** We calculate the principal eigenvector of $M$ (where $\lambda = 1$). This resulting vector $v$ provides the steady-state probability of each node, mathematically ranking the papers by structural relevance to the seed.

## Software Architecture
To manage API rate limits and the massive memory overhead of $N \times N$ matrices, the project is split into two Python modules orchestrated by a single entry point:

### `main.py` (Entry Point)
* **Function:** Orchestrates the full pipeline — scrapes the citation ego-network via BFS over the Semantic Scholar API, runs PageRank, fetches metadata, and prints a formatted reading list.
* **Constraints:** Implements a strict branching cap (e.g., top 50 citations per node) to prevent exponential explosion at a depth of 2.
* **Output:** Writes `edges.csv` and `ranked_output.csv` to a timestamped folder under `output/`, then prints results to the terminal.

### `math_engine.py` (Linear Algebra & PageRank)
* **Function:** Maps alphanumeric paper IDs to integer indices and constructs the network using `scipy.sparse` data structures to prevent memory overflow.
* **Execution:** Applies the damping factor, constructs the Markov transition matrix, and computes the principal eigenvector.
* **Output:** Returns the top-ranked paper IDs and their steady-state probabilities to `main.py`.

### `config.py` (Configuration)
* **Function:** Shared constants — seed paper ID, BFS depth/branching, damping factor, API rate limiting, and output file names.

## Setup & Execution

### Prerequisites
* Python 3.10+
* Required Libraries: `numpy`, `scipy`, `pandas`, `semanticscholar`

### Workflow
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py --seed <Semantic_Scholar_Paper_ID>
```

The pipeline scrapes the network, computes PageRank, and prints the reading list in one run. Results are saved to `output/<timestamp>/`.

## Known Challenges & Mitigations
* **Memory Constraints:** A depth of 2 in a citation network can yield $N > 10,000$ nodes (a 100M entry matrix). Dense matrices will cause immediate memory failure. This is mitigated entirely by utilizing `scipy.sparse.coo_matrix` and `csr_matrix`.
* **Dangling Nodes:** Uncited papers act as probability sinks in a standard Markov chain. The integration of the damping factor ($d = 0.85$) mathematically guarantees the matrix remains regular, allowing the simulation to "teleport" back to the seed.

Here is the exact step-by-step logical workflow, broken down by module.

### Step 1: Scrape (`main.py` — BFS traversal)
**Goal:** Traverse the Semantic Scholar API to build a local ego-network edge list.

1.  **Initialize State:**
    * Read the `SEED_ID` from `config.py` (or `--seed` CLI argument).
    * Define `MAX_DEPTH = 2` and `MAX_BRANCHING = 50`.
    * Initialize a `queue` (list of tuples: `(paper_id, current_depth)`).
    * Initialize a `visited` set to track processed paper IDs.
2.  **Execute BFS:**
    * While `queue` is not empty, pop the first element `(current_id, depth)`.
    * If `depth >= MAX_DEPTH`, skip.
    * Fetch both citations and references for `current_id` via the `semanticscholar` library, applying the branching cap.
    * For each connected paper, yield the edge and enqueue if not yet visited.
3.  **Export:**
    * Stream edges to `output/<timestamp>/edges.csv` with headers `Source,Target`.

### Step 2: Rank (`math_engine.py` — Personalized PageRank)
**Goal:** Parse the edges into a sparse matrix and solve the Personalized PageRank linear system.

1.  **Read and Map Nodes:**
    * Load `edges.csv` and map each unique paper ID to an integer index ($0$ to $N-1$).
2.  **Construct Sparse Transition Matrix ($P$):**
    * Build a `scipy.sparse.coo_matrix` from the edge list.
    * Column-normalize to get the transition probability matrix.
3.  **Solve the Linear System:**
    * Construct $A_{solve} = (I - d \times P)$ and $\mathbf{b} = (1 - d) \times \mathbf{e}_s$.
    * Use `scipy.sparse.linalg.spsolve(A_solve, b)` to find the steady-state vector $\mathbf{v}$.
4.  **Return** the top-$N$ paper IDs and scores to `main.py`, which writes `ranked_output.csv`.

### Step 3: Output (`main.py` — metadata resolution)
**Goal:** Resolve the mathematical rankings into readable academic metadata.

1.  **Batch API Query:** Fetch title, authors, year, abstract, and venue for the top-ranked papers via `semanticscholar.get_papers()`.
2.  **Format and Display:** Print a formatted reading list to the terminal.