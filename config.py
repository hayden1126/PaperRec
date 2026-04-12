"""Shared constants for the PaperRec pipeline."""

# Pipeline parameters
SEED_ID = "1706.03762v7" # Attention Is All You Need
MAX_DEPTH = 2
MAX_BRANCHING = 50
DAMPING = 0.85
TOP_N = 20

# Semantic Scholar
REQUEST_SLEEP_SECONDS = 1.1  # respect public rate limit (~1 req/s)
REQUEST_TIMEOUT_SECONDS = 30

# Files
OUTPUT_DIR = "output"
EDGES_CSV = "edges.csv"
RANKED_CSV = "ranked_output.csv"
