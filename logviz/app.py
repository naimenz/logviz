import datetime
import json
import sqlite3
from pathlib import Path

from flask import Flask, render_template, request
from graphql_server.flask import GraphQLView
from werkzeug.utils import secure_filename

from logviz.database import Database
from logviz.graphql_queries import schema

app = Flask(__name__)


# @app.before_request
# def log_request_info():
#     app.logger.debug('Headers: %s', request.headers)
#     app.logger.debug('Body: %s', request.get_data())

# Home page
@app.route("/")
def index() -> str:
    rendered_template: str = render_template("index.html")
    return rendered_template


@app.route("/run")
def display_run() -> tuple[str, int]:
    run_id = request.args.get("run_id")
    page_id = request.args.get("page_id", 1)
    if run_id is None:
        return "No run_id provided", 400
    if int(page_id) < 1:
        return f"Invalid page_id {page_id}", 400
    view = request.args.get("view", "default")

    # get the run name from the database before rendering the page
    run_name = Database.get_run_name(run_id)

    rendered_template: str
    match view:
        case "default":
            rendered_template = render_template(
                "default_page_view.html", run_id=run_id, page_id=page_id, run_name=run_name
            )
            return rendered_template, 200
        case "task":
            rendered_template = render_template(
                "timeline_view.html", run_id=run_id, page_id=page_id, run_name=run_name
            )
            return rendered_template, 200
        case _:
            raise ValueError(f"Unknown view {view}")


@app.route("/api/delete", methods=["DELETE"])
def delete_file() -> tuple[dict, int]:
    logviz_dir = app.config["LOGVIZ_DIR"]
    run_id = request.args.get("run_id")
    if run_id is None:
        return {"error": "Cannot delete empty run_id"}, 400
    deleted_count = Database.delete_run(run_id)
    if deleted_count == 0:
        return {"error": f"Run {run_id} not found"}, 404
    else:
        # clean up the log file if it exists
        file_path = get_log_file_path(logviz_dir, run_id)
        if file_path is not None:
            file_path.unlink()
        return {"message": f"Run {run_id} deleted successfully."}, 200


@app.route("/api/update_name", methods=["PATCH"])
def update_name() -> tuple[dict, int]:
    run_id = request.args.get("run_id")
    name = request.args.get("name")
    if run_id is None:
        return {"error": "Cannot update empty run_id"}, 400
    if name is None:
        return {"error": "Cannot update empty name"}, 400
    Database.update_name(run_id, name)
    return {"message": "Name updated successfully."}, 200


@app.route("/api/upload", methods=["POST"])
def upload_files() -> tuple[dict, int]:
    logviz_dir: Path = app.config["LOGVIZ_DIR"]
    logviz_dir.mkdir(parents=True, exist_ok=True)

    uploaded_files = request.files.getlist("files[]")

    for uploaded_file in uploaded_files:
        if uploaded_file.filename == "":
            return {"error": "Can't upload file with empty filename."}, 400

        if uploaded_file.filename is None:
            return {"error": "Can't upload file with no filename."}, 400

        fname = secure_filename(uploaded_file.filename)

        if len(fname) == 0:
            return {"error": "Can't upload file with empty secure filename."}, 400

        if not (fname.endswith(".jsonl") or fname.endswith(".log")):
            print(f"{fname}")
            return {"error": f"Invalid file type `{fname}`."}, 400

        uploaded_at = datetime.datetime.now().isoformat()
        try:
            Database.process_file(uploaded_file, uploaded_at=uploaded_at)
        except sqlite3.IntegrityError as e:
            return {"error": str(e)}, 400
        except KeyError:
            return {"error": "Invalid JSONL formatting"}, 400
        except Exception as e:
            return {"error": str(e)}, 500

        if app.config["STORE_JSONL"]:
            fpath = logviz_dir / fname
            while fpath.exists():
                fname = f"(1)_{fname}"
                fpath = logviz_dir / fname
            uploaded_file.seek(0)
            uploaded_file.save(fpath)

    return {"message": "File(s) uploaded successfully."}, 200


# Setup GraphQL route
app.add_url_rule(
    "/graphql", "graphql", view_func=GraphQLView.as_view("graphql", schema=schema, graphiql=True)
)


def get_log_file_path(log_dir: Path, target_run_id: str) -> Path | None:
    """Find the log file path for a given run id."""
    for file in log_dir.glob("*"):
        if file.suffix not in [".log", ".jsonl"]:
            continue
        try:
            file_run_id = _get_run_id(file)
            if file_run_id == target_run_id:
                return file
        except ValueError:
            continue
    return None


def _get_run_id(fpath: Path) -> str:
    """Extract the run id from the jsonl log."""
    with fpath.open("r") as f:
        lines = f.readlines()
        for line in lines:
            loaded_line = json.loads(line)
            if "run_id" in loaded_line:
                run_id: str = loaded_line["run_id"]
                return run_id
    raise ValueError(f"Cannot find run_id in {fpath}")
