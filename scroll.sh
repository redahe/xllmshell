#!/bin/sh

tmux copy-mode \; send-keys -X search-backward "$1"
tmux run-shell '
  line_n=$(tmux display-message -p "#{copy_cursor_y}")
  tmux send-keys -X bottom-line
  tmux send-keys -N "$line_n" -X cursor-down
  tmux send-keys -X top-line
'
tmux send-keys -X bottom-line \; send-keys -X search-backward "$1"
tmux send-keys -X cursor-down \; send-keys -X clear-selection
