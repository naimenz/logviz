import argparse
from pathlib import Path

from logviz.database import Database


def cli(args=None) -> None:
    if not args:
        args = parse_args()
    # importing here to avoid graphql if not necessary
    if args.old:
        from logviz.logviz_old.app import app as old_app

        app_to_run = old_app
    else:
        from logviz.app import app

        app_to_run = app
        app_to_run.config["LOGVIZ_DIR"] = Path(args.dir).expanduser().resolve()
        app_to_run.config["STORE_JSONL"] = args.store_jsonl
        app_to_run.config["DATABASE_URI"] = app_to_run.config["LOGVIZ_DIR"] / "logviz.db"
        Database.init_app(app_to_run)
    app_to_run.run(host="localhost", debug=args.debug, port=args.port)


def parse_args() -> argparse.Namespace:
    arg_parser = argparse.ArgumentParser(description="Logviz CLI")
    arg_parser.add_argument(
        "--old",
        action="store_true",
        help="Use the old logviz UI.",
    )
    arg_parser.add_argument(
        "--dir",
        type=str,
        help="Directory in which the sqlite database will be stored",
        default="~/.logviz",
    )
    arg_parser.add_argument(
        "--store-jsonl",
        action="store_true",
        help="Whether to store raw logs alongside the db",
    )
    arg_parser.add_argument(
        "--port",
        type=int,
        help="Port to run the server on.",
        default=5001,
    )
    arg_parser.add_argument(
        "--debug",
        action="store_true",
        help="Run the server in debug mode.",
    )
    return arg_parser.parse_args()


if __name__ == "__main__":
    cli()
