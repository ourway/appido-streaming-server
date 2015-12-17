
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
	```
	virtualenv env
	source env/bin/active
	pip install -r requirements.txt

	```
	then, we start celery for converting process
	and finally run server.py with gunicorn or other wsgi servers


## usage:
	...
	...
	...

