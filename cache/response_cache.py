"""
In-Memory Normalized Query Response Cache for Naukri.com Domain Support Agent.
Track: Recruitment & HR Operations.

Task 16 Requirements:
- In-memory thread-safe LRU cache keyed by sanitized, normalized query strings.
- Normalization: lowercasing, whitespace collapsing, and trailing punctuation removal.
- Metrics tracking: hits, misses, hit ratio, total requests.
- Verification Command (Line 337): python cache/response_cache.py
  Expected Outcome: Hit verified with call counter & latency drop.
"""

from collections import OrderedDict
import re
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from schemas.response_models import SupportAgentResponse, create_support_agent_response


def normalize_query(query: str) -> str:
    """
    Normalizes user inquiry string for deterministic cache keying:
    1. Converts text to lowercase.
    2. Strips leading and trailing punctuation (? . ! , ; :) and whitespace.
    3. Collapses internal repeated whitespace.
    
    Example:
        '   What is the probation period duration?  ' -> 'what is the probation period duration'
    """
    text = query.strip().lower()
    # Strip trailing punctuation
    text = re.sub(r"[?!.,;:]+$", "", text).strip()
    # Collapse multiple whitespace characters into a single space
    text = re.sub(r"\s+", " ", text)
    return text


class NormalizedResponseCache:
    """
    Thread-safe in-memory Least Recently Used (LRU) response cache.
    Eliminates redundant multi-agent pipeline invocations on repeated inquiries.
    """

    def __init__(self, max_size: int = 256):
        self.max_size = max_size
        self._cache: OrderedDict[str, SupportAgentResponse] = OrderedDict()
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0

    def get(self, query: str) -> Optional[SupportAgentResponse]:
        """
        Retrieves cached SupportAgentResponse for normalized query.
        Returns None on cache miss.
        """
        key = normalize_query(query)
        with self._lock:
            if key in self._cache:
                self._hits += 1
                # Move to most recently used end
                self._cache.move_to_end(key)
                cached_obj = self._cache[key]
                # Return copy with cached=True flag
                copy_resp = cached_obj.model_copy(update={"cached": True})
                return copy_resp
            else:
                self._misses += 1
                return None

    def set(self, query: str, response: SupportAgentResponse) -> None:
        """
        Inserts or updates a cached response under its normalized key.
        Evicts oldest entry if max_size is exceeded.
        """
        key = normalize_query(query)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = response
            if len(self._cache) > self.max_size:
                # Evict oldest entry (FIFO in OrderedDict)
                self._cache.popitem(last=False)

    def clear(self) -> None:
        """Clears all cached responses and resets metric counters."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    def stats(self) -> Dict[str, Any]:
        """Returns runtime performance and hit-ratio metrics."""
        with self._lock:
            total = self._hits + self._misses
            ratio = (self._hits / total) if total > 0 else 0.0
            return {
                "hits": self._hits,
                "misses": self._misses,
                "total_requests": total,
                "hit_ratio": round(ratio, 4),
                "current_size": len(self._cache),
                "max_size": self.max_size,
            }


# Global Singleton Cache Instance
GLOBAL_RESPONSE_CACHE = NormalizedResponseCache(max_size=256)


def demonstrate_cache() -> None:
    """
    Demonstrates Task 16 verification requirements:
    1. Turn 1: Cold query executes multi-agent pipeline (Cache Miss).
    2. Turn 2: Equivalent inquiry with different casing and punctuation hits cache.
    3. Records call counters and latency drop.
    """
    from crew.recruitment_crew import run_recruitment_crew

    print("=" * 80)
    print("Task 16: Normalized Query Response Cache Demonstration")
    print("Track: Naukri.com Recruitment & HR Operations")
    print("=" * 80)

    cache = NormalizedResponseCache(max_size=64)

    raw_query_1 = "What is the probation period duration at Naukri.com?"
    print(f"\n1. First Query Execution (Cold Request): \"{raw_query_1}\"")
    print(f"   Normalized Key: \"{normalize_query(raw_query_1)}\"")

    start_1 = time.perf_counter()
    cached_1 = cache.get(raw_query_1)
    if cached_1 is None:
        print("   -> Cache MISS detected. Executing multi-agent Crew pipeline...")
        resp_1 = run_recruitment_crew(raw_query_1, verbose=False)
        duration_1 = (time.perf_counter() - start_1) * 1000
        cache.set(raw_query_1, resp_1)
        print(f"   <- Multi-Agent Pipeline Completed in {duration_1:.2f} ms")
        print(f"   Answer: {resp_1.final_answer[:90]}...")
    else:
        print("   -> Unexpected cache hit!")

    stats_after_1 = cache.stats()
    print(f"   Cache Stats after Turn 1: Hits={stats_after_1['hits']}, Misses={stats_after_1['misses']}, Size={stats_after_1['current_size']}")

    # Second equivalent query: extra spaces, lowercase, extra question marks
    raw_query_2 = "   what is the probation period duration at naukri.com???   "
    print(f"\n2. Second Query Execution (Equivalent Normalized Request): \"{raw_query_2}\"")
    print(f"   Normalized Key: \"{normalize_query(raw_query_2)}\"")

    start_2 = time.perf_counter()
    cached_2 = cache.get(raw_query_2)
    duration_2 = (time.perf_counter() - start_2) * 1000

    assert cached_2 is not None, "Expected cache HIT on second normalized query!"
    print(f"   -> Cache HIT verified!")
    print(f"   <- Served from In-Memory Cache in {duration_2:.4f} ms")
    print(f"   Latency Drop: {duration_1:.2f} ms -> {duration_2:.4f} ms (Speedup: {duration_1 / max(duration_2, 0.0001):.1f}x)")
    print(f"   Cached Flag : {cached_2.cached}")
    print(f"   Answer      : {cached_2.final_answer[:90]}...")

    stats_after_2 = cache.stats()
    print(f"\n3. Final Cache Metrics:")
    print(f"   Total Requests : {stats_after_2['total_requests']}")
    print(f"   Hits           : {stats_after_2['hits']}")
    print(f"   Misses         : {stats_after_2['misses']}")
    print(f"   Hit Ratio      : {stats_after_2['hit_ratio'] * 100:.1f}%")

    print("\n" + "=" * 80)
    print("Verification Result: Hit verified with call counter & latency drop.")
    print("=" * 80)


if __name__ == "__main__":
    demonstrate_cache()
