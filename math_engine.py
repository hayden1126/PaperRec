"""Personalized PageRank on a scraped citation edge list."""

import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix, csr_matrix, diags, eye
from scipy.sparse.linalg import spsolve

import config


def load_edges(path: str) -> pd.DataFrame:
    """Read edge list CSV and clean out invalid rows."""
    df = pd.read_csv(path, dtype=str)
    df = df.dropna() # remove broken data
    df = df[df["Source"] != df["Target"]] # remove self loops
    return df


def build_index(df: pd.DataFrame) -> dict[str, int]:
    """Map every unique paper ID to a contiguous integer index."""
    unique_ids = pd.unique(pd.concat([df["Source"], df["Target"]], ignore_index=True))  # collect all IDs from both columns
    return {pid: i for i, pid in enumerate(unique_ids)}


def build_transition_matrix(df: pd.DataFrame, id_to_idx: dict[str, int]) -> csr_matrix:
    """Column-stochastic transition matrix P where P[i,j] = prob of moving from j to i."""
    n = len(id_to_idx)
    rows = df["Target"].map(id_to_idx).to_numpy()
    cols = df["Source"].map(id_to_idx).to_numpy()
    data = np.ones(len(df), dtype=np.float64)

    A = coo_matrix((data, (rows, cols)), shape=(n, n)).tocsr()  # sparse adjacency matrix from edge list

    col_sums = np.asarray(A.sum(axis=0)).ravel()  # out-degree of each node
    inv = np.zeros_like(col_sums)
    nz = col_sums > 0
    inv[nz] = 1.0 / col_sums[nz]  # inverse degrees, zero for dangling nodes
    P = A @ diags(inv)  # normalize columns so each sums to 1
    return P.tocsr()


def personalized_pagerank(P: csr_matrix, seed_idx: int, damping: float) -> np.ndarray:
    """Solve the PPR linear system directly and return the normalized score vector."""
    n = P.shape[0]
    e_s = np.zeros(n, dtype=np.float64)
    e_s[seed_idx] = 1.0  # teleport vector: all weight on the seed node

    A_solve = (eye(n, format="csr") - damping * P).tocsc()  # (I - αP), rearranged from v = αPv + (1-α)e_s
    b = (1.0 - damping) * e_s
    v = spsolve(A_solve, b)  # solve (I - αP)v = (1-α)e_s

    total = v.sum()
    if total > 0:
        v = v / total
    return v


def rank(edges_path: str, seed_id: str) -> tuple[np.ndarray, dict[int, str]]:
    """Load edges, build the graph, run PPR from seed, and return scores with ID mapping."""
    df = load_edges(edges_path)
    id_to_idx = build_index(df)
    print(f"Loaded {len(df)} edges over {len(id_to_idx)} unique nodes")

    if seed_id not in id_to_idx:
        raise SystemExit(f"Seed {seed_id} not present in {edges_path}")

    P = build_transition_matrix(df, id_to_idx)
    v = personalized_pagerank(P, id_to_idx[seed_id], config.DAMPING)
    idx_to_id = {i: pid for pid, i in id_to_idx.items()}
    return v, idx_to_id


def top_n(v: np.ndarray, idx_to_id: dict[int, str], n: int) -> list[tuple[str, float]]:
    """Return the top-n (paper_id, score) pairs sorted by score descending."""
    order = np.argsort(-v)[:n]  # indices of the n highest scores
    return [(idx_to_id[int(i)], float(v[int(i)])) for i in order]
