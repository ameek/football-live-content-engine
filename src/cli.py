import asyncio
import sys
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live

from src.config import settings, ProviderType
from src.providers.live_feed_provider import LiveFeedProvider
from src.providers.mock_provider import MockFootballProvider
from src.engine.difference_engine import DifferenceEngine
from src.engine.post_generator import PostGenerator
from src.engine.websocket_manager import WebSocketNotificationManager
from src.engine.monitor import MatchMonitor

console = Console()


async def cmd_list_live():
    """List all currently active live matches."""
    console.print(Panel("[bold green]⚽ Fetching Real-Time Live Football Matches...[/bold green]", border_style="green"))
    provider = LiveFeedProvider(timeout_seconds=settings.request_timeout_seconds)
    matches = await provider.get_live_matches()

    if not matches:
        console.print("[yellow]No live matches currently in progress.[/yellow]")
        return

    table = Table(title=f"🔥 Live Matches Currently In Progress ({len(matches)} matches found)")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Tournament", style="magenta")
    table.add_column("Home Team", style="bold white")
    table.add_column("Score", style="bold yellow", justify="center")
    table.add_column("Away Team", style="bold white")
    table.add_column("Status / Minute", style="green")

    for m in matches:
        min_text = f"{m.minute}'" if m.minute else ""
        table.add_row(
            m.id,
            m.tournament_name,
            m.home_team.name,
            f"{m.score.home} - {m.score.away}",
            m.away_team.name,
            f"{m.status_detail} {min_text}"
        )

    console.print(table)
    console.print(f"\n[cyan]Tip:[/cyan] Run [bold]python -m src.cli monitor <ID>[/bold] to start live tracking and post generation.")


async def cmd_monitor(match_id: str):
    """Live monitor a specific match and generate posts in terminal."""
    console.print(Panel(f"[bold green]⚡ Starting Live Event Monitor for Match ID: {match_id}[/bold green]", border_style="cyan"))

    provider = LiveFeedProvider(timeout_seconds=settings.request_timeout_seconds)
    match = await provider.get_match_by_id(match_id)
    if not match:
        console.print(f"[red]Match {match_id} not found.[/red]")
        return

    console.print(f"[bold]Tracking:[/] {match.home_team.name} vs {match.away_team.name} ({match.tournament_name})")

    diff_engine = DifferenceEngine()
    post_gen = PostGenerator()
    ws_mgr = WebSocketNotificationManager()
    monitor = MatchMonitor(provider, diff_engine, post_gen, ws_mgr, poll_interval_seconds=10)
    monitor.add_match(match_id)

    console.print("[dim]Polling for live events (Press Ctrl+C to stop)...[/dim]\n")

    try:
        while True:
            new_posts = await monitor.poll_once()
            for post in new_posts:
                console.print(Panel(
                    f"[bold yellow]{post.headline}[/bold yellow]\n\n"
                    f"{post.content}\n\n"
                    f"[blue]{' '.join(post.hashtags)}[/blue]",
                    title=f"📱 AI Generated Facebook Post [{post.post_id}]",
                    border_style="yellow"
                ))
            await asyncio.sleep(10)
    except KeyboardInterrupt:
        console.print("\n[yellow]Monitoring stopped by user.[/yellow]")


async def cmd_simulate():
    """Run a deterministic match simulation with live events and post generation."""
    console.print(Panel("[bold cyan]🎮 Running Live Match Simulation (Arsenal vs Chelsea)[/bold cyan]", border_style="cyan"))

    provider = MockFootballProvider()
    diff_engine = DifferenceEngine()
    post_gen = PostGenerator()
    ws_mgr = WebSocketNotificationManager()
    monitor = MatchMonitor(provider, diff_engine, post_gen, ws_mgr)

    monitor.add_match("match_ars_che")
    console.print("[green]Detecting simulated events and generating social posts...[/green]\n")

    posts = await monitor.poll_once()
    for post in posts:
        console.print(Panel(
            f"[bold yellow]{post.headline}[/bold yellow]\n\n"
            f"{post.content}\n\n"
            f"[blue]{' '.join(post.hashtags)}[/blue]",
            title=f"📱 AI Generated Post [{post.platform.upper()}] - {post.post_id}",
            border_style="green"
        ))


def main():
    if len(sys.argv) < 2 or sys.argv[1] == "help":
        console.print("[bold]Football Live Event Engine CLI[/bold]")
        console.print("Commands:")
        console.print("  [green]live[/green]               - List all live matches worldwide")
        console.print("  [green]monitor <match_id>[/green]  - Live monitor match events & generate posts")
        console.print("  [green]simulate[/green]           - Run full test match simulation")
        console.print("  [green]serve[/green]              - Launch Web Server & Dashboard at http://localhost:8000")
        return

    cmd = sys.argv[1].lower()
    if cmd == "live":
        asyncio.run(cmd_list_live())
    elif cmd == "monitor":
        if len(sys.argv) < 3:
            console.print("[red]Error: Match ID required. Usage: python -m src.cli monitor <match_id>[/red]")
            return
        asyncio.run(cmd_monitor(sys.argv[2]))
    elif cmd == "simulate":
        asyncio.run(cmd_simulate())
    elif cmd == "serve":
        import uvicorn
        console.print("[bold green]Starting Web Server & Dashboard at http://0.0.0.0:8000 ...[/bold green]")
        uvicorn.run("src.api.app:app", host=settings.host, port=settings.port, reload=False)
    else:
        console.print(f"[red]Unknown command: {cmd}[/red]")


if __name__ == "__main__":
    main()
