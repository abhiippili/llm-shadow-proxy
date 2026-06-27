.PHONY: infra stop-infra run-primary run-candidate run-judge run-proxy dev test test-unit test-all

# start MongoDB and Redis as background daemons
infra:
	mkdir -p /tmp/mongodata
	mongod --dbpath /tmp/mongodata --port 27017 --fork --logpath /tmp/mongod.log
	redis-server --daemonize yes --logfile /tmp/redis.log
	echo "MongoDB and Redis started"

# stop infra
stop-infra:
	pkill mongod || true
	pkill redis-server || true
	echo "Infra stopped"

# run individual services (open separate terminal for each)
# --app-dir keeps CWD at project root so pydantic-settings finds .env here
run-primary:
	pip install -r services/primary-llm/requirements.txt -q && \
	uvicorn app.main:app --app-dir services/primary-llm --host 0.0.0.0 --port 8001 --reload

run-candidate:
	pip install -r services/candidate-llm/requirements.txt -q && \
	uvicorn app.main:app --app-dir services/candidate-llm --host 0.0.0.0 --port 8002 --reload

run-judge:
	pip install -r services/judge/requirements.txt -q && \
	uvicorn app.main:app --app-dir services/judge --host 0.0.0.0 --port 8003 --reload

run-proxy:
	pip install -r services/proxy/requirements.txt -q && \
	uvicorn app.main:app --app-dir services/proxy --host 0.0.0.0 --port 8000 --reload

# run tests for a service: make test s=proxy
test:
	cd services/$(s) && pytest tests/ -v --cov=app --cov-report=term-missing

# unit tests only: make test-unit s=proxy
test-unit:
	cd services/$(s) && pytest tests/unit/ -v

# integration tests only: make test-integration s=proxy
test-integration:
	cd services/$(s) && pytest tests/integration/ -v

# all tests
test-all:
	cd services/judge && pytest tests/unit/ -v
	cd services/proxy && pytest tests/unit/ -v
