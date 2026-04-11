# xllmshell

xllmshell is an interactive shell for Ollama with a set of features to make 
chatting with LLMs more pleasant in the keyboard-centric terminal workflow


## Supported features

 - Formatting LLM response as a markdown with syntax highlighting (via [Rich](https://github.com/textualize/rich))
 - Converting LaTex formulas in LLM response to Unicode (via [TeXicode](https://github.com/dxddxx/TeXicode))
 - User input with hotkeys (vi/emacs), history and tab completion for commands (via [python-prompt-toolkit](https://github.com/prompt-toolkit/python-prompt-toolkit))
 - Automatic scrolling in tmux copy-mode to the beginning of the LLM response
 - Multi-line input by using your text editor (from the `$EDITOR` environment var)
 - Saving/loading conversations
 - Running in a non-interactive mode for scripting

## Demo
Programming questions:  
<img src="https://github.com/user-attachments/assets/29812e38-1f43-4a26-bc01-2246f59ff9a6" width="500">

Math questions:  
<img src="https://github.com/user-attachments/assets/953fa7ec-5eca-400e-8896-935a1802234f" width="500">

## Installation

The program is a single executable python script and should run as long as
the dependencies from the `requirements.txt` are installed.

### Installing in a python virtual environment
   To install requirements in a virtual environment, follow these steps from
the project directory:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

To run the script from the virtual environment:
```bash
#!/bin/bash                                                                                                                             
export XLLMSHELL_KEYS=emacs
source .venv/bin/activate && ./xllmshell.py "$@"
```
You can replace the local paths to the global ones and save it as a launch
script available in your `$PATH`. Optionally specifying preferred keybindings 
(vi/emacs) via `XLLMSHELL_KEYS` environment variable or by passing `--keys`.
