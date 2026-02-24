#!/bin/sh
set -e

# 1. Start the port bridge in the background
# Maps the external 1456 (where Docker is listening) to internal 1455
echo "📡 Starting port bridge (0.0.0.0:1456 -> 127.0.0.1:1455)..."
socat TCP-LISTEN:1456,fork,reuseaddr TCP:127.0.0.1:1455 &

# 2. Setup the Workspace
# Check if the mount directory exists; if so, move there.
MOUNT_DIR="/home/node/mount"
if [ -d "$MOUNT_DIR" ]; then
    echo "📂 Mount detected. Switching workspace to $MOUNT_DIR"
    cd "$MOUNT_DIR"
else
    echo "⚠️ No mount detected at $MOUNT_DIR. Staying in $(pwd)"
fi

# 3. Handle Shell Request
# If user passes 'sh' or 'bash', give them a terminal in the mount dir
if [ "$1" = 'sh' ] || [ "$1" = 'bash' ]; then
    echo "💻 Entering interactive shell..."
    exec "$@"
fi

# 4. Default behavior
if [ -z "$1" ]; then
    echo "🤖 Starting Codex Auth/Service..."
    exec codex auth
fi

# 5. Run specific arguments if provided
exec "$@"
