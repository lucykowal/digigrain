# MOD=<name> limits a target to one mod (mods/<name>); unset runs every mod.  e.g. make check MOD=digigrain
export MOD
.PHONY: build lint patch test check clean new-mod
build:
	scripts/build.sh
lint: build
	scripts/lint.sh
patch: build
	scripts/patch.sh
test:
	scripts/test.sh
check:
	scripts/check.sh
new-mod:
	scripts/new-mod.sh $(NAME)
clean:
	rm -rf out
