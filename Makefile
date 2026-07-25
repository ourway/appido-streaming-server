include .env
export

.PHONY: start ping

start:
	@make clean
	@docker-compose build --parallel --pull
	@docker-compose up --no-deps --remove-orphans -d
	@echo "waiting 2 seconds to start the server"
	@sleep 2
	@make logs

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

test:
	@docker-compose exec api-server python -m pytest --no-header -s -vv

ipython:
	@docker-compose exec api-server ipython 

lint:
	@docker-compose exec api-server pylint -j 2 server.py config.py utils.py tasks/

logs:
	@docker-compose logs -t -f --tail=all

ping:
	@docker-compose exec api-server curl -X GET "http://127.0.0.1:4000/streaming/ping" -H  "accept: application/json"

