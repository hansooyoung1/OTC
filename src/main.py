"""
OTC Signal Engine - Main Entry Point
Semi-automated trading signal engine for OTC markets.

Usage:
    python main.py              # Interactive mode with manual price input
    python main.py --simulate   # Simulated price data for testing
    python main.py --screen     # Screen capture mode (requires setup)
"""

import sys
import time
import argparse
import threading
from typing import Optional

# Add parent to path for imports
sys.path.insert(0, str(__file__).rsplit('src', 1)[0])

from src.data.tick_buffer import TickBuffer
from src.data.price_capture import (
    Tick as CaptureTick,
    ManualPriceInput,
    SimulatedPriceSource,
    OCRPriceCapture,
)
from src.signals.signal_generator import SignalGenerator, Signal, SignalStatus
from src.state.session_state import SessionStateMachine
from src.ui.alert_display import ConsoleDisplay
from config import SessionState, SESSION_CONFIG, DATA_CONFIG


class OTCSignalEngine:
    """
    Main engine orchestrator.
    Coordinates all components for signal generation.
    """
    
    def __init__(
        self,
        mode: str = "manual",
        enable_sound: bool = True
    ):
        self.mode = mode
        
        # Initialize components
        self.tick_buffer = TickBuffer()
        self.session_state = SessionStateMachine(
            on_state_change=self._on_state_change
        )
        self.signal_generator = SignalGenerator(
            tick_buffer=self.tick_buffer,
            session_state=self.session_state,
            on_signal=self._on_signal
        )
        self.display = ConsoleDisplay(enable_sound=enable_sound)
        
        # Price source (set based on mode)
        self._price_source = None
        self._setup_price_source()
        
        # Engine state
        self._running = False
        self._scan_thread: Optional[threading.Thread] = None
        self._last_scan_time = 0.0
        self._scan_interval = DATA_CONFIG.CAPTURE_INTERVAL_MS / 1000.0
        
        # Signal handling
        self._pending_signal: Optional[Signal] = None
        self._awaiting_result = False
    
    def _setup_price_source(self):
        """Setup price source based on mode"""
        callback = self._on_price_update
        
        if self.mode == "simulate":
            self._price_source = SimulatedPriceSource(
                callback=callback,
                base_price=1.12345,
                ticks_per_second=5.0
            )
        elif self.mode == "screen":
            # Default screen region - configure in settings.py
            region = {
                "left": DATA_CONFIG.PRICE_REGION_X,
                "top": DATA_CONFIG.PRICE_REGION_Y,
                "width": DATA_CONFIG.PRICE_REGION_WIDTH,
                "height": DATA_CONFIG.PRICE_REGION_HEIGHT
            }
            self._price_source = OCRPriceCapture(
                callback=callback,
                region=region,
                capture_interval_ms=DATA_CONFIG.CAPTURE_INTERVAL_MS
            )
        else:  # manual
            self._price_source = ManualPriceInput(callback=callback)
    
    def start(self):
        """Start the engine"""
        self.display.clear_screen()
        self._print_banner()
        
        # Start session
        self.session_state.start_session()
        self._show_status()
        
        # Start price source
        self._running = True
        self._price_source.start()
        
        # Start scan loop
        self._scan_thread = threading.Thread(target=self._scan_loop, daemon=True)
        self._scan_thread.start()
        
        # Main interaction loop
        try:
            self._interaction_loop()
        except KeyboardInterrupt:
            self.display.show_message("Interrupted by user", "warning")
        finally:
            self.stop()
    
    def stop(self):
        """Stop the engine"""
        self._running = False
        
        if self._price_source:
            self._price_source.stop()
        
        self.session_state.end_session()
        self.display.show_message("Engine stopped", "info")
    
    def _scan_loop(self):
        """Background scan loop"""
        while self._running:
            # Check for session timeout
            if self.session_state.check_session_timeout():
                self.display.show_message(
                    f"Session timeout ({SESSION_CONFIG.MAX_SESSION_MINUTES}min)",
                    "warning"
                )
                break
            
            # Don't scan if awaiting result or session locked
            if self._awaiting_result or not self.session_state.is_trading_allowed:
                time.sleep(0.5)
                continue
            
            # Rate limit scans
            now = time.time()
            if now - self._last_scan_time < self._scan_interval:
                time.sleep(0.05)
                continue
            
            self._last_scan_time = now
            
            # Scan for signals
            signal = self.signal_generator.scan()
            
            if signal.is_actionable:
                self._pending_signal = signal
    
    def _interaction_loop(self):
        """Main interaction loop for user input"""
        self.display.show_message(
            "Engine started. Enter prices or commands.",
            "success"
        )
        
        if self.mode != "manual":
            self.display.show_message(
                f"Running in {self.mode} mode. Type 'help' for commands.",
                "info"
            )
        
        while self._running and self.session_state.is_trading_allowed:
            try:
                # Check for pending signal
                if self._pending_signal:
                    self._handle_signal(self._pending_signal)
                    self._pending_signal = None
                    continue
                
                # In manual mode, price input is handled by ManualPriceInput
                # In other modes, handle commands
                if self.mode != "manual":
                    try:
                        cmd = input().strip().lower()
                        self._handle_command(cmd)
                    except EOFError:
                        break
                else:
                    # In manual mode, just wait
                    time.sleep(0.1)
                    
            except Exception as e:
                self.display.show_message(f"Error: {e}", "error")
    
    def _handle_signal(self, signal: Signal):
        """Handle an actionable signal"""
        # Display signal
        self.display.show_signal(signal)
        
        # Run countdown
        completed = self.display.show_countdown(signal)
        
        if not completed:
            self.display.show_message("Signal cancelled", "warning")
            return
        
        # Wait for user to confirm result
        self._awaiting_result = True
        self.display.show_message(
            "Did you take the trade? Enter result: (w)in / (l)oss / (s)kip",
            "info"
        )
        
        try:
            result = input("Result: ").strip().lower()
            
            if result in ['w', 'win']:
                self.signal_generator.record_trade_result(is_win=True)
                self.display.show_message("WIN recorded", "success")
            elif result in ['l', 'loss']:
                self.signal_generator.record_trade_result(is_win=False)
                self.display.show_message("LOSS recorded", "error")
            else:
                self.display.show_message("Trade skipped", "info")
        except EOFError:
            pass
        finally:
            self._awaiting_result = False
            self._show_status()
    
    def _handle_command(self, cmd: str):
        """Handle user commands"""
        if cmd == 'help':
            self._print_help()
        elif cmd == 'status':
            self._show_status()
        elif cmd == 'quit' or cmd == 'exit':
            self._running = False
        elif cmd == 'lock':
            self.session_state.force_lock("User requested")
        elif cmd == 'pairs':
            self._show_pair_info()
    
    def _on_price_update(self, capture_tick: CaptureTick):
        """Callback when price is updated"""
        tick = self.tick_buffer.add_tick(capture_tick.price, capture_tick.timestamp)
        if tick:
            # Calculate latency for noise scoring
            latency = (time.time() - tick.timestamp) * 1000
            self.signal_generator.confidence_scorer.record_tick_latency(latency)
    
    def _on_signal(self, signal: Signal):
        """Callback when signal is generated"""
        # This is called from the signal generator
        # The pending signal will be picked up by interaction loop
        pass
    
    def _on_state_change(self, old_state: SessionState, new_state: SessionState):
        """Callback when session state changes"""
        self.display.show_message(
            f"State changed: {old_state.value} -> {new_state.value}",
            "warning"
        )
        self._show_status()
    
    def _show_status(self):
        """Display current status"""
        stats = {
            'trades': self.session_state.stats.trades_taken,
            'wins': self.session_state.stats.wins,
            'losses': self.session_state.stats.losses,
            'duration': self.session_state.stats.session_duration_minutes
        }
        self.display.show_status(self.session_state.state, stats)
    
    def _show_pair_info(self):
        """Show pair selection info"""
        self.display.show_message(
            "Pair selection should be done manually at session start.\n"
            "Select pairs with:\n"
            "  - ≥90% payout\n"
            "  - Clean impulses\n"
            "  - Minimal chop\n"
            "  - Good UI responsiveness",
            "info"
        )
    
    def _print_banner(self):
        """Print startup banner"""
        banner = """
╔══════════════════════════════════════════════════════════════╗
║                   OTC SIGNAL ENGINE v1.0                     ║
║              Semi-Automated Trading Signals                  ║
╠══════════════════════════════════════════════════════════════╣
║  Mode: {mode:<10}  │  Max Trades: 2/day  │  Max Loss: 1  ║
╚══════════════════════════════════════════════════════════════╝
        """.format(mode=self.mode.upper())
        print(banner)
    
    def _print_help(self):
        """Print help information"""
        help_text = """
╔══════════════════════════════════════════════════════════════╗
║                        COMMANDS                              ║
╠══════════════════════════════════════════════════════════════╣
║  status  - Show current session status                       ║
║  pairs   - Show pair selection guidelines                    ║
║  lock    - Lock session (stop trading)                       ║
║  help    - Show this help                                    ║
║  quit    - Exit the engine                                   ║
╠══════════════════════════════════════════════════════════════╣
║                     SIGNAL GRADES                            ║
╠══════════════════════════════════════════════════════════════╣
║  A+  (85-100) - Highest quality, trade in any state          ║
║  A   (75-84)  - Good quality, trade in ACTIVE state only     ║
╠══════════════════════════════════════════════════════════════╣
║                    SESSION STATES                            ║
╠══════════════════════════════════════════════════════════════╣
║  🟢 ACTIVE   - Normal trading (A or A+)                      ║
║  🟡 CAUTION  - After 1 win (A+ only)                         ║
║  🔴 LOCKED   - After loss or 2 wins (no trading)             ║
╚══════════════════════════════════════════════════════════════╝
        """
        print(help_text)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="OTC Signal Engine - Semi-automated trading signals"
    )
    parser.add_argument(
        '--simulate', '-s',
        action='store_true',
        help='Use simulated price data'
    )
    parser.add_argument(
        '--screen', '-c',
        action='store_true',
        help='Use screen capture for prices'
    )
    parser.add_argument(
        '--no-sound',
        action='store_true',
        help='Disable sound alerts'
    )
    
    args = parser.parse_args()
    
    # Determine mode
    if args.simulate:
        mode = "simulate"
    elif args.screen:
        mode = "screen"
    else:
        mode = "manual"
    
    # Create and start engine
    engine = OTCSignalEngine(
        mode=mode,
        enable_sound=not args.no_sound
    )
    
    try:
        engine.start()
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
