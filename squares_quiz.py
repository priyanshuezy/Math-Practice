from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import IntPrompt, Confirm
from rich import box
import sqlite3
import datetime
import random
import sys
import os

console = Console()
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "db", "squares_quiz.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# ── DB ────────────────────────────────────────────────────────────────────────

def init_db():
    con = sqlite3.connect(DB_PATH)
    con.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            played_at TEXT NOT NULL,
            min_val   INTEGER,
            max_val   INTEGER,
            total_q   INTEGER,
            correct   INTEGER,
            wrong     INTEGER,
            score_pct INTEGER,
            hints_on  INTEGER
        );
        CREATE TABLE IF NOT EXISTS answers (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  INTEGER REFERENCES sessions(id),
            number      INTEGER,
            correct_ans INTEGER,
            user_ans    INTEGER,
            is_correct  INTEGER
        );
    """)
    con.commit(); con.close()

def save_session(min_val, max_val, results, hints_on):
    correct_count = sum(1 for r in results if r[3])
    score_pct     = int((correct_count / len(results)) * 100)
    played_at     = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        "INSERT INTO sessions (played_at,min_val,max_val,total_q,correct,wrong,score_pct,hints_on) VALUES (?,?,?,?,?,?,?,?)",
        (played_at, min_val, max_val, len(results), correct_count, len(results)-correct_count, score_pct, int(hints_on))
    )
    sid = cur.lastrowid
    cur.executemany(
        "INSERT INTO answers (session_id,number,correct_ans,user_ans,is_correct) VALUES (?,?,?,?,?)",
        [(sid, num, ca, ua, int(ok)) for num, ca, ua, ok in results]
    )
    con.commit(); con.close()
    return sid, played_at

# ── History ───────────────────────────────────────────────────────────────────

def show_history():
    con = sqlite3.connect(DB_PATH)
    rows = con.execute(
        "SELECT id,played_at,min_val,max_val,total_q,correct,wrong,score_pct,hints_on FROM sessions ORDER BY id DESC LIMIT 10"
    ).fetchall()
    con.close()
    if not rows:
        console.print("[yellow]No sessions saved yet.[/yellow]"); return
    console.rule("[bold cyan]📁 Last 10 Sessions[/bold cyan]")
    t = Table(box=box.SIMPLE_HEAVY, header_style="bold cyan")
    for col in ("ID","Date","Range","Q's","✅","❌","Score","Hints"):
        t.add_column(col, justify="center")
    for sid, played_at, mn, mx, total, correct, wrong, pct, hints in rows:
        c = "green" if pct >= 70 else "yellow" if pct >= 40 else "red"
        t.add_row(str(sid), played_at, f"{mn}–{mx}", str(total),
                  f"[green]{correct}[/green]", f"[red]{wrong}[/red]",
                  f"[{c}]{pct}%[/{c}]", "✅" if hints else "❌")
    console.print(t)

# ── Helpers ───────────────────────────────────────────────────────────────────

def parse_range_arg(arg):
    try:
        parts = arg.split("-")
        if len(parts) == 2:
            return int(parts[0]), int(parts[1])
    except Exception:
        pass
    return None

def get_range():
    console.print(Panel("[bold cyan]🔢 Squares Quiz[/bold cyan]", border_style="cyan"))
    console.print("\n[yellow]Enter the number range:[/yellow]")
    while True:
        min_val = IntPrompt.ask("[green]  Min[/green]")
        max_val = IntPrompt.ask("[green]  Max[/green]")
        if max_val > min_val and min_val >= 1:
            return min_val, max_val
        console.print("[red]  ❌ Min must be ≥ 1 and Max must be greater than Min.[/red]")

# ── Quiz ──────────────────────────────────────────────────────────────────────

def run_quiz(min_val=None, max_val=None, hints_on=None):
    if min_val is None:
        min_val, max_val = get_range()
    if hints_on is None:
        hints_on = Confirm.ask(
            "\n[magenta]Enable hints?[/magenta] [dim](show correct answer right after wrong)[/dim]",
            default=True
        )

    console.print()
    numbers = list(range(min_val, max_val + 1))
    random.shuffle(numbers)
    total   = len(numbers)
    results = []

    for i, num in enumerate(numbers, 1):
        correct = num * num
        console.rule(f"[bold]Question {i} of {total}[/bold]")
        console.print(f"\n  [cyan]What is [bold]{num}²[/bold] ?[/cyan]  ", end="")

        try:
            answer = IntPrompt.ask("")
        except Exception:
            answer = -999999

        is_correct = answer == correct

        if is_correct:
            console.print("  [bold green]✅ Correct![/bold green]")
        else:
            if hints_on:
                console.print(f"  [bold red]❌ Wrong![/bold red]   [yellow]Correct: [bold]{correct}[/bold][/yellow]")
            else:
                console.print("  [bold red]❌ Wrong![/bold red]")

        results.append((num, correct, answer, is_correct))

    show_results(results, hints_on, min_val, max_val)

# ── Results ───────────────────────────────────────────────────────────────────

def show_results(results, hints_on, min_val, max_val):
    correct_count = sum(1 for r in results if r[3])
    wrong_count   = len(results) - correct_count
    score_pct     = int((correct_count / len(results)) * 100)
    color         = "green" if score_pct >= 70 else "yellow" if score_pct >= 40 else "red"

    console.print()
    console.rule("[bold cyan]📊 Quiz Results[/bold cyan]")
    summary = (
        f"[bold green]✅ Correct: {correct_count}[/bold green]   "
        f"[bold red]❌ Wrong: {wrong_count}[/bold red]   "
        f"[white]Total: {len(results)}[/white]\n\n"
        f"[bold {color}]Score: {score_pct}%[/bold {color}]"
    )
    console.print(Panel(summary, border_style=color, padding=(1, 4)))

    table = Table(box=box.ROUNDED, border_style="dim", header_style="bold cyan")
    table.add_column("No.",            justify="center", width=5)
    table.add_column("Question",       justify="center")
    table.add_column("Your Answer",    justify="center")
    table.add_column("Correct Answer", justify="center")
    table.add_column("Result",         justify="center")

    for i, (num, correct, user_ans, is_correct) in enumerate(results, 1):
        table.add_row(
            str(i), f"[bold]{num}²[/bold]",
            f"[green]{user_ans}[/green]"  if is_correct else f"[red]{user_ans}[/red]",
            f"[green]{correct}[/green]"   if is_correct else f"[yellow]{correct}[/yellow]",
            "[green]✅ Correct[/green]"    if is_correct else "[red]❌ Wrong[/red]"
        )
    console.print(table)

    wrong_ones = [r for r in results if not r[3]]
    if wrong_ones and not hints_on:
        console.print()
        console.print(Panel("[bold red]❌ What You Got Wrong[/bold red]", border_style="red"))
        for num, correct, user_ans, _ in wrong_ones:
            console.print(f"  [cyan]{num}²[/cyan] → you said [red]{user_ans}[/red], correct is [green]{correct}[/green]")

    sid, played_at = save_session(min_val, max_val, results, hints_on)
    console.print()
    console.print(Panel(
        f"[dim]💾 Saved · Session[/dim] [white]#{sid}[/white] [dim]at[/dim] [white]{played_at}[/white]",
        border_style="dim", padding=(0, 2)
    ))

    console.print()
    console.print("[bold cyan]What do you want to do?[/bold cyan]")
    console.print("  [green]1[/green] → Try same range again [dim](repeat for practice)[/dim]")
    console.print("  [yellow]2[/yellow] → Start with a new range")
    console.print("  [red]3[/red] → Exit\n")

    choice = IntPrompt.ask("[white]Choice[/white]", default=1)
    if choice == 1:
        run_quiz(min_val=min_val, max_val=max_val, hints_on=hints_on)
    elif choice == 2:
        run_quiz()
    else:
        console.print("\n[dim]Bye! 👋[/dim]\n")

# ── Entry ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()

    args = sys.argv[1:]

    if args and args[0].lower() == "h":
        show_history()
        sys.exit()

    range_arg = None
    for a in args:
        parsed = parse_range_arg(a)
        if parsed:
            range_arg = parsed
            break

    if range_arg:
        mn, mx = range_arg
        console.print(Panel("[bold cyan]🔢 Squares Quiz[/bold cyan]", border_style="cyan"))
        hints_on = Confirm.ask(
            "\n[magenta]Enable hints?[/magenta] [dim](show correct answer right after wrong)[/dim]",
            default=True
        )
        run_quiz(min_val=mn, max_val=mx, hints_on=hints_on)
    else:
        run_quiz()
