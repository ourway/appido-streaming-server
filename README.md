
## What is Streaming Server?
Streaming server is a tool for converting videos and serve them in streaming mode.
We have a server to upload files and queue them for converting process
We can get status of files based on their uuid and finally we can use DASH to play files

## Install:
First we need ffmpeg and then bento4
...
...
...
After installing base requrements, We need python 2.7 and virtualenv:
clone GIT repo and cd into it.  then:
	virtualenv env
	source env/bin/active
	pip install -r requirements.txt

then, we start celery for converting process
and finally run server.py with gunicorn or other wsgi servers


## usage:
Lets upload a video (here)[http://videostreamer.medialab.ir/]:
Server will return a message like this:

	{
		"ticket": "b27ecc69-55c3-46ea-8027-7428e719e5c8",
		 "message": "OK"
	}


We can visit http://videostreamer.medialab.ir/api/key/b27ecc69-55c3-46ea-8027-7428e719e5c8 to see the status code
We will have:
	SUCCESS - /home/videostreamer/videos/b27ecc69-55c3-46ea-8027-7428e719e5c8

The video is ready in this address
	/videos/<guid>/rashavas.mpd
example:

http://videostreamer.medialab.ir/videos/b27ecc69-55c3-46ea-8027-7428e719e5c8/rashavas.mpd

you can visit http://demo.unified-streaming.com/players/dashjs/index.html to test it
	


goof




