#!/usr/bin/env python3

# Copyright (c) 2026 redahe

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.


import argparse
import ollama
import os
import json
import subprocess
import sys
import tempfile
import time

from rich.console import Console, Group
from rich.markdown import Markdown, CodeBlock
from rich.live import Live
from rich.text import Text
from rich.spinner import Spinner
from rich.panel import Panel
from rich.align import Align
from rich.syntax import Syntax

__version__ = "0.0.1"

# ########  CONFIGURATION
PREVIEW_STYLE = "bright_white on red"
PREVIEW_TEXT = Text(' Previewing unformatted response ',
                    style=PREVIEW_STYLE)
PREVIEW_SPINNER = Spinner("line", text="", style=PREVIEW_STYLE)
RESPONSE_MARKER = 'AI RESPONSE:'
REQUEST_MARKER_STYLED_TEXT = Text(' USER REQUEST:',
                                  style="bright_white on yellow")

PROMPT = "\x01\033[1;36m\x02>>>>\x01\033[0m\x02"

DEFAULT_HOST = "http://localhost:11434"
# ##########


class ZeroPaddingCodeBlock(CodeBlock):
    """
    Remove the default padding for the code blocks to facilitate copying
    """
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

    def __init__(self, model, format_response, convert_latex, tmux_scroll, host=None):
        self.client = ollama.Client(host=(host or DEFAULT_HOST))
        self.console = Console(highlight=False)
        self.model = model
        self.format_response = format_response
        self.set_convert_latex(convert_latex, False)
        self.set_tmux_scroll(tmux_scroll, False)
        self.messages = []

    def set_tmux_scroll(self, value, print_error=True):
        if value:
            if not os.environ.get("TMUX", None):
                if print_error:
                    self.console.print(
                        "[bold red]Not running in tmux ($TMUX is not set) [/bold red]")
                self.tmux_scroll = False
                return
        self.tmux_scroll = value

    def set_convert_latex(self, value, print_error=True):
        if value:
            try:
                return_code = subprocess.call(
                    ['txc', '-h'],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except FileNotFoundError:
                return_code = -1
            if return_code != 0:
                if print_error:
                    self.console.print(
                        "[bold red]TeXicode not found ('txc -h' failed) [/bold red]")
                self.convert_latex = False
                return
        self.convert_latex = value

    def process_latex(self, markdown):
        if ('```bash' in markdown or '```sh' in markdown or '```shell' in markdown):
            # txc often confuses shell script commands with Latex, skip latex
            return markdown
        with tempfile.NamedTemporaryFile(mode='w', delete=True) as temp:
            temp.write(markdown)
            temp.flush()
            return subprocess.check_output(
                ["txc", "-f", temp.name, "-c"], text=True)

    def scroll_in_tmux(self, marker):
        # Find the last marker occurrence in copy mode
        subprocess.run(
            ["tmux", "copy-mode", ";", "send-keys", "-X", "search-backward", marker])
        # If the response took more than one screen - scroll it to the top
        subprocess.run(["tmux", "run-shell",
                        ' line_n=$(tmux display-message -p "#{copy_cursor_y}")\n'
                        ' tmux send-keys -X bottom-line\n'
                        ' tmux send-keys -N "$line_n" -X cursor-down\n'
                        ' tmux send-keys -X top-line\n'])
        # Fix the cursor position if the response took less than one screen
        subprocess.run(["tmux", "send-keys", "-X", "bottom-line", ";",
                        "send-keys", "-X", "search-backward", marker])
        # Step one line down and clear search selection
        subprocess.run(["tmux", "send-keys", "-X", "cursor-down", ";",
                        "send-keys", "-X", "clear-selection"])

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
        last_lines = wrapped_lines[-self.console.height + 2:]
        result.append(Text("\n", style="default"))
        result.append(Text("\n").join(last_lines))
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
        cl = "bright_magenta"
        self.console.print("\n[bold]Available Commands:[/bold]")
        self.console.print(
            f"  [{cl}]/settings[/{cl}]        - Show current settings")
        self.console.print(
            f"  [{cl}]/model <name>[/{cl}]    - Change or show the current model")
        self.console.print(
            f"  [{cl}]/latex <on/off>[/{cl}]  - Enable/Disable converting LaTex formulas to Unicode")
        self.console.print(
            f"  [{cl}]/scroll <on/off>[/{cl}] - Enable/Disable autoscrolling to the beginning of the AI response in tmux copy-mode")
        self.console.print(
            f"  [{cl}]/format <on/off>[/{cl}] - Enable/Disable formating (highlighting) the markdown in AI response")
        self.console.print(
            f"  [{cl}]/clear[/{cl}]           - Clear conversation history")
        self.console.print(
            f"  [{cl}]/edit[/{cl}]            - Open $EDITOR to enter input")
        self.console.print(
            f"  [{cl}]/repeat[/{cl}]          - Repeat the response with no formatting")
        self.console.print(
            f"  [{cl}]/save <filename>[/{cl}] - Save conversation to a file")
        self.console.print(
            f"  [{cl}]/load <filename>[/{cl}] - Clear the current conversation and load history from a file ")
        self.console.print(
            f"  [{cl}]/exit[/{cl}]            - Exit the chat")
        self.console.print(
            f"  [{cl}]/help[/{cl}]            - Show this menu\n")

    def parse_on_off(self, value):
        return value.lower() in ["on", "true", "1", "yes", "y"]

    def print_user_input(self, user_input):
        self.console.print(REQUEST_MARKER_STYLED_TEXT, justify="right")
        content = Text(user_input, style="default")
        bubble = Panel(content, style="white", expand=False, padding=(0, 1))
        self.console.print(Align.right(bubble))
        self.console.print("")

    def format_ai_response(self, ai_response):
        response_to_show = ai_response
        if (self.convert_latex):
            response_to_show = self.process_latex(response_to_show)
        if (self.format_response):
            response_to_show = CustomMarkdown(response_to_show)
        else:
            response_to_show = Text(response_to_show)
        response_to_show = Group(
            Text(RESPONSE_MARKER, style="bright_white on bright_blue"),
            response_to_show)
        return response_to_show

    def process_user_query(self, user_input, script_mode=False):
        self.messages.append({'role': 'user', 'content': user_input})
        full_response = ""

        if script_mode:
            ollama_resp = self.client.chat(model=self.model, messages=self.messages)
            full_response = ollama_resp['message']['content']
            self.console.print(full_response)
            self.messages.append({'role': 'assistant', 'content': full_response})
            return

        self.print_user_input(user_input)
        with Live(console=self.console, refresh_per_second=10) as live:
            for chunk in self.client.chat(
                    model=self.model, messages=self.messages, stream=True):
                content = chunk['message']['content']
                full_response += content
                live.update(self.last_lines_preview(full_response), refresh=True)

            response_to_show = self.format_ai_response(full_response)
            live.update(response_to_show)
        self.messages.append({'role': 'assistant', 'content': full_response})
        self.console.print()
        if (self.tmux_scroll):
            self.scroll_in_tmux(RESPONSE_MARKER)

    def save_conversation(self, filename):
        with open(filename, 'w', encoding='utf-8') as file:
            json.dump(self.messages, file, indent=4)
        self.console.print(
            "[bold green]The conversation has been saved to:[/bold green]"
            f" [bold cyan]{filename}[/bold cyan]")

    def load_conversation(self, filename, script_mode=False):
        try:
            messages = []
            with open(filename, 'r', encoding='utf-8') as file:
                messages = json.load(file)
            if not isinstance(messages, list):
                raise Exception("File format is not recognized")
            for message in messages:
                if not isinstance(message, dict) or\
                        'role' not in message or\
                        message['role'] not in ['user', 'assistant'] or\
                        'content' not in message or \
                        not isinstance(message['content'], str) or\
                        len(message) != 2:
                    raise Exception(
                        f"Message format is not recognized ({str(message)})")
            self.messages = messages

            if script_mode:
                return

            for message in self.messages:
                if message['role'] == "user":
                    self.print_user_input(message['content'])
                elif message['role'] == "assistant":
                    ai_response = message['content']
                    self.console.print(self.format_ai_response(ai_response))
                    self.console.print()
        except Exception as e:
            self.console.print(f'[bold red]Error: {str(e)} [/bold red]')

    def run(self):
        self.print_info()
        try:
            while True:
                user_input = input(PROMPT)
                if not user_input:
                    continue
                if user_input.startswith('/'):
                    cmd_parts = user_input.split()
                    cmd = cmd_parts[0].lower()

                    if cmd in ['/exit', '/bye', '/quit']:
                        break
                    elif cmd == '/edit':
                        with self.console.screen():
                            user_input = self.get_input_from_editor()
                    elif cmd == '/latex':
                        if len(cmd_parts) > 1:
                            self.set_convert_latex(self.parse_on_off(cmd_parts[1]))
                        self.print_status_line()
                        continue
                    elif cmd == '/scroll':
                        if len(cmd_parts) > 1:
                            self.set_tmux_scroll(self.parse_on_off(cmd_parts[1]))
                        self.print_status_line()
                        continue
                    elif cmd == '/format':
                        if len(cmd_parts) > 1:
                            self.format_response = self.parse_on_off(cmd_parts[1])
                        self.print_status_line()
                        continue
                    elif cmd == '/save':
                        if len(cmd_parts) > 1:
                            self.save_conversation(cmd_parts[1])
                        else:
                            self.console.print(
                                "[bold red]Filename is missing[/bold red]")
                        continue
                    elif cmd == '/load':
                        if len(cmd_parts) > 1:
                            self.load_conversation(cmd_parts[1])
                        else:
                            self.console.print(
                                "[bold red]Filename is missing[/bold red]")
                        continue
                    elif cmd == '/clear':
                        self.messages = []
                        self.console.clear()
                        self.console.print(
                            "[bold green]Conversation cleared.[/bold green]")
                        continue
                    elif cmd == '/repeat':
                        for message in reversed(self.messages):
                            if message['role'] == 'assistant':
                                self.console.print(message['content'])
                                break
                        continue
                    elif cmd == '/model':
                        if len(cmd_parts) > 1:
                            self.model = cmd_parts[1]
                            self.console.print(
                                f"Switched to model: [bold cyan]{self.model}[/bold cyan]")
                        else:
                            self.console.print(
                                f"Current model: [bold cyan]{self.model}[/bold cyan]")
                        continue
                    elif cmd == '/settings':
                        self.print_status_line()
                        continue
                    elif cmd == '/help':
                        self.print_help()
                        continue
                    else:
                        self.console.print(
                            f"[bold red]Unknown command:[/bold red] {cmd}")
                        continue
                self.process_user_query(user_input)
        except KeyboardInterrupt:
            return
        except Exception:
            self.console.print_exception(show_locals=False)
            return


def parse_args():
    parser = argparse.ArgumentParser(
        description=f"xllmshell {__version__} - an interactive ollama shell")

    parser.add_argument(
        "-m", "--model", type=str,
        default="qwen2.5-coder:7b",
        help="Model to use")

    parser.add_argument(
        "-l", "--load", type=str,
        metavar='FILE_PATH',
        help="Load conversation history from a file")

    parser.add_argument(
        "-a", "--ask", type=str,
        metavar='QUERY_OR_DASH',
        help="Ask only one question. Read question from the standard input if single dash is passed")

    parser.add_argument(
        "--no-latex",
        action="store_true",
        help="Disable conversion of LaTex formulas to Unicode via TeXicode")

    parser.add_argument(
        "--no-format",
        action="store_true",
        help="Disable formatting (syntax highlighting) in reposnses")

    parser.add_argument(
        "--no-tmux",
        action="store_true",
        help="Disable autoscrolling to the begining of the AI response in tmux copy-mode")

    parser.add_argument(
        "-d", "--script-mode",
        action="store_true",
        help="Scripting mode: output bare AI response, no UI feautures, do not print the history. Must be used with --ask")

    parser.add_argument(
        "-o", "--host", type=str,
        metavar='HOST',
        default=DEFAULT_HOST,
        help=f"Specify Ollama host (default: {DEFAULT_HOST})")

    args = parser.parse_args()
    if (args.script_mode):
        if not args.ask:
            parser.error("Script mode must be used with --ask")
        args.no_format = True
        args.no_latex = True
        args.no_tmux = True
    return args


def main():
    args = parse_args()
    aiChat = AIChat(
        args.model,
        not (args.no_format),
        not (args.no_latex),
        not (args.no_tmux),
        args.host)
    if args.load:
        aiChat.load_conversation(args.load, args.script_mode)
    if args.ask:
        if args.ask == '-':
            query = sys.stdin.read()
        else:
            query = args.ask
        aiChat.process_user_query(query, args.script_mode)
    elif not args.script_mode:
        aiChat.run()


if __name__ == "__main__":
    main()
