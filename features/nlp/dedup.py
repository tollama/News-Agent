"""Near-duplicate detection using MinHash (datasketch)."""

from __future__ import annotations

from datasketch import MinHash, MinHashLSH


def _text_to_shingles(text: str, k: int = 3) -> set[str]:
    """Convert text to character-level k-shingles."""
    text = text.lower().strip()
    if len(text) < k:
        return {text}
    return {text[i : i + k] for i in range(len(text) - k + 1)}


def build_minhash(text: str, num_perm: int = 128) -> MinHash:
    """Build a MinHash signature for the given text."""
    m = MinHash(num_perm=num_perm)
    for shingle in _text_to_shingles(text):
        m.update(shingle.encode("utf-8"))
    return m


def find_duplicates(
    articles: list[dict[str, str]],
    threshold: float = 0.5,
    num_perm: int = 128,
) -> list[set[int]]:
    """Find near-duplicate clusters among articles by headline similarity.

    Args:
        articles: List of dicts with at least a "headline" key.
        threshold: Jaccard similarity threshold for duplicates.
        num_perm: Number of permutations for MinHash.

    Returns:
        List of sets, each containing indices of duplicate articles.
    """
    lsh = MinHashLSH(threshold=threshold, num_perm=num_perm)
    minhashes: dict[int, MinHash] = {}

    for idx, article in enumerate(articles):
        headline = article.get("headline", "")
        mh = build_minhash(headline, num_perm=num_perm)
        minhashes[idx] = mh
        try:
            lsh.insert(str(idx), mh)
        except ValueError:
            # Duplicate key — already similar to an existing entry
            pass

    # Build clusters
    visited: set[int] = set()
    clusters: list[set[int]] = []
    for idx, mh in minhashes.items():
        if idx in visited:
            continue
        result = lsh.query(mh)
        cluster = {int(r) for r in result}
        if len(cluster) > 1:
            clusters.append(cluster)
            visited.update(cluster)
        else:
            visited.add(idx)

    return clusters


def compute_novelty(article_index: int, clusters: list[set[int]]) -> float:
    """Compute novelty score (0-1) for an article based on cluster size.

    Novelty = 1.0 / cluster_size. Unique articles score 1.0.
    """
    for cluster in clusters:
        if article_index in cluster:
            return 1.0 / len(cluster)
    return 1.0


__all__ = ["build_minhash", "compute_novelty", "find_duplicates"]
