P ?= examples/pick-glue-place
PY ?= python3

.PHONY: verify verify-broken install all

install:
	$(PY) -m pip install -r requirements.txt

verify:
	PYTHONPATH=tools $(PY) -m mdf verify $(P)

# Must FAIL: proves the checks catch planted mistakes.
verify-broken:
	@PYTHONPATH=tools $(PY) -m mdf verify examples/pick-glue-place-broken --out /tmp/mdf-broken; \
	 rc=$$?; if [ $$rc -eq 1 ]; then echo "OK: broken example failed as expected"; else echo "ERROR: broken example did not fail (rc=$$rc)"; exit 1; fi

all: verify verify-broken
