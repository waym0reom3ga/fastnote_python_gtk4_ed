.PHONY: selftest clicks test

selftest:
	./run.sh --headless --notes-dir /tmp/fastnote_notes --selftest

clicks:
	python3 -m pytest tests/ -q

test: selftest clicks

