CHECK=`ps -o args | grep "{startx} /bin/sh /usr/bin/startx" | wc -l`
if [ $CHECK -eq 1 ]; then
   rm -rf /tmp/.X* 
else
   echo "$0 is already running.  We're done here."
   exit 1
fi

CHECK=`ps -o args | grep "cat /dev/location" | wc -l`

if [ $CHECK -eq 1 ]; then
   cat /dev/location > /dev/null &
fi

startx & 
x11vnc -create -noshm -forever &
