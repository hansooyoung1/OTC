"""
Price Capture Module
Handles screen-based price capture and manual input fallback.
Designed for OTC markets without official WebSocket access.
"""

import time
import threading
import re
from dataclasses import dataclass
from typing import Callable, Optional

# OCR dependencies (optional - only needed for screen capture mode)
try:
    import mss
    import pytesseract
    from PIL import Image
    import numpy as np
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False


# -----------------------------
# Data Model
# -----------------------------

@dataclass
class Tick:
    price: float
    timestamp: float


# -----------------------------
# Base Class
# -----------------------------

class PriceCaptureBase:
    def __init__(self, callback: Callable[[Tick], None]):
        self._callback = callback
        self._running = False

    def start(self):
        raise NotImplementedError

    def stop(self):
        self._running = False


# -----------------------------
# OCR Screen Capture (OTC)
# -----------------------------

class OCRPriceCapture(PriceCaptureBase):
    def __init__(
        self,
        callback: Callable[[Tick], None],
        region: dict,
        capture_interval_ms: int = 150,
        min_price_delta: float = 0.00001,
        max_reasonable_jump: float = 0.01,
        duplicate_confirmations: int = 2
    ):
        """
        region: MSS screen region for price
        capture_interval_ms: OCR polling rate
        min_price_delta: smallest meaningful move
        max_reasonable_jump: soft sanity cap (very permissive)
        duplicate_confirmations: OCR stability requirement
        """
        if not OCR_AVAILABLE:
            raise ImportError(
                "OCR dependencies not available. Install: pip install mss pytesseract pillow numpy\n"
                "Also install Tesseract OCR: https://github.com/UB-Mannheim/tesseract/wiki"
            )

        super().__init__(callback)
        self.region = region
        self.capture_interval = capture_interval_ms / 1000.0

        self.min_price_delta = min_price_delta
        self.max_reasonable_jump = max_reasonable_jump
        self.duplicate_confirmations = duplicate_confirmations

        self._last_price: Optional[float] = None
        self._last_tick_time: Optional[float] = None

        self._pending_price: Optional[float] = None
        self._pending_count: int = 0

        self._thread: Optional[threading.Thread] = None

    # -----------------------------
    # OCR Helpers
    # -----------------------------

    def _read_price_from_screen(self) -> Optional[float]:
        with mss.mss() as sct:
            screenshot = sct.grab(self.region)
            img = Image.fromarray(np.array(screenshot))

        text = pytesseract.image_to_string(
            img,
            config="--psm 7 -c tessedit_char_whitelist=0123456789."
        )

        match = re.search(r"\d+\.\d+", text)
        if not match:
            return None

        try:
            return float(match.group())
        except ValueError:
            return None

    # -----------------------------
    # Core Loop
    # -----------------------------

    def _capture_loop(self):
        self._running = True

        while self._running:
            now = time.time()
            price = self._read_price_from_screen()

            if price is not None:
                self._process_price(price, now)

            time.sleep(self.capture_interval)

    def _process_price(self, price: float, timestamp: float):
        # First ever price
        if self._last_price is None:
            self._emit_tick(price, timestamp)
            return

        delta = abs(price - self._last_price)

        # Ignore microscopic OCR jitter
        if delta < self.min_price_delta:
            return

        # Soft sanity check (NOT a kill switch)
        if delta > self.max_reasonable_jump:
            # Likely OCR artifact — ignore quietly
            return

        # OCR stability confirmation
        if self._pending_price == price:
            self._pending_count += 1
        else:
            self._pending_price = price
            self._pending_count = 1

        if self._pending_count >= self.duplicate_confirmations:
            self._emit_tick(price, timestamp)
            self._pending_price = None
            self._pending_count = 0

    # -----------------------------
    # Emit Tick
    # -----------------------------

    def _emit_tick(self, price: float, timestamp: float):
        self._last_price = price
        self._last_tick_time = timestamp

        tick = Tick(price=price, timestamp=timestamp)
        self._callback(tick)

    # -----------------------------
    # Public Controls
    # -----------------------------

    def start(self):
        if self._thread and self._thread.is_alive():
            return

        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def stop(self):
        super().stop()
        if self._thread:
            self._thread.join(timeout=1.0)


# -----------------------------
# Manual Price Input (Testing)
# -----------------------------

class ManualPriceInput(PriceCaptureBase):
    """
    Manual price input for testing or when screen capture unavailable.
    User types prices into console.
    """
    
    def __init__(self, callback: Callable[[Tick], None]):
        super().__init__(callback)
        self._input_thread: Optional[threading.Thread] = None
        self._last_price: Optional[float] = None
    
    def start(self):
        """Start accepting manual input"""
        self._running = True
        self._input_thread = threading.Thread(target=self._input_loop, daemon=True)
        self._input_thread.start()
    
    def stop(self):
        """Stop accepting input"""
        super().stop()
    
    def _input_loop(self):
        """Manual input loop"""
        print("\n[MANUAL INPUT MODE]")
        print("Enter prices as they appear on screen.")
        print("Type 'q' to quit.\n")
        
        while self._running:
            try:
                user_input = input("Price: ").strip()
                
                if user_input.lower() == 'q':
                    self._running = False
                    break
                
                try:
                    price = float(user_input)
                    self._last_price = price
                    tick = Tick(price=price, timestamp=time.time())
                    self._callback(tick)
                except ValueError:
                    print("Invalid price. Enter a number.")
                    
            except EOFError:
                break
    
    def inject_price(self, price: float):
        """Programmatically inject a price (for testing)"""
        self._last_price = price
        tick = Tick(price=price, timestamp=time.time())
        self._callback(tick)


# -----------------------------
# Simulated Price Source (Testing)
# -----------------------------

class SimulatedPriceSource(PriceCaptureBase):
    """
    Simulated price source for testing pattern detection.
    Generates realistic OTC-style price movements.
    """
    
    def __init__(
        self,
        callback: Callable[[Tick], None],
        base_price: float = 1.12345,
        tick_size: float = 0.00001,
        ticks_per_second: float = 5.0
    ):
        super().__init__(callback)
        self._base_price = base_price
        self._tick_size = tick_size
        self._interval = 1.0 / ticks_per_second
        self._sim_thread: Optional[threading.Thread] = None
        self._last_price = base_price
    
    def start(self):
        """Start simulation"""
        import random
        self._random = random
        self._running = True
        self._sim_thread = threading.Thread(target=self._sim_loop, daemon=True)
        self._sim_thread.start()
    
    def stop(self):
        """Stop simulation"""
        super().stop()
        if self._sim_thread:
            self._sim_thread.join(timeout=2.0)
    
    def _sim_loop(self):
        """Generate simulated ticks"""
        trend_direction = 0
        trend_ticks_remaining = 0
        
        while self._running:
            # Decide movement pattern
            if trend_ticks_remaining <= 0:
                pattern = self._random.choice(['trend', 'chop', 'impulse'])
                
                if pattern == 'trend':
                    trend_direction = self._random.choice([-1, 1])
                    trend_ticks_remaining = self._random.randint(5, 15)
                elif pattern == 'impulse':
                    trend_direction = self._random.choice([-1, 1])
                    trend_ticks_remaining = self._random.randint(3, 6)
                else:
                    trend_direction = 0
                    trend_ticks_remaining = self._random.randint(5, 10)
            
            # Generate tick
            if trend_direction != 0:
                # Trending - bias in direction
                move = self._random.choice([trend_direction, trend_direction, 0])
            else:
                # Choppy
                move = self._random.choice([-1, 0, 1])
            
            self._last_price += move * self._tick_size * self._random.uniform(0.5, 2.0)
            
            tick = Tick(price=self._last_price, timestamp=time.time())
            self._callback(tick)
            
            trend_ticks_remaining -= 1
            time.sleep(self._interval * self._random.uniform(0.8, 1.2))
