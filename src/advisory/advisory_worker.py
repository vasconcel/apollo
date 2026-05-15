"""
Advisory worker pipeline for APOLLO.

This module provides:
- Background advisory generation
- Rate limiting and throttling
- Retry logic with exponential backoff
- Progress tracking and persistence

This is the ONLY module that should invoke LLM generation.
UI modules must NEVER call LLM directly.
"""

import os
import sys
import time
import random
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime

from .advisory_models import (
    AdvisoryResult,
    AdvisoryConfig,
    AdvisoryRequest,
    AdvisoryDecision,
    CriterionEvaluation,
    QueueItem,
    AdvisoryStatus
)
from .advisory_queue import get_advisory_queue
from .advisory_cache import get_advisory_cache, store_advisory


class AdvisoryWorker:
    """
    Advisory generation worker.
    
    Processes queue items and generates advisories with:
    - Rate limiting
    - Exponential backoff
    - Retry logic
    - Progress persistence
    """
    
    def __init__(self, config: Optional[AdvisoryConfig] = None):
        self.config = config or AdvisoryConfig()
        self._llm = None
        self._protocol_criteria: Optional[Dict] = None
    
    @property
    def llm(self):
        """Lazy load LLM assistant."""
        if self._llm is None:
            try:
                from src.core.llm_assistant import get_llm_assistant
                self._llm = get_llm_assistant()
            except ImportError as e:
                print(f"Warning: LLM assistant not available: {e}")
                self._llm = None
        return self._llm
    
    def process_item(self, item: QueueItem) -> AdvisoryResult:
        """
        Process a single queue item.
        
        This is the main entry point for worker processing.
        """
        queue = get_advisory_queue(self.config)
        
        queue.mark_processing(item)
        
        request = AdvisoryRequest(
            cache_key=item.cache_key,
            protocol_version=item.protocol_version,
            title="",
            abstract="",
            literature_type="WL",
            metadata={"article_id": item.article_id}
        )
        
        advisory = self._generate_with_retry(request)
        
        store_advisory(advisory)
        
        if advisory.error and "failed" in advisory.error.lower():
            queue.mark_failed(item, advisory.error)
        else:
            queue.mark_completed(item)
        
        return advisory
    
    def _generate_with_retry(self, request: AdvisoryRequest) -> AdvisoryResult:
        """Generate advisory with retry logic."""
        last_error = None
        
        for attempt in range(self.config.max_retries + 1):
            try:
                advisory = self._generate_advisory(request)
                
                if advisory.error and "429" in advisory.error:
                    if attempt < self.config.max_retries:
                        backoff = self._calculate_backoff(attempt)
                        print(f"Rate limited, retrying in {backoff:.1f}s (attempt {attempt + 1}/{self.config.max_retries + 1})")
                        time.sleep(backoff)
                        continue
                
                return advisory
                
            except Exception as e:
                last_error = str(e)
                
                if attempt < self.config.max_retries:
                    backoff = self._calculate_backoff(attempt)
                    print(f"Error: {last_error}, retrying in {backoff:.1f}s")
                    time.sleep(backoff)
                else:
                    break
        
        return AdvisoryResult.create_failed(
            reason=last_error or "Max retries exceeded",
            cache_key=request.cache_key,
            protocol_version=request.protocol_version
        )
    
    def _generate_advisory(self, request: AdvisoryRequest) -> AdvisoryResult:
        """Generate advisory from LLM."""
        start_time = time.time()
        
        if not self.llm:
            return AdvisoryResult(
                cache_key=request.cache_key,
                protocol_version=request.protocol_version,
                decision=AdvisoryDecision.UNAVAILABLE,
                confidence=0.0,
                justification="LLM not available",
                error="LLM assistant not initialized",
                generated_at=datetime.utcnow().isoformat()
            )
        
        if not self.llm.is_available():
            return AdvisoryResult(
                cache_key=request.cache_key,
                protocol_version=request.protocol_version,
                decision=AdvisoryDecision.UNAVAILABLE,
                confidence=0.0,
                justification="LLM service unavailable",
                error="LLM not available",
                generated_at=datetime.utcnow().isoformat()
            )
        
        if self._protocol_criteria is None:
            self._protocol_criteria = self._load_protocol_criteria()
        
        title = request.title
        abstract = request.abstract
        literature_type = request.literature_type
        metadata = request.metadata
        
        try:
            suggestion = self.llm.suggest_ic(
                title=title,
                abstract=abstract,
                literature_type=literature_type,
                protocol_criteria=self._protocol_criteria,
                metadata=metadata
            )
            
            suggestion_dict = suggestion.to_dict()
            
            criterion_evaluations = []
            triggered_criteria = []
            
            if "criterion_evaluations" in suggestion_dict:
                for ce in suggestion_dict["criterion_evaluations"]:
                    criterion_evaluations.append(CriterionEvaluation(
                        criterion_id=ce.get("criterion_id", ""),
                        criterion_name=ce.get("criterion_name", ""),
                        satisfied=ce.get("satisfied", False),
                        evidence=ce.get("evidence", ""),
                        confidence=ce.get("confidence", 0.0)
                    ))
                    if ce.get("satisfied"):
                        triggered_criteria.append(ce.get("criterion_id", ""))
            
            decision = AdvisoryDecision(suggestion_dict.get("decision", "UNAVAILABLE"))
            
            duration_ms = (time.time() - start_time) * 1000
            
            return AdvisoryResult(
                cache_key=request.cache_key,
                protocol_version=request.protocol_version,
                decision=decision,
                confidence=suggestion_dict.get("confidence", 0.0),
                triggered_criteria=triggered_criteria,
                criterion_evaluations=criterion_evaluations,
                justification=suggestion_dict.get("justification", ""),
                generated_at=datetime.utcnow().isoformat(),
                generation_duration_ms=duration_ms
            )
            
        except Exception as e:
            return AdvisoryResult(
                cache_key=request.cache_key,
                protocol_version=request.protocol_version,
                decision=AdvisoryDecision.UNAVAILABLE,
                confidence=0.0,
                justification=f"Generation failed: {str(e)}",
                error=str(e),
                generated_at=datetime.utcnow().isoformat()
            )
    
    def _calculate_backoff(self, attempt: int) -> float:
        """Calculate exponential backoff with jitter."""
        base_backoff = self.config.backoff_base ** attempt
        capped_backoff = min(base_backoff, self.config.backoff_max)
        
        jitter_range = capped_backoff * self.config.jitter
        jitter = random.uniform(-jitter_range, jitter_range)
        
        return max(0.1, capped_backoff + jitter)
    
    def _load_protocol_criteria(self) -> Dict[str, str]:
        """Load protocol criteria."""
        try:
            from src.ui.modules.ic_screening_view import get_protocol_ic_criteria
            return get_protocol_ic_criteria()
        except ImportError:
            return {}
    
    def process_all(self, max_items: Optional[int] = None) -> Dict:
        """
        Process all pending queue items.
        
        Args:
            max_items: Maximum items to process (None for all)
            
        Returns:
            Processing summary
        """
        queue = get_advisory_queue(self.config)
        
        processed = 0
        succeeded = 0
        failed = 0
        
        while True:
            item = queue.get_next()
            if item is None:
                break
            
            if max_items is not None and processed >= max_items:
                break
            
            print(f"Processing: {item.article_id} ({item.cache_key[:8]}...)")
            
            result = self.process_item(item)
            processed += 1
            
            if result.error:
                failed += 1
                print(f"  Failed: {result.error}")
            else:
                succeeded += 1
                print(f"  Success: {result.decision.value} ({result.confidence:.2f})")
            
            if processed < (max_items or float('inf')):
                sleep_time = self.config.sleep_seconds
                time.sleep(sleep_time)
        
        return {
            "processed": processed,
            "succeeded": succeeded,
            "failed": failed,
            "remaining": queue.state.pending
        }
    
    def process_single(
        self,
        title: str,
        abstract: str,
        protocol_version: str = "1.0"
    ) -> AdvisoryResult:
        """
        Process a single article (standalone, not from queue).
        
        Useful for testing or on-demand generation.
        """
        cache = get_advisory_cache(self.config)
        cache_key = cache.compute_cache_key(title, abstract, protocol_version)
        
        if cache.has(cache_key, protocol_version):
            return cache.get(cache_key, protocol_version)
        
        request = AdvisoryRequest(
            cache_key=cache_key,
            protocol_version=protocol_version,
            title=title,
            abstract=abstract,
            literature_type="WL"
        )
        
        advisory = self._generate_with_retry(request)
        store_advisory(advisory)
        
        return advisory


def run_worker(
    max_items: Optional[int] = None,
    config: Optional[AdvisoryConfig] = None
) -> Dict:
    """
    Run advisory worker.
    
    Entry point for CLI: python advisory_worker.py
    """
    worker = AdvisoryWorker(config)
    return worker.process_all(max_items)


def generate_single_advisory(
    title: str,
    abstract: str,
    protocol_version: str = "1.0"
) -> AdvisoryResult:
    """
    Generate advisory for single article.
    
    Entry point for on-demand generation.
    """
    worker = AdvisoryWorker()
    return worker.process_single(title, abstract, protocol_version)


if __name__ == "__main__":
    max_items = None
    if len(sys.argv) > 1:
        try:
            max_items = int(sys.argv[1])
        except ValueError:
            pass
    
    print("=" * 60)
    print("APOLLO Advisory Worker")
    print("=" * 60)
    
    result = run_worker(max_items)
    
    print("=" * 60)
    print(f"Processing complete:")
    print(f"  Processed: {result['processed']}")
    print(f"  Succeeded: {result['succeeded']}")
    print(f"  Failed: {result['failed']}")
    print(f"  Remaining: {result['remaining']}")
    print("=" * 60)