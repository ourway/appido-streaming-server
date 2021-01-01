include .env
export

.PHONY: start ping

start:
	@make clean
	@docker-compose up --build --remove-orphans -d
	@echo "waiting 2 seconds to start the server"
	@sleep 2

clean:
	@docker-compose stop
	@docker-compose rm -f
	@docker-compose kill
	@docker volume prune -f
	@docker network prune -f

fmt:
	@docker-compose exec api-server isort -w 99 -m 3 --trailing-comma .
	@docker-compose exec api-server black -l 99 .

restart:
	@make clean
	@make start

shell:
	@docker-compose exec api-server sh

test-fmtc:
	@docker-compose exec api-server python -m pytest --cov-report term-missing:skip-covered  --cov=promo_feed systests  --no-header -s -vv -m fmtc

test-tasks:
	@docker-compose exec api-server python -m pytest --cov-report term-missing:skip-covered  --cov=promo_feed systests  --no-header -s -vv -m tasks

test:
	@docker-compose exec api-server python -m pytest --cov-report term-missing:skip-covered  --cov=promo_feed systests  --no-header -s -vv

ipython:
	@docker-compose exec api-server ipython 

lint:
	@docker-compose exec api-server pylint -j 2 promo_feed/

logs:
	@docker-compose logs -t -f --tail=all

ping:
	@docker-compose exec api-server curl -X GET "http://127.0.0.1:4000/streaming/v1/ping/" -H  "accept: application/json" -H  "Authorization: Bearer $(SECRET_KEY)"

