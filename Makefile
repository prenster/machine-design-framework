P ?= examples/pick-glue-place
PY ?= python3

.PHONY: verify verify-broken install all plc lock baseline hooks claimcheck

install:
	$(PY) -m pip install -r requirements.txt

verify:
	PYTHONPATH=tools $(PY) -m mdf verify $(P)

lock:
	@test -n "$(BY)" || (echo 'usage: make lock P=<project> BY="<your name>"  (the chief engineer, after reading CHECKS.md)'; exit 2)
	PYTHONPATH=tools $(PY) -m mdf lock $(P) --by "$(BY)"

baseline:
	PYTHONPATH=tools $(PY) -m mdf lock $(P)

hooks:
	git config core.hooksPath .githooks

claimcheck:
	PYTHONPATH=tools $(PY) -m mdf claimcheck $(P)

plc:
	PYTHONPATH=tools $(PY) -m mdf plc $(P)

# Must FAIL: proves the checks catch planted mistakes.
verify-broken:
	@PYTHONPATH=tools $(PY) -m mdf verify examples/pick-glue-place-broken --out /tmp/mdf-broken; \
	 rc=$$?; if [ $$rc -eq 1 ]; then echo "OK: broken example failed as expected"; else echo "ERROR: broken example did not fail (rc=$$rc)"; exit 1; fi

all: verify verify-broken
