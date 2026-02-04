"""
Confidence Scoring Engine
Calculates final confidence score from pattern detection results.
Score Range: 0-100
Minimum tradable: 75 (A or A+)
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import sys
sys.path.insert(0, str(__file__).rsplit('src', 1)[0])
from config import CONFIDENCE_CONFIG, TIMING_CONFIG, SignalGrade
from src.patterns.base_pattern import PatternResult


@dataclass
class ConfidenceResult:
    """Final confidence calculation result"""
    total_score: int
    grade: SignalGrade
    
    # Component breakdown
    pattern_quality: int
    tick_consistency: int
    volatility_quality: int
    timing_bonus: int
    noise_penalty: int
    
    # Decision
    is_tradable: bool
    block_reason: Optional[str]
    
    def __str__(self) -> str:
        return (
            f"Confidence: {self.total_score}/100 [{self.grade.value}]\n"
            f"  Pattern: {self.pattern_quality}/30\n"
            f"  Ticks: {self.tick_consistency}/20\n"
            f"  Volatility: {self.volatility_quality}/20\n"
            f"  Timing: {self.timing_bonus}/15\n"
            f"  Noise: {self.noise_penalty}/15\n"
            f"  Tradable: {self.is_tradable}"
        )


class ConfidenceScorer:
    """
    Confidence scoring engine.
    Takes pattern detection result and applies full scoring logic.
    """
    
    def __init__(self):
        self._last_tick_time: float = 0.0
        self._tick_latencies: list = []
        self._max_latency_samples = 20
    
    def calculate(
        self,
        pattern_result: PatternResult,
        current_hour_utc: Optional[int] = None
    ) -> ConfidenceResult:
        """
        Calculate final confidence score.
        
        Formula:
        Confidence = Pattern Quality + Tick Consistency + Volatility Quality 
                   + Timing Bonus - Noise Penalty
        """
        
        # If pattern not detected or explicitly blocked
        if not pattern_result.detected:
            return self._blocked_result("No pattern detected")
        
        if pattern_result.is_blocked:
            return self._blocked_result(pattern_result.block_reason)
        
        # Get component scores from pattern
        pattern_quality = pattern_result.pattern_quality_score
        tick_consistency = pattern_result.tick_consistency_score
        volatility_quality = pattern_result.volatility_quality_score
        
        # Check component thresholds (hard blocks)
        if pattern_quality < CONFIDENCE_CONFIG.PATTERN_BLOCK_BELOW:
            return self._blocked_result(
                f"Pattern quality too low: {pattern_quality}/{CONFIDENCE_CONFIG.PATTERN_BLOCK_BELOW}"
            )
        
        if tick_consistency < CONFIDENCE_CONFIG.TICK_BLOCK_BELOW:
            return self._blocked_result(
                f"Tick consistency too low: {tick_consistency}/{CONFIDENCE_CONFIG.TICK_BLOCK_BELOW}"
            )
        
        if volatility_quality < CONFIDENCE_CONFIG.VOLATILITY_BLOCK_BELOW:
            return self._blocked_result(
                f"Volatility quality too low: {volatility_quality}/{CONFIDENCE_CONFIG.VOLATILITY_BLOCK_BELOW}"
            )
        
        # Calculate timing bonus
        timing_bonus = self._calculate_timing_bonus(current_hour_utc)
        
        # Calculate noise penalty
        noise_penalty = self._calculate_noise_penalty()
        
        # Calculate total score
        total_score = (
            pattern_quality +
            tick_consistency +
            volatility_quality +
            timing_bonus -
            noise_penalty
        )
        
        # Clamp to valid range
        total_score = max(0, min(100, total_score))
        
        # Determine grade
        grade = self._determine_grade(total_score)
        
        # Check if tradable
        is_tradable = total_score >= CONFIDENCE_CONFIG.MIN_TRADABLE_SCORE
        
        block_reason = None
        if not is_tradable:
            block_reason = f"Score {total_score} below minimum {CONFIDENCE_CONFIG.MIN_TRADABLE_SCORE}"
        
        return ConfidenceResult(
            total_score=total_score,
            grade=grade,
            pattern_quality=pattern_quality,
            tick_consistency=tick_consistency,
            volatility_quality=volatility_quality,
            timing_bonus=timing_bonus,
            noise_penalty=noise_penalty,
            is_tradable=is_tradable,
            block_reason=block_reason
        )
    
    def _calculate_timing_bonus(self, current_hour_utc: Optional[int] = None) -> int:
        """
        Calculate timing bonus based on known OTC hot/dead windows.
        Returns 0-15
        """
        if current_hour_utc is None:
            current_hour_utc = datetime.utcnow().hour
        
        # Check hot windows
        for start, end in TIMING_CONFIG.HOT_WINDOWS:
            if start <= current_hour_utc < end:
                return 12  # Strong bonus
        
        # Check dead windows
        for start, end in TIMING_CONFIG.DEAD_WINDOWS:
            if start <= current_hour_utc < end:
                return 0  # No bonus in dead period
        
        # Neutral time
        return 6
    
    def _calculate_noise_penalty(self) -> int:
        """
        Calculate noise penalty based on execution environment.
        Returns 0-15 (higher = more penalty)
        """
        penalty = 0
        
        # Check tick latency (if we have data)
        if self._tick_latencies:
            avg_latency = sum(self._tick_latencies) / len(self._tick_latencies)
            
            # Penalize high latency
            if avg_latency > 200:  # > 200ms
                penalty += 5
            elif avg_latency > 100:  # > 100ms
                penalty += 2
            
            # Check latency variance (jitter)
            if len(self._tick_latencies) >= 5:
                variance = sum((l - avg_latency) ** 2 for l in self._tick_latencies) / len(self._tick_latencies)
                if variance > 5000:  # High jitter
                    penalty += 4
                elif variance > 2000:
                    penalty += 2
        
        # Base environmental penalty (always assume some noise in OTC)
        penalty += 3
        
        return min(15, penalty)
    
    def _determine_grade(self, score: int) -> SignalGrade:
        """Determine grade from score"""
        if score >= CONFIDENCE_CONFIG.A_PLUS_THRESHOLD:
            return SignalGrade.A_PLUS
        elif score >= CONFIDENCE_CONFIG.MIN_TRADABLE_SCORE:
            return SignalGrade.A
        else:
            return SignalGrade.BLOCKED
    
    def _blocked_result(self, reason: str) -> ConfidenceResult:
        """Create a blocked (non-tradable) result"""
        return ConfidenceResult(
            total_score=0,
            grade=SignalGrade.BLOCKED,
            pattern_quality=0,
            tick_consistency=0,
            volatility_quality=0,
            timing_bonus=0,
            noise_penalty=0,
            is_tradable=False,
            block_reason=reason
        )
    
    def record_tick_latency(self, latency_ms: float):
        """Record observed tick latency for noise calculation"""
        self._tick_latencies.append(latency_ms)
        if len(self._tick_latencies) > self._max_latency_samples:
            self._tick_latencies.pop(0)
    
    def reset_latency_data(self):
        """Reset latency tracking"""
        self._tick_latencies.clear()
