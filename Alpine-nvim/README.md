```bash
docker container ls -a # list all docker container
docker container prune # delete all container.
docker images #list all the images locally
docker image prune -a # delete all docker images
docker run -it -p 5900:5900 --name i3 -v $PWD:/mnt subhajitroy/alpine-i3wm:alpha sh #smaple docker creation

```