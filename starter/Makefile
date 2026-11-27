PY := .venv/bin/python

.PHONY: venv check run

venv:
	python3 -m venv .venv
	$(PY) -m pip install -r requirements.txt

check:
	$(PY) -m pytest -q

run:
	$(PY) bot.py
