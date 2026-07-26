#!/usr/bin/env python3
"""Terminal Control Menu for ContentForwardBot."""

import os
import sys
import signal
import subprocess
import time
from pathlib import Path

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.columns import Columns
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

ROOT_DIR = Path(__file__).parent
PID_FILE = ROOT_DIR / "bot.pid"
LOG_FILE = ROOT_DIR / "logs" / "bot.log"

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


def show_banner():
    clear()
    if HAS_RICH:
        lines = [
            "[bold white]ContentForwardBot[/bold white]",
            "[dim]Terminal Control Panel[/dim]",
        ]
        console.print()
        console.print(Panel.fit(
            "\n".join(lines),
            border_style="bright_blue",
            padding=(0, 2),
        ))
        console.print()
    else:
        print()
        print("  +--------------------------------------+")
        print("  |        ContentForwardBot             |")
        print("  |        Terminal Control Panel        |")
        print("  +--------------------------------------+")
        print()


def show_menu():
    running = is_bot_running()
    show_banner()

    if HAS_RICH:
        if running:
            console.print("  Status: [bold green]RUNNING[/bold green]")
        else:
            console.print("  Status: [bold red]STOPPED[/bold red]")
        console.print()
        console.print("  [dim]---[/dim]")
        console.print()

        table = Table(show_header=False, show_edge=False, padding=(0, 1))
        table.add_column("num", style="bold bright_blue", width=4)
        table.add_column("action", style="bold white")
        table.add_column("desc", style="dim")

        s1 = "dim" if running else "bold green"
        s2 = "dim" if not running else "bold red"
        table.add_row("1.", "[green]Start Bot[/green]", "Launch in background", style=s1)
        table.add_row("2.", "[red]Stop Bot[/red]", "Terminate process", style=s2)
        table.add_row("3.", "[cyan]Live Logs[/cyan]", "Real-time log viewer")
        table.add_row("4.", "[yellow]Git Pull[/yellow]", "Update from repository")
        table.add_row("5.", "[white]Exit[/white]", "Close this panel")
        console.print(table)
        console.print()
    else:
        status = "RUNNING" if running else "STOPPED"
        print(f"  Status: {status}")
        print()
        print("  1.  Start Bot         Launch in background")
        print("  2.  Stop Bot          Terminate process")
        print("  3.  Live Logs         Real-time log viewer")
        print("  4.  Git Pull          Update from repository")
        print("  5.  Exit              Close this panel")
        print()


def get_choice() -> str:
    if HAS_RICH:
        return console.input("  [bold bright_blue]>[/bold bright_blue] ").strip()
    return input("  > ").strip()


def action_start():
    if is_bot_running():
        if HAS_RICH:
            console.print("\n  [yellow]Bot is already running.[/yellow]")
        else:
            print("\n  Bot is already running.")
        return

    if not ROOT_DIR.joinpath("main.py").exists():
        if HAS_RICH:
            console.print("\n  [red]main.py not found.[/red]")
        else:
            print("\n  main.py not found.")
        return

    if not ROOT_DIR.joinpath(".env").exists():
        if HAS_RICH:
            console.print("\n  [red].env file not found. Configure .env first.[/red]")
        else:
            print("\n  .env file not found.")
        return

    if HAS_RICH:
        console.print("\n  [cyan]Starting bot...[/cyan]")
    else:
        print("\n  Starting bot...")

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
            console.print(f"  [green]Bot started  [dim]PID {process.pid}[/dim][/green]")
        else:
            print(f"  Bot started (PID: {process.pid})")
    else:
        PID_FILE.unlink(missing_ok=True)
        if HAS_RICH:
            console.print("  [red]Failed to start. Check logs/bot.log[/red]")
        else:
            print("  Failed to start. Check logs/bot.log")


def action_stop():
    pid = get_pid()
    if pid is None:
        if HAS_RICH:
            console.print("\n  [yellow]Bot is not running.[/yellow]")
        else:
            print("\n  Bot is not running.")
        return

    if HAS_RICH:
        console.print(f"\n  [cyan]Stopping bot [dim]PID {pid}[/dim]...[/cyan]")
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
            console.print("  [red]Permission denied.[/red]")
        else:
            print("  Permission denied.")
        return

    PID_FILE.unlink(missing_ok=True)
    if HAS_RICH:
        console.print("  [green]Bot stopped.[/green]")
    else:
        print("  Bot stopped.")


def action_view_logs():
    log_path = ROOT_DIR / "logs" / "bot.log"

    if HAS_RICH:
        console.print()
        console.print(Panel(
            "[bold]Live Logs[/bold]  [dim]|  press [bold]q[/bold] to return[/dim]",
            border_style="bright_blue",
            padding=(0, 1),
        ))
        console.print()
    else:
        print()
        print("  Live Logs  |  press q to return")
        print("  " + "-" * 40)
        print()

    if not log_path.exists():
        if HAS_RICH:
            console.print("  [dim]No logs yet. Waiting...[/dim]")
        else:
            print("  No logs yet. Waiting...")
        time.sleep(1)

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
