"""
Pattern 2: Micro Double-Top / Double-Bottom (A / A+ Pattern)

Detection:
- Price hits level
- Small pullback
- Retest within 3-10s
- Second push weaker/slower

Entry:
- Reversal direction
- Expiry: 10-30s
- Entry on failure to break level

Blocks:
- Clean break → NO TRADE
- Retest > 10s → NO TRADE
- Rising volatility → NO TRADE
"""

import time
from .base_pattern import PatternBase, PatternResult, PatternType, TradeDirection
import sys
sys.path.insert(0, str(__file__).rsplit('src', 1)[0])
from config import PATTERN_CONFIG
from src.data.tick_buffer import TickBuffer


class MicroDoubleTopBottom(PatternBase):
    """
    Detects micro double-top or double-bottom formations.
    Maximum grade: A+
    """
    
    def __init__(self, tick_buffer: TickBuffer):
        super().__init__(tick_buffer)
        self._first_touch_price: float = 0.0
        self._first_touch_time: float = 0.0
        self._first_touch_direction: int = 0  # 1 = high (double top), -1 = low (double bottom)
    
    @property
    def pattern_type(self) -> PatternType:
        return PatternType.MICRO_DOUBLE_TOP  # Will be set dynamically
    
    @property
    def max_grade(self) -> str:
        return "A+"
    
    def detect(self) -> PatternResult:
        """Detect Micro Double-Top or Double-Bottom pattern"""
        
        # Get ticks for analysis window
        analysis_ticks = self.tick_buffer.get_ticks_in_window(15.0)  # 15 second window
        
        if len(analysis_ticks) < 10:
            return self._no_pattern_result()
        
        # Find potential first touch (local extreme)
        prices = [t.price for t in analysis_ticks]
        local_high = max(prices)
        local_low = min(prices)
        
        # Find first touch index
        high_idx = prices.index(local_high)
        low_idx = prices.index(local_low)
        
        # Try both double-top and double-bottom
        double_top_result = self._detect_double_top(analysis_ticks, local_high, high_idx)
        double_bottom_result = self._detect_double_bottom(analysis_ticks, local_low, low_idx)
        
        # Return the higher quality detection
        if double_top_result.detected and double_bottom_result.detected:
            if double_top_result.base_score >= double_bottom_result.base_score:
                return double_top_result
            return double_bottom_result
        elif double_top_result.detected:
            return double_top_result
        elif double_bottom_result.detected:
            return double_bottom_result
        
        return self._no_pattern_result()
    
    def _detect_double_top(self, ticks, local_high: float, high_idx: int) -> PatternResult:
        """Detect double-top pattern"""
        
        if high_idx < 3 or high_idx > len(ticks) - 5:
            return self._no_pattern_result()
        
        first_touch = ticks[high_idx]
        first_touch_time = first_touch.timestamp
        
        # Look for pullback after first touch
        pullback_ticks = ticks[high_idx+1:min(high_idx+8, len(ticks))]
        
        if len(pullback_ticks) < 2:
            return self._no_pattern_result()
        
        pullback_low = min(t.price for t in pullback_ticks)
        pullback_depth = local_high - pullback_low
        
        # Minimum pullback requirement
        if pullback_depth < PATTERN_CONFIG.DOUBLE_MIN_PULLBACK_PIPS * 0.0001:
            return self._no_pattern_result("Pullback too shallow")
        
        # Look for retest (second touch)
        retest_start_idx = high_idx + len(pullback_ticks)
        if retest_start_idx >= len(ticks):
            return self._no_pattern_result()
        
        retest_ticks = ticks[retest_start_idx:]
        
        if len(retest_ticks) < 2:
            return self._no_pattern_result()
        
        # Find second high
        retest_high = max(t.price for t in retest_ticks)
        retest_high_idx = [t.price for t in retest_ticks].index(retest_high)
        second_touch = retest_ticks[retest_high_idx]
        
        # Check retest timing
        retest_time = second_touch.timestamp - first_touch_time
        
        if retest_time < PATTERN_CONFIG.DOUBLE_RETEST_MIN_SEC:
            return self._no_pattern_result("Retest too fast")
        
        if retest_time > PATTERN_CONFIG.DOUBLE_RETEST_MAX_SEC:
            return self._blocked_result(
                "Retest too slow - pattern expired",
                PatternType.MICRO_DOUBLE_TOP
            )
        
        # Check level tolerance
        level_diff = abs(retest_high - local_high)
        if level_diff > PATTERN_CONFIG.DOUBLE_LEVEL_TOLERANCE_PIPS * 0.0001:
            return self._no_pattern_result("Levels not aligned")
        
        # Check if second push is weaker
        # Compare tick sizes and speed
        first_push_ticks = ticks[max(0, high_idx-3):high_idx+1]
        second_push_ticks = retest_ticks[:retest_high_idx+1]
        
        if len(first_push_ticks) > 0 and len(second_push_ticks) > 0:
            first_push_strength = sum(t.size for t in first_push_ticks)
            second_push_strength = sum(t.size for t in second_push_ticks)
            
            # Second push should be weaker
            if second_push_strength > first_push_strength * PATTERN_CONFIG.DOUBLE_SECOND_PUSH_WEAKER_RATIO:
                # Check if it broke through (continuation)
                if retest_high > local_high + PATTERN_CONFIG.DOUBLE_LEVEL_TOLERANCE_PIPS * 0.0001:
                    return self._blocked_result(
                        "Clean break - continuation not reversal",
                        PatternType.MICRO_DOUBLE_TOP
                    )
        
        # Check for failure to break (entry trigger)
        latest_tick = self.tick_buffer.latest_tick
        if latest_tick is None:
            return self._no_pattern_result()
        
        # Need price to start falling away from the level
        recent_ticks = self.tick_buffer.get_ticks_in_window(1.5)
        if len(recent_ticks) < 2:
            return self._no_pattern_result()
        
        down_ticks = sum(1 for t in recent_ticks if t.direction < 0)
        if down_ticks < len(recent_ticks) * 0.5:
            return self._no_pattern_result("Waiting for rejection confirmation")
        
        # Check volatility not rising
        avg_recent_vol = self.tick_buffer.get_average_tick_size(10)
        avg_old_vol = self.tick_buffer.get_average_tick_size(30)
        
        if avg_old_vol > 0 and avg_recent_vol > avg_old_vol * 1.5:
            return self._blocked_result(
                "Rising volatility during pattern",
                PatternType.MICRO_DOUBLE_TOP
            )
        
        # PATTERN DETECTED - Calculate scores
        
        # Pattern Quality Score
        quality_score = 22  # Base
        
        # Bonus for textbook formation
        if level_diff < PATTERN_CONFIG.DOUBLE_LEVEL_TOLERANCE_PIPS * 0.0001 * 0.5:
            quality_score += 4  # Very precise level
        
        if PATTERN_CONFIG.DOUBLE_RETEST_MIN_SEC + 2 <= retest_time <= PATTERN_CONFIG.DOUBLE_RETEST_MAX_SEC - 2:
            quality_score += 4  # Ideal timing
        
        quality_score = min(30, quality_score)
        
        # Tick Consistency
        consistency_score = self._calculate_tick_consistency(recent_ticks, -1)  # Expect down
        
        # Volatility Quality
        volatility_score = self._calculate_volatility_quality(ticks)
        
        # Expiry based on pattern timing
        if retest_time < 5:
            recommended_expiry = 10
        elif retest_time < 8:
            recommended_expiry = 15
        else:
            recommended_expiry = 30
        
        return PatternResult(
            detected=True,
            pattern_type=PatternType.MICRO_DOUBLE_TOP,
            direction=TradeDirection.PUT,  # Reversal from top
            pattern_quality_score=quality_score,
            tick_consistency_score=consistency_score,
            volatility_quality_score=volatility_score,
            recommended_expiry=recommended_expiry,
            entry_price=latest_tick.price,
            block_reason=None
        )
    
    def _detect_double_bottom(self, ticks, local_low: float, low_idx: int) -> PatternResult:
        """Detect double-bottom pattern"""
        
        if low_idx < 3 or low_idx > len(ticks) - 5:
            return self._no_pattern_result()
        
        first_touch = ticks[low_idx]
        first_touch_time = first_touch.timestamp
        
        # Look for pullback after first touch (bounce up)
        pullback_ticks = ticks[low_idx+1:min(low_idx+8, len(ticks))]
        
        if len(pullback_ticks) < 2:
            return self._no_pattern_result()
        
        pullback_high = max(t.price for t in pullback_ticks)
        pullback_depth = pullback_high - local_low
        
        if pullback_depth < PATTERN_CONFIG.DOUBLE_MIN_PULLBACK_PIPS * 0.0001:
            return self._no_pattern_result("Pullback too shallow")
        
        # Look for retest
        retest_start_idx = low_idx + len(pullback_ticks)
        if retest_start_idx >= len(ticks):
            return self._no_pattern_result()
        
        retest_ticks = ticks[retest_start_idx:]
        
        if len(retest_ticks) < 2:
            return self._no_pattern_result()
        
        # Find second low
        retest_low = min(t.price for t in retest_ticks)
        retest_low_idx = [t.price for t in retest_ticks].index(retest_low)
        second_touch = retest_ticks[retest_low_idx]
        
        # Check retest timing
        retest_time = second_touch.timestamp - first_touch_time
        
        if retest_time < PATTERN_CONFIG.DOUBLE_RETEST_MIN_SEC:
            return self._no_pattern_result("Retest too fast")
        
        if retest_time > PATTERN_CONFIG.DOUBLE_RETEST_MAX_SEC:
            return self._blocked_result(
                "Retest too slow - pattern expired",
                PatternType.MICRO_DOUBLE_BOTTOM
            )
        
        # Check level tolerance
        level_diff = abs(retest_low - local_low)
        if level_diff > PATTERN_CONFIG.DOUBLE_LEVEL_TOLERANCE_PIPS * 0.0001:
            return self._no_pattern_result("Levels not aligned")
        
        # Check if second push is weaker
        first_push_ticks = ticks[max(0, low_idx-3):low_idx+1]
        second_push_ticks = retest_ticks[:retest_low_idx+1]
        
        if len(first_push_ticks) > 0 and len(second_push_ticks) > 0:
            first_push_strength = sum(t.size for t in first_push_ticks)
            second_push_strength = sum(t.size for t in second_push_ticks)
            
            if second_push_strength > first_push_strength * PATTERN_CONFIG.DOUBLE_SECOND_PUSH_WEAKER_RATIO:
                if retest_low < local_low - PATTERN_CONFIG.DOUBLE_LEVEL_TOLERANCE_PIPS * 0.0001:
                    return self._blocked_result(
                        "Clean break - continuation not reversal",
                        PatternType.MICRO_DOUBLE_BOTTOM
                    )
        
        # Check for failure to break (entry trigger)
        latest_tick = self.tick_buffer.latest_tick
        if latest_tick is None:
            return self._no_pattern_result()
        
        # Need price to start rising away from the level
        recent_ticks = self.tick_buffer.get_ticks_in_window(1.5)
        if len(recent_ticks) < 2:
            return self._no_pattern_result()
        
        up_ticks = sum(1 for t in recent_ticks if t.direction > 0)
        if up_ticks < len(recent_ticks) * 0.5:
            return self._no_pattern_result("Waiting for rejection confirmation")
        
        # Check volatility
        avg_recent_vol = self.tick_buffer.get_average_tick_size(10)
        avg_old_vol = self.tick_buffer.get_average_tick_size(30)
        
        if avg_old_vol > 0 and avg_recent_vol > avg_old_vol * 1.5:
            return self._blocked_result(
                "Rising volatility during pattern",
                PatternType.MICRO_DOUBLE_BOTTOM
            )
        
        # PATTERN DETECTED
        quality_score = 22
        
        if level_diff < PATTERN_CONFIG.DOUBLE_LEVEL_TOLERANCE_PIPS * 0.0001 * 0.5:
            quality_score += 4
        
        if PATTERN_CONFIG.DOUBLE_RETEST_MIN_SEC + 2 <= retest_time <= PATTERN_CONFIG.DOUBLE_RETEST_MAX_SEC - 2:
            quality_score += 4
        
        quality_score = min(30, quality_score)
        
        consistency_score = self._calculate_tick_consistency(recent_ticks, 1)
        volatility_score = self._calculate_volatility_quality(ticks)
        
        if retest_time < 5:
            recommended_expiry = 10
        elif retest_time < 8:
            recommended_expiry = 15
        else:
            recommended_expiry = 30
        
        return PatternResult(
            detected=True,
            pattern_type=PatternType.MICRO_DOUBLE_BOTTOM,
            direction=TradeDirection.CALL,  # Reversal from bottom
            pattern_quality_score=quality_score,
            tick_consistency_score=consistency_score,
            volatility_quality_score=volatility_score,
            recommended_expiry=recommended_expiry,
            entry_price=latest_tick.price,
            block_reason=None
        )
