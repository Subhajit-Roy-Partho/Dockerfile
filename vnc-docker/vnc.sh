#!/bin/bash


# Step 1: Start Xvfb
# -screen 0  <resolution>x<depth>  (e.g., 1280x1024x24)
# -ac : disable access control (makes it easier for x11vnc to connect)
# &   : run in the background
Xvfb :99 -screen 0 1920x1080x24 -ac +extension GLX +render -noreset &
XVFBPID=$! # Store Xvfb's process ID
sleep 2    # Give Xvfb a moment to initialize

# Step 2: Start x11vnc
# -display :99       : Connect to the Xvfb display
# -nopw              : For testing, no password. For actual use, set a password with `x11vnc -storepasswd` and use `-usepw`
# -forever           : Keep x11vnc running even after clients disconnect
# -bg                : Run x11vnc in the background
# -rfbport 5900      : Explicitly set VNC port (optional if 5900 is okay)
x11vnc -display :99 -nopw -forever -bg -rfbport 5900 -usepw -shared
X11VNCPID=$! # Store x11vnc's process ID
sleep 1

# Step 3: Set the DISPLAY environment variable and launch your application
export DISPLAY=:99

# Optional: Start a window manager (makes managing multiple apps easier)
openbox & # or fluxbox &, or other lightweight WM
OB_PID=$!
sleep 1 # Give Openbox a moment

# Now launch your desired application(s)
relion &
# xterm &
# geany &

echo "----------------------------------------------------"
echo "Xvfb running on display :99 (PID: ${XVFBPID})"
echo "x11vnc serving display :99 on VNC port 5900 (PID: ${X11VNCPID})"
echo "Connect with your VNC viewer to localhost:5900 (or <this_machine_ip>:5900)"
echo "To stop: kill ${X11VNCPID} ${XVFBPID}; fg; Ctrl+C (for apps)"
echo "Or more robustly: pkill -P ${XVFBPID}; kill ${XVFBPID}; pkill -P ${X11VNCPID}; kill ${X11VNCPID}"
echo "----------------------------------------------------"


wait $XVFBPID
EXIT_CODE_XVFB=$?
wait $OB_PID
EXIT_CODE_OB=$?
wait $X11VNCPID
EXIT_CODE_X11VNC=$?

wait $XVFB_PID
EXIT_CODE_XVFB=$?
wait $OB_PID
EXIT_CODE_OB=$?
wait $X11VNC_PID
EXIT_CODE_X11VNC=$?

echo "Xvfb exited with code: $EXIT_CODE_XVFB"
echo "Openbox exited with code: $EXIT_CODE_OB"
echo "x11vnc exited with code: $EXIT_CODE_X11VNC"

# To keep the terminal from exiting and killing background jobs immediately,
# you might want to run 'wait' or just let an app run in the foreground.
# Or, if firefox (or your main app) is the last command and not backgrounded,
# it will keep the script alive. If everything is backgrounded, the script ends
# and the shell might kill the jobs.
# For simplicity here, we'll let firefox run. If it closes, the script might end.
# A 'wait' command would wait for all child processes.
# For example, if you background firefox, you can add:
# wait $! # waits for the last backgrounded process (firefox in this case)
