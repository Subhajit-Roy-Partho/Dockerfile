#!/bin/sh

# 1. Start the bridge in the background (&)
echo "Starting port bridge (1456 -> 1455)..."
socat TCP-LISTEN:1456,fork,reuseaddr TCP:127.0.0.1:1455 &

# 2. Start your main application (codex)
# Using 'exec' here is best practice so codex receives shutdown signals
echo "Starting Codex..."
exec codex