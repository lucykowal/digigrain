.PHONY: build lint patch test check clean
build:
	scripts/build.sh
lint: build
	scripts/lint.sh
patch: build
	scripts/patch.sh
test:
	python3 -m unittest discover -s tests -v
check:
	scripts/check.sh
clean:
	rm -rf out
