# Logviz: Visualize [openai/evals](https://github.com/openai/evals) logs
This is a simple webapp for visualizing logs from [openai/evals](https://github.com/openai/evals), primarily developed by me (Ian McKenzie) and Dane Sherburn (@danesherbs).

![image](https://github.com/naimenz/logviz/assets/7796965/dfc8ec60-e27a-4389-9b39-9c849e2f430e)

# Running the webapp
- The webapp can be run from the command line by simply running `logviz`
- The webapp will then be accessible via the browser:
    - `localhost:5001` (or whichever `--port` you choose)
- The old version of `logviz` can be run with `logviz --old`
- Run `logviz --help` for more information about options

# Installation
This app can be installed with `pipx`, `pip`, or `poetry`. Instructions are provided for all three.
- `pipx` allows you to run `logviz` from the command line at any time, regardless of the current directory or active virtual environment.
- `pip` installation is pretty straightforward.
- `poetry` installation is best for developing, since it's easy to `poetry add` new dependencies and it manages the virtual environment for you.

## Pipx instructions
NOTE: I'm not yet sure how easy it is to update the app when installing via `pipx`. It might be fine, I'll have to test it.

1. Clone the repository and `cd` into it
    - `git clone git@github.com:naimenz/logviz.git && cd logviz`
2. [Install `pipx`](https://github.com/pypa/pipx?tab=readme-ov-file#install-pipx)
3. Install `logviz` with `pipx`
    - `pipx install .`

## Pip instructions
1. Clone the repository and `cd` into it
    - `git clone git@github.com:naimenz/logviz.git && cd logviz`
2. Make a virtual environment
    - `python -m venv .venv`
3. Activate the virtual environment
    - `source .venv/bin/activate`
4. Install the webapp
    - `pip install .`
    - (For developing, run `pip install -e .` to install in editable mode instead.)

## Poetry instructions
1. Clone the repository and `cd` into it
    - `git clone git@github.com:naimenz/logviz.git && cd logviz`
2. Install [poetry](https://python-poetry.org/)
    - `curl -sSL https://install.python-poetry.org | python3 -`
4. Make and activate a poetry shell
    - `poetry shell`
3. Install the project
    - `poetry install`

# Migrating to database-based `logviz`
The most recent version of `logviz` uses an `sqlite` database to manage logs. This is a breaking change, so logs previously added to `logviz` will not be accessible by default. I've added a migration script:

1. Run `logviz`
2. Run `./scripts/migrate_logs <dir> <port>`, where `dir` is the log directory you used and port is the port you are running on.
    - By default, this would be:
    - `./scripts/migrate_logs ~/.cache/logviz 5001`
