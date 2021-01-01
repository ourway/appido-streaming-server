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

Certificates:
```

```
