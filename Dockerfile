FROM python:2

## for celery 
ENV C_FORCE_ROOT=true

## bento4
ADD Bento4/ /Bento4/
ENV PATH=$PATH:/Bento4/bin/

RUN chmod -R +x /Bento4/

## python requirements
ADD requirements.txt /data/

## ffmpeg prequesties

RUN apt-get update -y
RUN apt-get -y --force-yes install autoconf automake build-essential \
    libass-dev libfreetype6-dev libsdl1.2-dev libtheora-dev libtool \
    libva-dev libvdpau-dev libvorbis-dev libxcb1-dev libxcb-shm0-dev \
    libxcb-xfixes0-dev pkg-config texinfo zlib1g-dev

RUN apt-get install -y libx264-dev
RUN apt-get install -y libx264-dev
RUN apt-get install -y libmp3lame-dev
RUN apt-get install -y libopus-dev



## ffmpeg
ADD ffmpeg/ffmpeg /usr/bin/ffmpeg
ADD ffmpeg/ffprobe /usr/bin/ffprobe

RUN chmod +x /usr/bin/ffmpeg
RUN chmod +x /usr/bin/ffprobe


## vim
RUN apt-get install -y vim



WORKDIR /data
RUN pip install -r requirements.txt

ADD run-streaming-schedueler /run-streaming-schedueler
ADD run-streaming-api /run-streaming-api



WORKDIR /streaming
EXPOSE 4000
