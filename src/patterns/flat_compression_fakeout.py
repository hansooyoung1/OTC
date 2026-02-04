"""
Pattern 4: Flat Compression → Fakeout (A Pattern)

Detection:
- Tight range ≥5s
- Minimal movement
- Sudden breakout tick
- Immediate hesitation

Entry:
- Opposite breakout direction
- Expiry: 10-15s

Blocks:
- Breakout accelerates → NO TRADE
- No hesitation → NO TRADE
"""

import time
from .base_pattern import PatternBase, PatternResult, PatternType, TradeDirection
import sys
sys.path.insert(0, str(__file__).rsplit('src', 1)[0])
from config import PATTERN_CONFIG
from src.data.tick_buffer import TickBuffer


class FlatCompressionFakeout(PatternBase):
    """
    Detects flat compression followed by fakeout breakout.
    Maximum grade: A
    """
    
    def __init__(self, tick_buffer: TickBuffer):
        super().__init__(tick_buffer)
        self._compression_detected_time: float = 0.0
        self._compression_high: float = 0.0
        self._compression_low: float = 0.0
    
    @property
    def pattern_type(self) -> PatternType:
        return PatternType.FLAT_COMPRESSION_FAKEOUT
    
    @property
    def max_grade(self) -> str:
        return "A"
    
    def detect(self) -> PatternResult:
        """Detect Flat Compression → Fakeout pattern"""
        
        now = time.time()
        
        # Look for compression phase in recent history
        # We need at least 5 seconds of data
        compression_ticks = self.tick_buffer.get_ticks_in_window(
            PATTERN_CONFIG.COMPRESSION_MIN_DURATION_SEC + 3.0
        )
        
        if len(compression_ticks) < 10:
            return self._no_pattern_result()
        
        # Identify potential compression zone (before recent ticks)
        # Split: compression period vs potential breakout
        split_idx = max(5, len(compression_ticks) - 5)
        compression_zone = compression_ticks[:split_idx]
        recent_zone = compression_ticks[split_idx:]
        
        if len(compression_zone) < 5:
            return self._no_pattern_result()
        
        # Calculate compression range
        comp_prices = [t.price for t in compression_zone]
        comp_high = max(comp_prices)
        comp_low = min(comp_prices)
        comp_range = comp_high - comp_low
        
        # Check if range is tight enough
        if comp_range > PATTERN_CONFIG.COMPRESSION_MAX_RANGE_PIPS * 0.0001:
            return self._no_pattern_result("Range too wide for compression")
        
        # Check compression duration
        comp_duration = compression_zone[-1].timestamp - compression_zone[0].timestamp
        
        if comp_duration < PATTERN_CONFIG.COMPRESSION_MIN_DURATION_SEC:
            return self._no_pattern_result("Compression duration too short")
        
        # Check for minimal movement (low volatility during compression)
        comp_tick_sizes = [t.size for t in compression_zone if t.size > 0]
        if not comp_tick_sizes:
            return self._no_pattern_result()
        
        avg_comp_tick = sum(comp_tick_sizes) / len(comp_tick_sizes)
        
        # Now look for breakout in recent zone
        if len(recent_zone) < 2:
            return self._no_pattern_result()
        
        # Find the breakout tick (first tick outside compression range)
        breakout_tick = None
        breakout_direction = 0
        
        for tick in recent_zone:
            if tick.price > comp_high:
                breakout_tick = tick
                breakout_direction = 1  # Upward breakout
                break
            elif tick.price < comp_low:
                breakout_tick = tick
                breakout_direction = -1  # Downward breakout
                break
        
        if breakout_tick is None:
            return self._no_pattern_result("No breakout detected")
        
        # Check breakout size (should be significant)
        if breakout_tick.size < avg_comp_tick * 1.5:
            return self._no_pattern_result("Breakout too weak")
        
        # CRITICAL: Check for hesitation after breakout
        # Get ticks after the breakout
        breakout_idx = recent_zone.index(breakout_tick)
        post_breakout = recent_zone[breakout_idx + 1:] if breakout_idx < len(recent_zone) - 1 else []
        
        # Also check very recent ticks
        very_recent = self.tick_buffer.get_ticks_in_window(
            PATTERN_CONFIG.FAKEOUT_HESITATION_MAX_SEC
        )
        
        if len(post_breakout) < 1 and len(very_recent) < 2:
            return self._no_pattern_result("Waiting for post-breakout behavior")
        
        # Combine post-breakout ticks
        all_post = post_breakout + [t for t in very_recent if t not in post_breakout]
        
        if len(all_post) < 2:
            return self._no_pattern_result()
        
        # Check for hesitation: ticks should NOT continue in breakout direction
        continuation_ticks = sum(1 for t in all_post if t.direction == breakout_direction)
        reversal_ticks = sum(1 for t in all_post if t.direction == -breakout_direction)
        
        # Block: Breakout accelerates (genuine breakout, not fakeout)
        if continuation_ticks > len(all_post) * 0.6:
            return self._blocked_result(
                "Breakout accelerating - genuine breakout not fakeout",
                self.pattern_type
            )
        
        # Block: No hesitation detected
        if reversal_ticks < 1:
            return self._blocked_result(
                "No hesitation detected after breakout",
                self.pattern_type
            )
        
        # Check if price is returning toward compression zone
        latest_tick = self.tick_buffer.latest_tick
        if latest_tick is None:
            return self._no_pattern_result()
        
        # Fakeout confirmation: price should be heading back
        if breakout_direction > 0:
            # Upward breakout - price should be falling back
            if latest_tick.price > breakout_tick.price:
                return self._no_pattern_result("Price still above breakout - no fakeout yet")
        else:
            # Downward breakout - price should be rising back
            if latest_tick.price < breakout_tick.price:
                return self._no_pattern_result("Price still below breakout - no fakeout yet")
        
        # PATTERN DETECTED - Calculate scores
        
        # Pattern Quality Score (0-30)
        quality_score = 20  # Base for valid fakeout
        
        # Bonus for very tight compression
        if comp_range < PATTERN_CONFIG.COMPRESSION_MAX_RANGE_PIPS * 0.0001 * 0.5:
            quality_score += 4
        
        # Bonus for clean breakout followed by clear rejection
        if reversal_ticks >= 2:
            quality_score += 3
        
        # Bonus for compression duration
        if comp_duration >= PATTERN_CONFIG.COMPRESSION_MIN_DURATION_SEC * 1.5:
            quality_score += 3
        
        quality_score = min(30, quality_score)
        
        # Tick Consistency - expect reversal ticks
        consistency_score = self._calculate_tick_consistency(all_post, -breakout_direction)
        
        # Volatility Quality - compression followed by spike then compression
        volatility_score = 15  # Base - fakeouts have mixed volatility profile
        if len(all_post) >= 2:
            post_sizes = [t.size for t in all_post if t.size > 0]
            if post_sizes:
                avg_post = sum(post_sizes) / len(post_sizes)
                # After initial spike, volatility should decrease
                if avg_post < breakout_tick.size * 0.7:
                    volatility_score = 18
        
        # Expiry: medium for fakeout plays
        recommended_expiry = 10 if comp_duration < 7 else 15
        
        return PatternResult(
            detected=True,
            pattern_type=self.pattern_type,
            direction=self._get_opposite_direction(breakout_direction),
            pattern_quality_score=quality_score,
            tick_consistency_score=consistency_score,
            volatility_quality_score=volatility_score,
            recommended_expiry=recommended_expiry,
            entry_price=latest_tick.price,
            block_reason=None
        )
