#!/usr/bin/env python3
"""Terminal Control Menu for ContentForwardBot."""

import os
import sys
import signal
import subprocess
import threading
import time
from pathlib import Path

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

ROOT_DIR = Path(__file__).parent
PID_FILE = ROOT_DIR / "bot.pid"
LOG_FILE = ROOT_DIR / "logs" / "bot.log"
MAX_LOG_SIZE = 20 * 1024 * 1024

console = Console() if HAS_RICH else None


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def is_bot_running() -> bool:
    if not PID_FILE.exists():
        return False
    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, 0)
        return True
    except (ValueError, ProcessLookupError, PermissionError):
        PID_FILE.unlink(missing_ok=True)
        return False


def get_pid() -> int | None:
    if not PID_FILE.exists():
        return None
    try:
        return int(PID_FILE.read_text().strip())
    except (ValueError, FileNotFoundError):
        return None


def show_banner(status: str = ""):
    clear()
    if HAS_RICH:
        title = Text("ContentForwardBot", style="bold cyan")
        subtitle = Text("Terminal Control Menu", style="dim")
        console.print(Panel.fit(title, subtitle=subtitle))
        if status:
            console.print(f"  {status}")
        console.print()
    else:
        print("=" * 50)
        print("      ContentForwardBot")
        print("      Terminal Control Menu")
        print("=" * 50)
        if status:
            print(f"  {status}")
        print()


def show_menu():
    running = is_bot_running()
    status = "[bold green]● Running[/bold green]" if running else "[bold red]● Stopped[/bold red]"
    show_banner(status)

    if HAS_RICH:
        options = [
            ("1", "🚀 Start Bot",     "green"  if not running else "dim"),
            ("2", "🛑 Stop Bot",      "red"    if running else "dim"),
            ("3", "📋 View Live Logs", "cyan"),
            ("4", "🔄 Git Pull",      "yellow"),
            ("5", "❌ Exit",          "white"),
        ]
        for num, label, style in options:
            console.print(f"  [bold {style}]{num}. {label}[/bold {style}]")
        console.print()
    else:
        status_text = "Running" if running else "Stopped"
        print(f"  Status: {status_text}")
        print()
        print("  1. 🚀 Start Bot")
        print("  2. 🛑 Stop Bot")
        print("  3. 📋 View Live Logs")
        print("  4. 🔄 Git Pull")
        print("  5. ❌ Exit")
        print()


def get_choice() -> str:
    if HAS_RICH:
        return console.input("  [bold]Select option > [/bold]").strip()
    return input("  Select option > ").strip()


def action_start():
    if is_bot_running():
        if HAS_RICH:
            console.print("\n  [yellow]Bot is already running.[/yellow]")
        else:
            print("\n  Bot is already running.")
        return

    if not ROOT_DIR.joinpath("main.py").exists():
        if HAS_RICH:
            console.print("\n  [red]main.py not found in project directory.[/red]")
        else:
            print("\n  main.py not found in project directory.")
        return

    if not ROOT_DIR.joinpath(".env").exists():
        if HAS_RICH:
            console.print("\n  [red].env file not found. Copy .env.example to .env and configure it.[/red]")
        else:
            print("\n  .env file not found.")
        return

    if HAS_RICH:
        console.print("\n  [cyan]Starting bot in background...[/cyan]")
    else:
        print("\n  Starting bot in background...")

    log_path = ROOT_DIR / "logs"
    log_path.mkdir(exist_ok=True)

    with open(log_path / "bot.log", "a") as log_f:
        process = subprocess.Popen(
            [sys.executable, "main.py", "--run-bot"],
            cwd=str(ROOT_DIR),
            stdout=log_f,
            stderr=log_f,
            start_new_session=True,
        )

    PID_FILE.write_text(str(process.pid))

    time.sleep(1)
    if process.poll() is None:
        if HAS_RICH:
            console.print(f"  [green]Bot started (PID: {process.pid})[/green]")
        else:
            print(f"  Bot started (PID: {process.pid})")
    else:
        PID_FILE.unlink(missing_ok=True)
        if HAS_RICH:
            console.print("  [red]Bot failed to start. Check logs/bot.log[/red]")
        else:
            print("  Bot failed to start. Check logs/bot.log")


def action_stop():
    pid = get_pid()
    if pid is None:
        if HAS_RICH:
            console.print("\n  [yellow]Bot is not running.[/yellow]")
        else:
            print("\n  Bot is not running.")
        return

    if HAS_RICH:
        console.print(f"\n  [cyan]Stopping bot (PID: {pid})...[/cyan]")
    else:
        print(f"\n  Stopping bot (PID: {pid})...")

    try:
        os.kill(pid, signal.SIGTERM)
        for _ in range(10):
            time.sleep(0.5)
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
        else:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    except ProcessLookupError:
        pass
    except PermissionError:
        if HAS_RICH:
            console.print("  [red]Permission denied. Try running with sudo.[/red]")
        else:
            print("  Permission denied. Try running with sudo.")
        return

    PID_FILE.unlink(missing_ok=True)
    if HAS_RICH:
        console.print("  [green]Bot stopped.[/green]")
    else:
        print("  Bot stopped.")


def action_view_logs():
    log_path = ROOT_DIR / "logs" / "bot.log"

    if HAS_RICH:
        console.print("\n  [cyan]Live Logs — press [bold]q[/bold] to return to menu[/cyan]\n")
    else:
        print("\n  Live Logs — press q to return to menu\n")

    if not log_path.exists():
        if HAS_RICH:
            console.print("  [dim]No log file yet. Waiting for logs...[/dim]\n")
        else:
            print("  No log file yet. Waiting for logs...\n")

    try:
        import tty
        import termios
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        tty.setcbreak(fd)
        use_raw = True
    except (ImportError, Exception):
        use_raw = False

    try:
        f = open(log_path, "r")
        f.seek(0, 2)
        while True:
            line = f.readline()
            if line:
                if HAS_RICH:
                    console.print(f"  {line.rstrip()}")
                else:
                    print(f"  {line.rstrip()}")
            else:
                if use_raw:
                    import select
                    if select.select([sys.stdin], [], [], 0.1)[0]:
                        ch = sys.stdin.read(1)
                        if ch in ("q", "Q", "\x1b"):
                            break
                else:
                    try:
                        import msvcrt
                        if msvcrt.kbhit():
                            ch = msvcrt.getwch()
                            if ch in ("q", "Q", "\x1b"):
                                break
                    except ImportError:
                        time.sleep(0.5)
    finally:
        if use_raw:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        try:
            f.close()
        except Exception:
            pass


def action_git_pull():
    if HAS_RICH:
        console.print("\n  [cyan]Running git pull...[/cyan]\n")
    else:
        print("\n  Running git pull...\n")

    result = subprocess.run(
        ["git", "pull"],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
    )

    if HAS_RICH:
        if result.returncode == 0:
            console.print(f"  [green]{result.stdout.strip()}[/green]")
        else:
            console.print(f"  [red]{result.stderr.strip()}[/red]")
    else:
        output = result.stdout.strip() or result.stderr.strip()
        print(f"  {output}")


def action_exit():
    if HAS_RICH:
        confirm = console.input("\n  [dim]Are you sure? (y/N) > [/dim]").strip().lower()
    else:
        confirm = input("\n  Are you sure? (y/N) > ").strip().lower()
    if confirm == "y":
        clear()
        sys.exit(0)


def main():
    actions = {
        "1": action_start,
        "2": action_stop,
        "3": action_view_logs,
        "4": action_git_pull,
        "5": action_exit,
    }

    while True:
        show_menu()
        choice = get_choice()
        action = actions.get(choice)
        if action:
            action()
        else:
            if HAS_RICH:
                console.print("\n  [red]Invalid option.[/red]")
            else:
                print("\n  Invalid option.")
        time.sleep(0.5)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        clear()
        print("Goodbye.")
        sys.exit(0)
