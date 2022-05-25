xrdb -merge ~/.Xresources
xterm -geometry 80x50+494+51 &
xterm -geometry 80x20+494-0 &
exec i3 -V >> /root/i3logs/i3log-$(date +'%F-%k-%M-%S') 2>&1
