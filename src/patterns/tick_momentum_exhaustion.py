"""
Pattern 3: Tick Momentum Exhaustion (A Pattern - only when combined)

Detection:
- ≥4 ticks same direction
- Each tick smaller than previous
- Speed visibly slows

Entry:
- Opposite direction
- Expiry: 5-10s
- On smallest tick

Blocks:
- Tick size increases → NO TRADE
- Volatility spike → NO TRADE
"""

import time
from .base_pattern import PatternBase, PatternResult, PatternType, TradeDirection
import sys
sys.path.insert(0, str(__file__).rsplit('src', 1)[0])
from config import PATTERN_CONFIG
from src.data.tick_buffer import TickBuffer


class TickMomentumExhaustion(PatternBase):
    """
    Detects momentum exhaustion through decreasing tick sizes.
    Maximum grade: A (only when combined with other factors)
    """
    
    def __init__(self, tick_buffer: TickBuffer):
        super().__init__(tick_buffer)
    
    @property
    def pattern_type(self) -> PatternType:
        return PatternType.TICK_MOMENTUM_EXHAUSTION
    
    @property
    def max_grade(self) -> str:
        return "A"  # Only A, not A+ as standalone
    
    def detect(self) -> PatternResult:
        """Detect Tick Momentum Exhaustion pattern"""
        
        # Get consecutive ticks in same direction
        consecutive_ticks = self.tick_buffer.get_consecutive_direction_ticks()
        
        # Minimum ticks requirement
        if len(consecutive_ticks) < PATTERN_CONFIG.EXHAUSTION_MIN_TICKS:
            return self._no_pattern_result()
        
        momentum_direction = consecutive_ticks[0].direction
        
        if momentum_direction == 0:
            return self._no_pattern_result()
        
        # Check for decreasing tick sizes (exhaustion signature)
        tick_sizes = [t.size for t in consecutive_ticks if t.size > 0]
        
        if len(tick_sizes) < PATTERN_CONFIG.EXHAUSTION_MIN_TICKS:
            return self._no_pattern_result()
        
        # Verify each tick is smaller than previous
        decay_count = 0
        increase_count = 0
        
        for i in range(1, len(tick_sizes)):
            ratio = tick_sizes[i] / tick_sizes[i-1] if tick_sizes[i-1] > 0 else 1.0
            
            if ratio < PATTERN_CONFIG.EXHAUSTION_TICK_DECAY_RATIO:
                decay_count += 1
            elif ratio > 1.0:
                increase_count += 1
        
        # Block: Tick size increases detected
        if increase_count > 0:
            return self._blocked_result(
                "Tick size increasing - momentum not exhausted",
                self.pattern_type
            )
        
        # Need consistent decay
        min_decay_needed = len(tick_sizes) - 2  # Allow one non-decay
        if decay_count < min_decay_needed:
            return self._no_pattern_result("Insufficient tick decay")
        
        # Check for speed slowing
        recent_ticks = self.tick_buffer.get_recent_ticks(10)
        if len(recent_ticks) >= 6:
            first_half = recent_ticks[:len(recent_ticks)//2]
            second_half = recent_ticks[len(recent_ticks)//2:]
            
            # Calculate time between ticks
            if len(first_half) >= 2 and len(second_half) >= 2:
                first_span = first_half[-1].timestamp - first_half[0].timestamp
                second_span = second_half[-1].timestamp - second_half[0].timestamp
                
                first_rate = len(first_half) / first_span if first_span > 0 else 0
                second_rate = len(second_half) / second_span if second_span > 0 else 0
                
                # Second half should be slower
                if first_rate > 0 and second_rate > first_rate:
                    return self._no_pattern_result("Speed not slowing")
        
        # Check for volatility spike (blocks the pattern)
        if self.tick_buffer.detect_volatility_spike():
            return self._blocked_result(
                "Volatility spike detected",
                self.pattern_type
            )
        
        # Check for entry trigger: at or near smallest tick
        latest_tick = self.tick_buffer.latest_tick
        if latest_tick is None:
            return self._no_pattern_result()
        
        # Latest tick should be one of the smallest
        avg_recent_size = sum(tick_sizes[-3:]) / 3 if len(tick_sizes) >= 3 else tick_sizes[-1]
        avg_early_size = sum(tick_sizes[:3]) / 3 if len(tick_sizes) >= 3 else tick_sizes[0]
        
        # Significant exhaustion check
        if avg_early_size > 0:
            exhaustion_ratio = avg_recent_size / avg_early_size
            if exhaustion_ratio > 0.6:  # Not enough exhaustion
                return self._no_pattern_result("Insufficient exhaustion depth")
        
        # PATTERN DETECTED - Calculate scores
        
        # Pattern Quality Score (0-30)
        quality_score = 18  # Base (lower for standalone)
        
        # Bonus for strong exhaustion
        if decay_count >= len(tick_sizes) - 1:
            quality_score += 4  # Perfect decay
        
        # Bonus for long sequence
        if len(consecutive_ticks) >= 6:
            quality_score += 3
        
        # Bonus for clear speed slowdown
        if len(recent_ticks) >= 6:
            early_speed = self.tick_buffer.get_tick_speed(3)
            late_speed = len(recent_ticks[-3:]) / (recent_ticks[-1].timestamp - recent_ticks[-3].timestamp + 0.001)
            if early_speed > 0 and late_speed < early_speed * 0.7:
                quality_score += 3
        
        quality_score = min(30, quality_score)
        
        # Tick Consistency Score - all same direction
        consistency_score = self._calculate_tick_consistency(consecutive_ticks, momentum_direction)
        
        # Volatility Quality Score - expect decreasing
        volatility_score = self._calculate_volatility_quality(consecutive_ticks, expect_compression=True)
        
        # Expiry: short for exhaustion plays
        if len(consecutive_ticks) >= 6:
            recommended_expiry = 10
        else:
            recommended_expiry = 5
        
        return PatternResult(
            detected=True,
            pattern_type=self.pattern_type,
            direction=self._get_opposite_direction(momentum_direction),
            pattern_quality_score=quality_score,
            tick_consistency_score=consistency_score,
            volatility_quality_score=volatility_score,
            recommended_expiry=recommended_expiry,
            entry_price=latest_tick.price,
            block_reason=None
        )
