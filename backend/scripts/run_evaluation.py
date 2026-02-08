#!/usr/bin/env python3
"""
RAG Evaluation Runner — compute retrieval metrics against a golden dataset.

Usage:
    python scripts/run_evaluation.py --baseline          # Save baseline metrics
    python scripts/run_evaluation.py --compare baseline  # Compare against saved baseline
    python scripts/run_evaluation.py --report            # Print metrics (no save)
    python scripts/run_evaluation.py --k 5               # Compute @5 instead of @10
"""
import argparse
import json
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.evaluation import (
    EvaluationService,
    GoldenDataset,
    compare_reports,
)


GOLDEN_DATASET_PATH = Path(__file__).parent.parent / "tests" / "evaluation" / "golden_dataset.json"
BASELINES_DIR = Path(__file__).parent.parent / "tests" / "evaluation" / "baselines"


def create_retrieval_pipeline():
    """
    Create a retrieval pipeline function for evaluation.

    Returns a function that takes a query string and returns a list of chunk IDs.
    """
    from app.services.embeddings import embedding_service
    from app.services.vector_store import vector_store_service

    def pipeline(query: str):
        query_embedding = embedding_service.embed_text(query)
        import numpy as np
        if isinstance(query_embedding, tuple):
            query_embedding = np.array(query_embedding, dtype=np.float32)

        chunks = vector_store_service.search_chunks(
            query_embedding=query_embedding,
            top_k=20,
        )
        return [str(c.chunk_id) for c in chunks if c.chunk_id]

    return pipeline


def save_baseline(report_dict: dict, name: str = "baseline"):
    """Save a report as a named baseline."""
    BASELINES_DIR.mkdir(parents=True, exist_ok=True)
    path = BASELINES_DIR / f"{name}.json"
    with open(path, "w") as f:
        json.dump(report_dict, f, indent=2)
    print(f"Baseline saved: {path}")


def load_baseline(name: str = "baseline") -> dict:
    """Load a named baseline."""
    path = BASELINES_DIR / f"{name}.json"
    if not path.exists():
        print(f"Baseline not found: {path}")
        sys.exit(1)
    with open(path, "r") as f:
        return json.load(f)


def print_report(report_dict: dict):
    """Pretty-print an evaluation report."""
    print("\n" + "=" * 60)
    print("RAG EVALUATION REPORT")
    print("=" * 60)
    print(f"Dataset version: {report_dict['dataset_version']}")
    print(f"Total queries: {report_dict['total_queries']}")
    print(f"K: {report_dict['k']}")

    print("\n--- Retrieval Metrics ---")
    ret = report_dict["retrieval"]
    print(f"  Recall@{report_dict['k']}:  {ret['avg_recall_at_k']:.4f}")
    print(f"  NDCG@{report_dict['k']}:   {ret['avg_ndcg_at_k']:.4f}")
    print(f"  MRR:        {ret['avg_mrr']:.4f}")

    print("\n--- Answer Quality ---")
    aq = report_dict["answer_quality"]
    print(f"  Faithfulness:  {aq['avg_faithfulness']:.4f}")
    print(f"  Relevance:     {aq['avg_relevance']:.4f}")
    print(f"  Completeness:  {aq['avg_completeness']:.4f}")

    print("\n--- Per-Query Results ---")
    for qr in report_dict.get("per_query", []):
        status = "OK" if not qr.get("error") else f"ERR: {qr['error']}"
        print(
            f"  {qr['id']}: recall={qr['recall']:.2f} ndcg={qr['ndcg']:.2f} "
            f"mrr={qr['mrr']:.2f} ({qr['relevant_found']}/{qr['retrieved']}) [{status}]"
        )
    print("=" * 60)


def print_comparison(deltas: dict):
    """Pretty-print a comparison between baseline and current."""
    print("\n" + "=" * 60)
    print("RAG EVALUATION COMPARISON")
    print("=" * 60)

    for section_name, section_data in deltas.items():
        print(f"\n--- {section_name.replace('_', ' ').title()} ---")
        for metric, vals in section_data.items():
            indicator = ""
            if vals["improved"]:
                indicator = " [IMPROVED]"
            elif vals["regressed"]:
                indicator = " [REGRESSED]"

            delta_sign = "+" if vals["delta"] >= 0 else ""
            print(
                f"  {metric}: {vals['baseline']:.4f} -> {vals['current']:.4f} "
                f"({delta_sign}{vals['delta']:.4f}){indicator}"
            )
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="RAG Evaluation Runner")
    parser.add_argument("--baseline", action="store_true", help="Save results as baseline")
    parser.add_argument("--baseline-name", default="baseline", help="Name for baseline file")
    parser.add_argument("--compare", type=str, help="Compare against named baseline")
    parser.add_argument("--report", action="store_true", help="Print metrics only")
    parser.add_argument("--k", type=int, default=10, help="Cutoff K for metrics")
    parser.add_argument("--dataset", type=str, help="Path to golden dataset JSON")
    parser.add_argument("--tags", nargs="+", help="Filter queries by tags")
    parser.add_argument("--difficulty", type=str, help="Filter by difficulty")

    args = parser.parse_args()

    # Load golden dataset
    dataset_path = args.dataset or str(GOLDEN_DATASET_PATH)
    print(f"Loading golden dataset: {dataset_path}")
    dataset = GoldenDataset.from_file(dataset_path)

    if args.tags:
        dataset = dataset.filter_by_tags(args.tags)
        print(f"Filtered to {len(dataset.queries)} queries with tags: {args.tags}")

    if args.difficulty:
        dataset = dataset.filter_by_difficulty(args.difficulty)
        print(f"Filtered to {len(dataset.queries)} queries with difficulty: {args.difficulty}")

    if not dataset.queries:
        print("No queries to evaluate. Check your golden dataset and filters.")
        sys.exit(1)

    # Create pipeline and run evaluation
    print(f"Running evaluation with K={args.k} on {len(dataset.queries)} queries...")
    pipeline = create_retrieval_pipeline()
    svc = EvaluationService()
    report = svc.evaluate_retrieval(dataset, pipeline, k=args.k)
    report_dict = report.to_dict()

    # Print report
    print_report(report_dict)

    # Save baseline if requested
    if args.baseline:
        save_baseline(report_dict, args.baseline_name)

    # Compare if requested
    if args.compare:
        baseline_data = load_baseline(args.compare)
        deltas = compare_reports(baseline_data, report_dict)
        print_comparison(deltas)


if __name__ == "__main__":
    main()
