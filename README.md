# xllmshell

xllmsmell is an Interactive shell for Ollama with a set of features to make
chatting with LLM in a terminal more pleasant


## Supported features

 - Formatting LLM response (as a markdown with syntax highlighting), using [Rich](https://github.com/textualize/rich)
 - Converting LaTex formulas in LLM response to Unicode, using [TeXicode](https://github.com/dxddxx/TeXicode)
 - Automatic scrolling in tmux copy-mode to the beginning of the LLM response
 - Multi-line input by using your text editor (from the `$EDITOR` environment var)
 - Saving/loading conversations
 - Running in a non-interactive mode for scripting


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
source .venv/bin/activate && ./xllmshell.py "$@"
```
You can replace the local paths to the global ones and save it as a launch script
available in your `$PATH`
