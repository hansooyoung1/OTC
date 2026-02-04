"""
Pattern 1: Impulse → Stall → Snapback (A+ Pattern)

Detection (ALL required):
- ≥3 consecutive ticks in one direction
- Total movement ≥ minimum impulse distance
- Stall: No new high/low for 2-4 seconds
- Tick size contraction
- Tight price vibration
- No continuation breakout

Entry:
- Direction: opposite impulse
- Expiry: 5-15s
- Entry: first tick against impulse

Blocks:
- No stall → NO TRADE
- Stall > 6-7s → NO TRADE
- Whipsaw → NO TRADE
"""

import time
from .base_pattern import PatternBase, PatternResult, PatternType, TradeDirection
import sys
sys.path.insert(0, str(__file__).rsplit('src', 1)[0])
from config import PATTERN_CONFIG
from src.data.tick_buffer import TickBuffer


class ImpulseStallSnapback(PatternBase):
    """
    Detects impulse followed by stall with potential snapback.
    Maximum grade: A+
    """
    
    def __init__(self, tick_buffer: TickBuffer):
        super().__init__(tick_buffer)
        self._impulse_detected_time: float = 0.0
        self._impulse_direction: int = 0
        self._impulse_high: float = 0.0
        self._impulse_low: float = 0.0
        self._stall_start_time: float = 0.0
    
    @property
    def pattern_type(self) -> PatternType:
        return PatternType.IMPULSE_STALL_SNAPBACK
    
    @property
    def max_grade(self) -> str:
        return "A+"
    
    def detect(self) -> PatternResult:
        """Detect Impulse → Stall → Snapback pattern"""
        
        # Get recent consecutive ticks in same direction
        consecutive_ticks = self.tick_buffer.get_consecutive_direction_ticks()
        
        # Need minimum ticks for impulse
        if len(consecutive_ticks) < PATTERN_CONFIG.IMPULSE_MIN_TICKS:
            return self._no_pattern_result()
        
        # Calculate impulse distance
        impulse_distance = self.tick_buffer.calculate_impulse_distance(consecutive_ticks)
        
        if impulse_distance < PATTERN_CONFIG.IMPULSE_MIN_DISTANCE_PIPS * 0.0001:
            return self._no_pattern_result()
        
        impulse_direction = consecutive_ticks[0].direction
        
        # Record impulse detection
        now = time.time()
        
        # Get price extremes from impulse
        impulse_prices = [t.price for t in consecutive_ticks]
        impulse_high = max(impulse_prices)
        impulse_low = min(impulse_prices)
        
        # Check for stall phase
        # Look at ticks after the impulse
        recent_window_ticks = self.tick_buffer.get_ticks_in_window(
            PATTERN_CONFIG.STALL_MAX_DURATION_SEC + 2
        )
        
        # Separate impulse ticks from potential stall ticks
        impulse_end_time = consecutive_ticks[-1].timestamp
        stall_ticks = [t for t in recent_window_ticks if t.timestamp > impulse_end_time]
        
        if len(stall_ticks) < 2:
            return self._no_pattern_result("Insufficient stall ticks")
        
        # Calculate stall duration
        stall_duration = now - impulse_end_time
        
        # Block: Stall too short
        if stall_duration < PATTERN_CONFIG.STALL_MIN_DURATION_SEC:
            return self._no_pattern_result("Stall too short")
        
        # Block: Stall too long (momentum lost)
        if stall_duration > PATTERN_CONFIG.STALL_MAX_DURATION_SEC:
            return self._blocked_result(
                "Stall too long - momentum dissipated",
                self.pattern_type
            )
        
        # Check for no new high/low during stall
        stall_high = max(t.price for t in stall_ticks)
        stall_low = min(t.price for t in stall_ticks)
        
        if impulse_direction > 0:
            # Bullish impulse - no new high during stall
            if stall_high > impulse_high:
                return self._blocked_result(
                    "New high during stall - continuation not reversal",
                    self.pattern_type
                )
        else:
            # Bearish impulse - no new low during stall
            if stall_low < impulse_low:
                return self._blocked_result(
                    "New low during stall - continuation not reversal",
                    self.pattern_type
                )
        
        # Check tick size contraction (compression)
        impulse_avg_tick = sum(t.size for t in consecutive_ticks) / len(consecutive_ticks)
        stall_avg_tick = sum(t.size for t in stall_ticks if t.size > 0) / max(1, len([t for t in stall_ticks if t.size > 0]))
        
        if impulse_avg_tick == 0 or stall_avg_tick > impulse_avg_tick * PATTERN_CONFIG.STALL_MAX_TICK_SIZE_RATIO:
            # No compression - not a proper stall
            return self._no_pattern_result("No tick compression during stall")
        
        # Check for whipsaw (too much alternation during stall)
        stall_alternations = 0
        for i in range(1, len(stall_ticks)):
            if stall_ticks[i].direction != stall_ticks[i-1].direction:
                if stall_ticks[i].direction != 0 and stall_ticks[i-1].direction != 0:
                    stall_alternations += 1
        
        if stall_alternations > 4:
            return self._blocked_result("Whipsaw detected during stall", self.pattern_type)
        
        # Check for first tick against impulse (entry trigger)
        latest_tick = self.tick_buffer.latest_tick
        if latest_tick is None:
            return self._no_pattern_result()
        
        # Entry trigger: tick opposite to impulse direction
        if latest_tick.direction != -impulse_direction:
            return self._no_pattern_result("Waiting for reversal tick")
        
        # PATTERN DETECTED - Calculate scores
        
        # Pattern Quality Score (0-30)
        quality_score = 20  # Base for valid pattern
        
        # Bonus for textbook impulse size
        if len(consecutive_ticks) >= 5:
            quality_score += 4
        if impulse_distance > PATTERN_CONFIG.IMPULSE_MIN_DISTANCE_PIPS * 0.0001 * 1.5:
            quality_score += 3
        
        # Bonus for clean stall
        if stall_alternations <= 2:
            quality_score += 3
        
        quality_score = min(30, quality_score)
        
        # Tick Consistency Score (0-20)
        consistency_score = self._calculate_tick_consistency(consecutive_ticks, impulse_direction)
        
        # Volatility Quality Score (0-20)
        all_pattern_ticks = consecutive_ticks + stall_ticks
        volatility_score = self._calculate_volatility_quality(all_pattern_ticks, expect_compression=True)
        
        # Determine expiry based on stall duration
        if stall_duration < 3:
            recommended_expiry = 5
        elif stall_duration < 5:
            recommended_expiry = 10
        else:
            recommended_expiry = 15
        
        return PatternResult(
            detected=True,
            pattern_type=self.pattern_type,
            direction=self._get_opposite_direction(impulse_direction),
            pattern_quality_score=quality_score,
            tick_consistency_score=consistency_score,
            volatility_quality_score=volatility_score,
            recommended_expiry=recommended_expiry,
            entry_price=latest_tick.price,
            block_reason=None
        )
