"""PaperRec: 
scrape a citation ego-network from a seed paper, 
rank via Personalized PageRank,
and display a reading list."""

import argparse
import csv
import os
import time
from datetime import datetime
from collections.abc import Iterator

from semanticscholar import SemanticScholar

import config
import math_engine


Edge = tuple[str, str]

METADATA_FIELDS = ["title", "authors", "year", "abstract", "citationCount", "venue"]


BATCH_SIZE = 500  # Semantic Scholar batch endpoint limit


class SemanticScholarClient:
    """SemanticScholar wrapper with safe pagination and pacing."""

    def __init__(self, *, branching: int, sleep_seconds: float, timeout: float) -> None:
        self._sch = SemanticScholar(timeout=timeout)
        self._branching = branching
        self._sleep = sleep_seconds

    def resolve_id(self, paper_id: str) -> str:
        """Resolve an external ID (e.g. ARXIV:...) to an internal paperId."""
        paper = self._sch.get_paper(paper_id, fields=["paperId"])
        if paper and paper.paperId:
            return paper.paperId
        return paper_id

    def get_papers(self, paper_ids: list[str]) -> dict:
        papers = self._sch.get_papers(paper_ids, fields=METADATA_FIELDS)
        return {p.paperId: p for p in papers if p and p.paperId}

    def get_papers_with_neighbors(self, paper_ids: list[str]) -> list:
        """Batch-fetch papers with their references and citations."""
        fields = ["paperId", "references.paperId", "citations.paperId"]
        results = []
        for i in range(0, len(paper_ids), BATCH_SIZE):
            batch = paper_ids[i : i + BATCH_SIZE]
            papers = self._sch.get_papers(batch, fields=fields)
            results.extend(p for p in papers if p and p.paperId)
            if i + BATCH_SIZE < len(paper_ids):
                time.sleep(self._sleep)
        return results


def scrape(client: SemanticScholarClient, seed_id: str, max_depth: int, branching: int) -> Iterator[Edge]:
    """BFS by depth level, using batch API calls to fetch all neighbors at once."""
    visited: set[str] = {seed_id}
    current_level = [seed_id]

    for depth in range(max_depth):
        print(
            f"[depth {depth}] batch-fetching {len(current_level)} papers...",
            flush=True,
        )
        papers = client.get_papers_with_neighbors(current_level)
        next_level: list[str] = []

        for paper in papers:
            pid = paper.paperId

            for ref in (paper.references or [])[:branching]:
                if ref and ref.paperId:
                    yield (pid, ref.paperId)
                    if ref.paperId not in visited:
                        visited.add(ref.paperId)
                        next_level.append(ref.paperId)

            for cit in (paper.citations or [])[:branching]:
                if cit and cit.paperId:
                    yield (cit.paperId, pid)
                    if cit.paperId not in visited:
                        visited.add(cit.paperId)
                        next_level.append(cit.paperId)

        print(
            f"[depth {depth}] discovered {len(next_level)} new papers",
            flush=True,
        )
        current_level = next_level



# Output / Display

def load_rankings(path: str) -> list[tuple[int, str, float]]:
    rows: list[tuple[int, str, float]] = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append((int(r["Rank"]), r["PaperID"], float(r["Score"])))
    return rows


def format_entry(rank: int, score: float, paper) -> str:
    if not paper:
        return f"#{rank:2d}  [score={score:.4f}]  <metadata unavailable>"
    title = paper.title or "(untitled)"
    year = paper.year or "----"
    venue = paper.venue or ""
    authors = paper.authors or []
    first_author = authors[0].name if authors else "Unknown"
    extra_authors = f" et al. ({len(authors)})" if len(authors) > 1 else ""
    abstract = (paper.abstract or "").strip().replace("\n", " ")
    if len(abstract) > 280:
        abstract = abstract[:277] + "..."
    header = f"#{rank:2d}  [score={score:.4f}]  ({year})  {title}"
    byline = f"      {first_author}{extra_authors}"
    if venue:
        byline += f"  -  {venue}"
    body = f"      {abstract}" if abstract else ""
    return "\n".join(filter(None, [header, byline, body]))


# Main

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="PaperRec: citation-based paper recommendations.")
    p.add_argument("--seed", default=config.SEED_ID, help="Semantic Scholar paper ID")
    p.add_argument("--max-depth", type=int, default=config.MAX_DEPTH)
    p.add_argument("--max-branching", type=int, default=config.MAX_BRANCHING)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    client = SemanticScholarClient(
        branching=args.max_branching,
        sleep_seconds=config.REQUEST_SLEEP_SECONDS,
        timeout=config.REQUEST_TIMEOUT_SECONDS,
    )

    seed_id = client.resolve_id(args.seed)
    print(f"Resolved seed: {args.seed} -> {seed_id}", flush=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = os.path.join(config.OUTPUT_DIR, timestamp)
    os.makedirs(run_dir, exist_ok=True)
    print(f"Seed: {seed_id}", flush=True)
    print(f"Run dir: {run_dir}", flush=True)

    edges_path = os.path.join(run_dir, config.EDGES_CSV)
    ranked_path = os.path.join(run_dir, config.RANKED_CSV)

    # 1. Scrape
    count = 0
    with open(edges_path, "w", newline="", encoding="utf-8", buffering=1) as f:
        writer = csv.writer(f)
        writer.writerow(["Source", "Target"])
        for edge in scrape(client, seed_id, args.max_depth, args.max_branching):
            writer.writerow(edge)
            count += 1
    print(f"Wrote {count} edges to {edges_path}")

    # 2. Rank
    v, idx_to_id = math_engine.rank(edges_path, seed_id)
    order = math_engine.top_n(v, idx_to_id, config.TOP_N)

    with open(ranked_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Rank", "PaperID", "Score"])
        for rank, (pid, score) in enumerate(order, start=1):
            writer.writerow([rank, pid, f"{score:.8f}"])
    print(f"Wrote top {config.TOP_N} to {ranked_path}")

    # 3. Display
    rankings = load_rankings(ranked_path)
    paper_ids = [pid for _, pid, _ in rankings]
    by_id = client.get_papers(paper_ids)

    print("=" * 80)
    print(f" Personalized PageRank Reading List  (top {len(rankings)})")
    print(f" Run: {run_dir}")
    print("=" * 80)
    for rank, pid, score in rankings:
        print(format_entry(rank, score, by_id.get(pid)))
        print()


if __name__ == "__main__":
    main()
