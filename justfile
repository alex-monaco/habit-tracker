venv := ".venv"
python := venv + "/bin/python3"
streamlit := venv + "/bin/streamlit"

default:
    @just --list

install:
    python3 -m venv {{venv}}
    {{python}} -m pip install -r requirements.txt

run:
    {{streamlit}} run app.py

extract start end:
    {{python}} extract_habits.py --start {{start}} --end {{end}}

test:
    {{python}} -m pytest tests

lint:
    {{python}} -m ruff check .

fmt:
    {{python}} -m ruff format .

clean:
    rm -rf __pycache__ .pytest_cache
    find . -type d -name __pycache__ -exec rm -rf {} +
