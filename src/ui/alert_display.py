"""
Alert Display Module
Handles visual and audio alerts for signals.
"""

import time
import sys
import os
from typing import Optional, Callable
from abc import ABC, abstractmethod
from dataclasses import dataclass
sys.path.insert(0, str(__file__).rsplit('src', 1)[0])
from src.signals.signal_generator import Signal, SignalStatus
from src.signals.countdown import BlockingCountdown
from config import SessionState

# Try to import rich for pretty console output
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.live import Live
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# Try to import colorama for basic color support
try:
    from colorama import init, Fore, Back, Style
    init()
    COLORAMA_AVAILABLE = True
except ImportError:
    COLORAMA_AVAILABLE = False


class AlertDisplay(ABC):
    """Abstract base for alert display implementations"""
    
    @abstractmethod
    def show_signal(self, signal: Signal):
        """Display a trading signal"""
        pass
    
    @abstractmethod
    def show_countdown(self, signal: Signal) -> bool:
        """Show countdown before execution. Returns True if completed."""
        pass
    
    @abstractmethod
    def show_status(self, state: SessionState, stats: dict):
        """Show current session status"""
        pass
    
    @abstractmethod
    def show_message(self, message: str, level: str = "info"):
        """Show a status message"""
        pass


class ConsoleDisplay(AlertDisplay):
    """
    Console-based alert display.
    Works with or without rich/colorama.
    """
    
    def __init__(self, enable_sound: bool = True):
        self._enable_sound = enable_sound
        self._use_rich = RICH_AVAILABLE
        self._use_colors = COLORAMA_AVAILABLE
        
        if self._use_rich:
            self._console = Console()
    
    def show_signal(self, signal: Signal):
        """Display trading signal"""
        if not signal.is_actionable:
            # Blocked or no pattern - minimal output
            if signal.status != SignalStatus.NO_PATTERN:
                self._print_blocked(signal)
            return
        
        self._print_signal(signal)
        self._play_alert_sound()
    
    def show_countdown(self, signal: Signal) -> bool:
        """Run countdown with display"""
        if self._use_rich:
            return self._rich_countdown(signal)
        else:
            return BlockingCountdown.run(3)
    
    def show_status(self, state: SessionState, stats: dict):
        """Show session status"""
        if self._use_rich:
            self._rich_status(state, stats)
        else:
            self._basic_status(state, stats)
    
    def show_message(self, message: str, level: str = "info"):
        """Show message with level"""
        timestamp = time.strftime("%H:%M:%S")
        
        level_symbols = {
            "info": "ℹ️ ",
            "success": "✅",
            "warning": "⚠️ ",
            "error": "❌",
            "critical": "🔥"
        }
        
        symbol = level_symbols.get(level, "")
        
        if self._use_colors:
            colors = {
                "info": Fore.CYAN,
                "success": Fore.GREEN,
                "warning": Fore.YELLOW,
                "error": Fore.RED,
                "critical": Fore.RED + Style.BRIGHT
            }
            color = colors.get(level, "")
            print(f"{color}[{timestamp}] {symbol} {message}{Style.RESET_ALL}")
        else:
            print(f"[{timestamp}] {symbol} {message}")
    
    def _print_signal(self, signal: Signal):
        """Print actionable signal"""
        if self._use_rich:
            self._rich_signal(signal)
        else:
            self._basic_signal(signal)
    
    def _print_blocked(self, signal: Signal):
        """Print blocked signal"""
        if self._use_colors:
            print(f"{Fore.YELLOW}[BLOCKED] {signal.block_reason}{Style.RESET_ALL}")
        else:
            print(f"[BLOCKED] {signal.block_reason}")
    
    def _basic_signal(self, signal: Signal):
        """Basic text signal display"""
        print("\n" + "=" * 50)
        print("          🔔 SIGNAL DETECTED 🔔")
        print("=" * 50)
        print(f"  Direction: {signal.direction.value}")
        print(f"  Expiry:    {signal.expiry_seconds}s")
        print(f"  Score:     {signal.confidence_score}/100 [{signal.grade.value}]")
        print(f"  Pattern:   {signal.pattern_type.value}")
        if signal.entry_price:
            print(f"  Entry:     {signal.entry_price:.5f}")
        print("=" * 50)
    
    def _rich_signal(self, signal: Signal):
        """Rich formatted signal display"""
        # Create signal panel
        direction_color = "green" if signal.direction.value == "CALL" else "red"
        
        content = f"""
[bold {direction_color}]{signal.direction.value}[/bold {direction_color}]

Expiry: [cyan]{signal.expiry_seconds}s[/cyan]
Score: [yellow]{signal.confidence_score}[/yellow]/100 [[bold]{signal.grade.value}[/bold]]
Pattern: {signal.pattern_type.value}
"""
        if signal.entry_price:
            content += f"Entry: {signal.entry_price:.5f}"
        
        panel = Panel(
            content.strip(),
            title="🔔 SIGNAL DETECTED",
            border_style=direction_color,
            padding=(1, 4)
        )
        
        self._console.print()
        self._console.print(panel)
    
    def _basic_status(self, state: SessionState, stats: dict):
        """Basic text status display"""
        state_displays = {
            SessionState.ACTIVE: "🟢 ACTIVE",
            SessionState.CAUTION: "🟡 CAUTION",
            SessionState.LOCKED: "🔴 LOCKED"
        }
        
        print("\n--- Session Status ---")
        print(f"State: {state_displays.get(state, 'UNKNOWN')}")
        print(f"Trades: {stats.get('trades', 0)}/2")
        print(f"Wins: {stats.get('wins', 0)}")
        print(f"Losses: {stats.get('losses', 0)}")
        print(f"Duration: {stats.get('duration', 0):.1f} min")
        print("----------------------")
    
    def _rich_status(self, state: SessionState, stats: dict):
        """Rich formatted status display"""
        state_styles = {
            SessionState.ACTIVE: ("green", "🟢 ACTIVE"),
            SessionState.CAUTION: ("yellow", "🟡 CAUTION (A+ only)"),
            SessionState.LOCKED: ("red", "🔴 LOCKED")
        }
        
        style, label = state_styles.get(state, ("white", "UNKNOWN"))
        
        table = Table(title="Session Status", show_header=False, border_style=style)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="white")
        
        table.add_row("State", f"[{style}]{label}[/{style}]")
        table.add_row("Trades", f"{stats.get('trades', 0)}/2")
        table.add_row("Wins", f"[green]{stats.get('wins', 0)}[/green]")
        table.add_row("Losses", f"[red]{stats.get('losses', 0)}[/red]")
        table.add_row("Duration", f"{stats.get('duration', 0):.1f} min")
        
        self._console.print()
        self._console.print(table)
    
    def _rich_countdown(self, signal: Signal) -> bool:
        """Rich countdown display"""
        try:
            direction_color = "green" if signal.direction.value == "CALL" else "red"
            
            for i in range(3, 0, -1):
                panel = Panel(
                    f"[bold white on {direction_color}]   {signal.direction.value}   [/bold white on {direction_color}]\n\n"
                    f"[bold]{i}[/bold]",
                    title="⏱️ COUNTDOWN",
                    border_style=direction_color,
                    padding=(1, 4)
                )
                self._console.print(panel)
                time.sleep(1.0)
            
            # Execute panel
            execute_panel = Panel(
                f"[bold white on {direction_color}]   {signal.direction.value}   [/bold white on {direction_color}]\n\n"
                f"[bold yellow]🔥 EXECUTE NOW 🔥[/bold yellow]",
                title="⚡ GO",
                border_style="yellow",
                padding=(1, 4)
            )
            self._console.print(execute_panel)
            self._play_execute_sound()
            
            return True
            
        except KeyboardInterrupt:
            self._console.print("[yellow]Countdown cancelled[/yellow]")
            return False
    
    def _play_alert_sound(self):
        """Play alert sound on Windows"""
        if not self._enable_sound:
            return
        
        try:
            if sys.platform == 'win32':
                import winsound
                winsound.Beep(800, 200)  # 800Hz for 200ms
                winsound.Beep(1000, 200)  # 1000Hz for 200ms
        except Exception:
            pass  # Sound not available
    
    def _play_execute_sound(self):
        """Play execution sound on Windows"""
        if not self._enable_sound:
            return
        
        try:
            if sys.platform == 'win32':
                import winsound
                winsound.Beep(1200, 300)  # Higher pitch for execute
        except Exception:
            pass
    
    def clear_screen(self):
        """Clear console screen"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def print_header(self, title: str):
        """Print section header"""
        if self._use_rich:
            self._console.rule(f"[bold cyan]{title}[/bold cyan]")
        else:
            print("\n" + "=" * 50)
            print(f"  {title}")
            print("=" * 50)


class MinimalDisplay(AlertDisplay):
    """
    Minimal display for background operation.
    Only shows critical alerts.
    """
    
    def show_signal(self, signal: Signal):
        if signal.is_actionable:
            print(f"\n*** SIGNAL: {signal.direction.value} {signal.expiry_seconds}s [{signal.grade.value}] ***\n")
    
    def show_countdown(self, signal: Signal) -> bool:
        print("3...", end=" ", flush=True)
        time.sleep(1)
        print("2...", end=" ", flush=True)
        time.sleep(1)
        print("1...", end=" ", flush=True)
        time.sleep(1)
        print("GO!")
        return True
    
    def show_status(self, state: SessionState, stats: dict):
        pass  # Silent
    
    def show_message(self, message: str, level: str = "info"):
        if level in ["error", "critical"]:
            print(f"[{level.upper()}] {message}")
