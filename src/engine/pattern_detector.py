"""
Pattern Detector
Orchestrates all pattern detectors and returns best match.
"""

from typing import List, Optional
from dataclasses import dataclass
import sys
sys.path.insert(0, str(__file__).rsplit('src', 1)[0])
from src.data.tick_buffer import TickBuffer
from src.patterns.base_pattern import PatternBase, PatternResult, PatternType
from src.patterns.impulse_stall_snapback import ImpulseStallSnapback
from src.patterns.micro_double_top_bottom import MicroDoubleTopBottom
from src.patterns.tick_momentum_exhaustion import TickMomentumExhaustion
from src.patterns.flat_compression_fakeout import FlatCompressionFakeout


@dataclass
class DetectionResult:
    """Result of pattern detection across all detectors"""
    best_pattern: Optional[PatternResult]
    all_detections: List[PatternResult]
    patterns_checked: int
    patterns_detected: int
    
    @property
    def has_detection(self) -> bool:
        return self.best_pattern is not None and self.best_pattern.detected


class PatternDetector:
    """
    Master pattern detector.
    Runs all pattern detectors and selects the best match.
    """
    
    def __init__(self, tick_buffer: TickBuffer):
        self.tick_buffer = tick_buffer
        
        # Initialize all pattern detectors
        self._detectors: List[PatternBase] = [
            ImpulseStallSnapback(tick_buffer),  # A+ capable
            MicroDoubleTopBottom(tick_buffer),   # A+ capable
            TickMomentumExhaustion(tick_buffer), # A only
            FlatCompressionFakeout(tick_buffer), # A only
        ]
    
    def detect(self) -> DetectionResult:
        """
        Run all pattern detectors and return best result.
        Selection priority:
        1. Higher base score
        2. Higher max grade capability (A+ > A)
        3. First detected if tie
        """
        
        all_results: List[PatternResult] = []
        
        for detector in self._detectors:
            result = detector.detect()
            all_results.append(result)
        
        # Filter to only detected patterns (not blocked)
        detected = [r for r in all_results if r.detected and not r.is_blocked]
        
        patterns_detected = len(detected)
        patterns_checked = len(self._detectors)
        
        if not detected:
            return DetectionResult(
                best_pattern=None,
                all_detections=all_results,
                patterns_checked=patterns_checked,
                patterns_detected=0
            )
        
        # Sort by base score (higher is better)
        detected.sort(key=lambda r: r.base_score, reverse=True)
        
        # Additional sorting: prefer A+ capable patterns if scores are close
        best = detected[0]
        for result in detected[1:]:
            score_diff = best.base_score - result.base_score
            if score_diff <= 3:  # Close scores
                # Check if result is from A+ capable pattern
                if result.pattern_type in [
                    PatternType.IMPULSE_STALL_SNAPBACK,
                    PatternType.MICRO_DOUBLE_TOP,
                    PatternType.MICRO_DOUBLE_BOTTOM
                ]:
                    if best.pattern_type in [
                        PatternType.TICK_MOMENTUM_EXHAUSTION,
                        PatternType.FLAT_COMPRESSION_FAKEOUT
                    ]:
                        best = result  # Prefer A+ capable
        
        return DetectionResult(
            best_pattern=best,
            all_detections=all_results,
            patterns_checked=patterns_checked,
            patterns_detected=patterns_detected
        )
    
    def detect_specific(self, pattern_type: PatternType) -> Optional[PatternResult]:
        """
        Run a specific pattern detector only.
        Useful for testing or targeted detection.
        """
        for detector in self._detectors:
            if detector.pattern_type == pattern_type:
                return detector.detect()
            # Handle double top/bottom variants
            if pattern_type == PatternType.MICRO_DOUBLE_TOP and isinstance(detector, MicroDoubleTopBottom):
                return detector.detect()
            if pattern_type == PatternType.MICRO_DOUBLE_BOTTOM and isinstance(detector, MicroDoubleTopBottom):
                return detector.detect()
        
        return None
    
    def get_detector_status(self) -> dict:
        """Get status of all detectors"""
        return {
            d.pattern_type.value: {
                "max_grade": d.max_grade,
                "active": True
            }
            for d in self._detectors
        }
