.PHONY: build deploy status restart logs

build:
	git push origin
	jobforge submit-job --image-tags "latest" --watch --history deploy/build.yaml

deploy:
	nomad job run deploy/readerlm-litserve.nomad

restart:
	nomad job restart readerlm-litserve

status:
	nomad job status readerlm-litserve

logs:
	nomad alloc logs -job readerlm-litserve
