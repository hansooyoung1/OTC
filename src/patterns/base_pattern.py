"""
Base Pattern Module
Abstract base class for all OTC micro-pattern detectors.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple
import sys
sys.path.insert(0, str(__file__).rsplit('src', 1)[0])
from src.data.tick_buffer import TickBuffer, Tick


class PatternType(Enum):
    """Supported pattern types"""
    IMPULSE_STALL_SNAPBACK = "IMPULSE_STALL_SNAPBACK"
    MICRO_DOUBLE_TOP = "MICRO_DOUBLE_TOP"
    MICRO_DOUBLE_BOTTOM = "MICRO_DOUBLE_BOTTOM"
    TICK_MOMENTUM_EXHAUSTION = "TICK_MOMENTUM_EXHAUSTION"
    FLAT_COMPRESSION_FAKEOUT = "FLAT_COMPRESSION_FAKEOUT"
    NONE = "NONE"


class TradeDirection(Enum):
    """Trade direction"""
    CALL = "CALL"
    PUT = "PUT"
    NONE = "NONE"


@dataclass
class PatternResult:
    """Result of pattern detection"""
    detected: bool
    pattern_type: PatternType
    direction: TradeDirection
    pattern_quality_score: int  # 0-30
    tick_consistency_score: int  # 0-20
    volatility_quality_score: int  # 0-20
    recommended_expiry: int  # seconds
    entry_price: Optional[float]
    block_reason: Optional[str] = None
    
    @property
    def is_blocked(self) -> bool:
        return self.block_reason is not None
    
    @property
    def base_score(self) -> int:
        """Sum of pattern-specific scores (max 70)"""
        return (
            self.pattern_quality_score +
            self.tick_consistency_score +
            self.volatility_quality_score
        )


class PatternBase(ABC):
    """Abstract base class for pattern detection"""
    
    def __init__(self, tick_buffer: TickBuffer):
        self.tick_buffer = tick_buffer
    
    @property
    @abstractmethod
    def pattern_type(self) -> PatternType:
        """Return the pattern type this detector handles"""
        pass
    
    @property
    @abstractmethod
    def max_grade(self) -> str:
        """Return maximum possible grade (A or A+)"""
        pass
    
    @abstractmethod
    def detect(self) -> PatternResult:
        """
        Detect if the pattern is currently present.
        Returns PatternResult with all scoring components.
        """
        pass
    
    def _no_pattern_result(self, reason: Optional[str] = None) -> PatternResult:
        """Helper to create a non-detection result"""
        return PatternResult(
            detected=False,
            pattern_type=PatternType.NONE,
            direction=TradeDirection.NONE,
            pattern_quality_score=0,
            tick_consistency_score=0,
            volatility_quality_score=0,
            recommended_expiry=0,
            entry_price=None,
            block_reason=reason
        )
    
    def _blocked_result(self, reason: str, pattern_type: PatternType) -> PatternResult:
        """Helper to create a blocked result (pattern seen but blocked)"""
        return PatternResult(
            detected=True,
            pattern_type=pattern_type,
            direction=TradeDirection.NONE,
            pattern_quality_score=0,
            tick_consistency_score=0,
            volatility_quality_score=0,
            recommended_expiry=0,
            entry_price=None,
            block_reason=reason
        )
    
    def _calculate_tick_consistency(self, ticks: List[Tick], expected_direction: int) -> int:
        """
        Calculate tick consistency score.
        How well do ticks align with expected pattern behavior?
        """
        if not ticks:
            return 0
        
        aligned_count = sum(1 for t in ticks if t.direction == expected_direction)
        alignment_ratio = aligned_count / len(ticks)
        
        # Score based on alignment
        if alignment_ratio >= 0.8:
            return 20  # Strong alignment
        elif alignment_ratio >= 0.6:
            return 15
        elif alignment_ratio >= 0.4:
            return 10
        else:
            return 5  # Poor alignment
    
    def _calculate_volatility_quality(self, ticks: List[Tick], expect_compression: bool = False) -> int:
        """
        Calculate volatility quality score.
        Compression after impulse is good. Random spikes are bad.
        """
        if not ticks or len(ticks) < 3:
            return 10
        
        recent_sizes = [t.size for t in ticks[-5:] if t.size > 0]
        older_sizes = [t.size for t in ticks[:-5] if t.size > 0]
        
        if not recent_sizes or not older_sizes:
            return 10
        
        recent_avg = sum(recent_sizes) / len(recent_sizes)
        older_avg = sum(older_sizes) / len(older_sizes)
        
        if older_avg == 0:
            return 10
        
        ratio = recent_avg / older_avg
        
        if expect_compression:
            # Want volatility to decrease (compression)
            if ratio < 0.5:
                return 20  # Good compression
            elif ratio < 0.8:
                return 15
            elif ratio < 1.2:
                return 10
            else:
                return 5  # Volatility expanding - bad
        else:
            # Want stable volatility
            if 0.7 <= ratio <= 1.3:
                return 18
            elif 0.5 <= ratio <= 1.5:
                return 12
            else:
                return 6
    
    def _get_opposite_direction(self, direction: int) -> TradeDirection:
        """Convert tick direction to opposite trade direction"""
        if direction > 0:
            return TradeDirection.PUT  # Opposite of up impulse
        elif direction < 0:
            return TradeDirection.CALL  # Opposite of down impulse
        return TradeDirection.NONE
    
    def _get_same_direction(self, direction: int) -> TradeDirection:
        """Convert tick direction to same trade direction"""
        if direction > 0:
            return TradeDirection.CALL
        elif direction < 0:
            return TradeDirection.PUT
        return TradeDirection.NONE
