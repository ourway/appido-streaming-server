## Install:

Requirements:
```console
brew install nss hyperkit minikube mkcert helm
brew install gsed pipenv
```
and then for certs:
```console
mkcert --install
cd cert
mkcert app.streamserver.net streamserver.net "*.streamserver.net" dev.streamserver.net
mv app.streamserver.net+3-key.pem key.pem
mv app.streamserver.net+3.pem cert.pem
cd ../
```

Sample stream request:
```console
curl --location --request POST 'https://dev.streamserver.net/streaming/api/media_add_path' \
--header 'Content-Type: application/json' \
--data-raw '{
    "filepath": null,
    "format": "video",
    "correlator": "123",
    "url": "https://file-examples-com.github.io/uploads/2017/04/file_example_MP4_1920_18MG.mp4",
    "webhook": null
}'
```
Result sample:
```json
{
    "message": "Created",
    "ticket": "226fa94a1fb54b78a77a37ee6da20d4b",
    "webhook": null,
    "task": "4fc07e0b-c8b8-440e-9434-11c294a6a0a5"
}
```

Sample status query:
```console
curl --location --request GET 'https://dev.streamserver.net/streaming/api/key/226fa94a1fb54b78a77a37ee6da20d4b'
```
Result sample:
```json
{
    "result": {
        "status": "Ready",
        "progress": 0,
        "message": null,
        "info": {
            "mpd": "/d7a3decdb6280eb0ef3a059ac35ea0ee-stream/program.mpd",
            "m3u8": "/d7a3decdb6280eb0ef3a059ac35ea0ee-stream/hls/program.m3u8"
        },
        "datetime": "01/01/21 08:21:30"
    }
```

