.PHONY: build deploy status restart logs test test-unit test-integration lint typecheck security-scan

# Build and deployment
build:
	git push origin
	jobforge submit-job --image-tags "latest" --watch --history deploy/build.yaml

deploy:
	nomad job run deploy/readerlm-litserve.nomad

restart:
	nomad job restart -on-error=fail readerlm-litserve

status:
	nomad job status readerlm-litserve

logs:
	nomad alloc logs -job readerlm-litserve

# Testing
test: test-unit test-integration

test-unit:
	python -m pytest tests/test_html_preprocessor.py tests/test_quantization.py tests/test_url_fetcher.py -v

test-integration:
	python tests/integration_test.py

# Code quality
lint:
	ruff check .

typecheck:
	mypy server.py html_preprocessor.py --ignore-missing-imports

security-scan:
	bandit -r . -x ./tests
