#!/usr/bin/env python3

import argparse
import ollama
import os
import subprocess
import sys
import tempfile
import time

from rich.console import Console, Group
from rich.markdown import Markdown, CodeBlock
from rich.live import Live
from rich.table import Table
from rich.text import Text
from rich.spinner import Spinner
from rich.panel import Panel
from rich.align import Align
from rich.syntax import Syntax

__version__ = "0.0.1"

#########  CONFIGURATION
PREVIEW_STYLE="bright_white on red"
PREVIEW_TEXT = Text(' Previewing unformatted response ',
                    style=PREVIEW_STYLE)
PREVIEW_SPINNER = Spinner("line", text="", style=PREVIEW_STYLE)
RESPONSE_MARKER = 'AI RESPONSE:'
REQUEST_MARKER_STYLED_TEXT = Text(' USER REQUEST:', 
                                  style = "bright_white on yellow")

PROMPT = "\x01\033[1;36m\x02>>>>\x01\033[0m\x02"
###########

class ZeroPaddingCodeBlock(CodeBlock):
    def __rich_console__(self, console, options):
        code_str = self.text.plain
        syntax = Syntax(
            code_str,
            self.lexer_name,
            theme="monokai",
            word_wrap=console.soft_wrap,
            padding=0
        )
        yield syntax

class CustomMarkdown(Markdown):
    elements = {
        **Markdown.elements,
        "fence": ZeroPaddingCodeBlock,
        "code_block": ZeroPaddingCodeBlock
    }

class AIChat:

    def __init__(self, model, format_response, convert_latex, tmux_scroll):
        self.model = model
        self.format_response=format_response
        self.convert_latex=convert_latex
        self.tmux_scroll=tmux_scroll
        self.console = Console(highlight=False)
        self.messages = []


    def process_latex(self, markdown):
        if ('```bash' in markdown or '```sh' in markdown or '```shell' in markdown):
            # txc often confuses shell script commands with Latex, skip latex 
            return markdown
        with tempfile.NamedTemporaryFile(mode='w', delete=True) as temp:
            temp.write(markdown)
            temp.flush()
            return subprocess.check_output(
                    ["txc", "-f", temp.name, "-c"], text=True)

    def last_lines_preview(self, content):
        spinner_frame = PREVIEW_SPINNER.render(time.time())
        result = Text("", style="default")
        result.append(Text(" ", style=PREVIEW_STYLE))
        result.append(spinner_frame)
        result.append(PREVIEW_TEXT)
        result.append(spinner_frame)
        result.append(Text(" ", style=PREVIEW_STYLE))
        text_obj = Text.from_markup(content)
        wrapped_lines = list(text_obj.wrap(self.console, width=self.console.width))
        last_lines = wrapped_lines[-self.console.height+2:]
        result.append(Text("\n", style="default"))
        result.append( Text("\n").join(last_lines))
        return result

    def get_input_from_editor(self):
        with tempfile.NamedTemporaryFile(mode='r', delete=True) as temp:
            editor = os.environ.get('EDITOR', 'vi')
            subprocess.call([editor, temp.name])
            return temp.read()


    def print_status_line(self):
        def status_value(status):
            return "[bold green]On[/bold green]" if status else\
                    "[bold red]Off[/bold red]"

        self.console.print(f"Model: [bold cyan]{self.model}[/bold cyan] |"
                           f" Latex: {status_value(self.convert_latex)} |"
                           f" Tmux-scroll: {status_value(self.tmux_scroll)} |"
                           f" Format responses: {status_value(self.format_response)}")


    def print_info(self):
        self.print_status_line()
        self.console.print(
            "Enter a request or type [bright_magenta]/help[/bright_magenta] for commands\n")

    def print_help(self):
        bm="bright_magenta"
        self.console.print("\n[bold]Available Commands:[/bold]")
        self.console.print(
            f"  [bm]/model <name>[/bm] - Change or show the current model")
        self.console.print(
            f"  [bm]/clear[/bm]        - Clear conversation history")
        self.console.print(
            f"  [bm]/edit[/bm]         - Open $EDITOR to enter input")
        self.console.print(
            f"  [bm]/repeat[/bm]       - Repeat the response with no formatting")
        self.console.print(
            f"  [bm]/exit[/bm]         - Exit the chat")
        self.console.print(
            f"  [bm]/help[/bm]         - Show this menu\n")
 

    def run(self):
        self.print_info()
        try:
            while True:
                user_input = input(PROMPT)
                if not user_input:
                    continue
                # --- Slash Command Handler ---
                if user_input.startswith('/'):
                    cmd_parts = user_input.split()
                    cmd = cmd_parts[0].lower()

                    if cmd in ['/exit', '/bye', '/quit']:
                        break
                    elif cmd == '/edit':
                        with self.console.screen():
                            user_input = get_input_from_editor()
                    elif cmd == '/clear':
                        self.messages = []
                        self.console.clear()
                        self.console.print("[bold green]Conversation cleared.[/bold green]")
                        continue
                    elif cmd == '/repeat':
                        for message in reversed(self.messages):
                            if message['role']=='assistant': 
                                self.console.print(message['content'])
                                break
                        continue
                    elif cmd == '/model':
                        if len(cmd_parts) > 1:
                            self.model = cmd_parts[1]
                            self.console.print(f"Switched to model: [bold cyan]{self.model}[/bold cyan]")
                        else:
                            self.console.print(f"Current model: [bold cyan]{self.model}[/bold cyan]")
                        continue
                    elif cmd == '/help':
                        self.print_help()
                        continue
                    
                    else:
                        self.console.print(f"[bold red]Unknown command:[/bold red] {cmd}")
                        continue
                # -----------------------------

                self.console.print(REQUEST_MARKER_STYLED_TEXT, justify="right")
                content = Text(user_input, style="default")
                bubble = Panel(content, style="white", expand=False, padding=(0, 1))
                self.console.print(Align.right(bubble))
                self.console.print("")

                self.messages.append({'role': 'user', 'content': user_input})
                full_response = ""
                

                with Live(console=self.console, refresh_per_second=10) as live:
                    for chunk in ollama.chat(model=self.model, messages=self.messages, stream=True):
                        content = chunk['message']['content']
                        full_response += content
                        live.update(self.last_lines_preview(full_response), refresh=True)
                    display_group = Group(
                            Text(RESPONSE_MARKER, style="bright_white on bright_blue"),
                            CustomMarkdown(self.process_latex(full_response),
                                           justify="left", code_theme="monokai"))
                    live.update(display_group)

                self.messages.append({'role': 'assistant', 'content': full_response})
                print() 
                subprocess.run(["sh", "./scroll.sh", RESPONSE_MARKER], check=True)

        except KeyboardInterrupt:
            return
        except Exception:
            self.console.print_exception(show_locals=False)
            return


def parse_args():
    parser = argparse.ArgumentParser(
            description=f"xllmterm {__version__} - an interactive ollama shell")

    parser.add_argument(
        "-m","--model", type=str, 
        default="qwen2.5-coder:7b", 
        help="Model to use")

    parser.add_argument(
        "-l","--convert_latex",
        action="store_true",
        help="Enable conversion of LaTex formulas to Unicode via TeXicode")

    parser.add_argument(
        "--no_format",
        action="store_true",
        help="Disable formatting (syntax highlighting) in reposnses")

    parser.add_argument(
        "--no_tmux",
        action="store_true",
        help="Disable autoscrolling to the begining of the AI response in tmux copy-mode")
    return parser.parse_args()


def main ():
    args = parse_args()
    aiChat = AIChat(
            args.model,
            not(args.no_format),
            args.convert_latex,
            not(args.no_tmux))
    aiChat.run()


if __name__ == "__main__":
    main()
