import json
import sqlite3
from pathlib import Path
from typing import Any, Optional

from flask import current_app, g
from werkzeug.datastructures import FileStorage


class Database:
    @staticmethod
    def init_app(app):
        Path(app.config["DATABASE_URI"]).parent.mkdir(parents=True, exist_ok=True)
        with app.app_context():
            Database.initialize_db()

        @app.before_request
        def before_request():
            Database.get_connection()

        @app.teardown_appcontext
        def close_connection(exception=None):
            db = g.pop("db", None)
            if db is not None:
                db.close()

    @staticmethod
    def get_connection():
        if "db" not in g:
            # Assuming you have your database URI stored in app config
            g.db = sqlite3.connect(
                current_app.config["DATABASE_URI"], detect_types=sqlite3.PARSE_DECLTYPES
            )
            g.db.row_factory = sqlite3.Row
        return g.db

    @classmethod
    def initialize_db(cls):
        """Initializes the database, making sure the necessary tables are present."""
        conn = cls.get_connection()
        cursor = conn.cursor()
        tables = [
            """ CREATE TABLE IF NOT EXISTS runs (
                    run_id text PRIMARY KEY,
                    uploaded_at text,
                    num_samples integer NOT NULL,
                    name text NOT NULL
                ); """,
            """ CREATE TABLE IF NOT EXISTS final_report_data (
                    run_id text NOT NULL,
                    key text NOT NULL,
                    value text,
                    PRIMARY KEY (run_id, key),
                    FOREIGN KEY (run_id) REFERENCES runs (run_id)
                ); """,
            """ CREATE TABLE IF NOT EXISTS spec_data (
                    run_id text NOT NULL,
                    key text NOT NULL,
                    value text,
                    PRIMARY KEY (run_id, key),
                    FOREIGN KEY (run_id) REFERENCES runs (run_id)
                ); """,
            """ CREATE TABLE IF NOT EXISTS metric_data (
                    sample_id text NOT NULL,
                    run_id text NOT NULL,
                    key text NOT NULL,
                    value text,
                    PRIMARY KEY (sample_id, run_id, key),
                    FOREIGN KEY (sample_id) REFERENCES samples (sample_id),
                    FOREIGN KEY (run_id) REFERENCES runs (run_id)
                ); """,
            """ CREATE TABLE IF NOT EXISTS samples (
                  sample_id text NOT NULL,
                  run_id integer NOT NULL,
                  FOREIGN KEY (run_id) REFERENCES runs (run_id),
                  PRIMARY KEY (sample_id, run_id)
              ); """,
            """ CREATE TABLE IF NOT EXISTS events (
                  event_id integer NOT NULL,
                  sample_id integer NOT NULL,
                  run_id integer NOT NULL,
                  event_type text NOT NULL,
                  data text,
                  created_at text NOT NULL,
                  PRIMARY KEY (event_id, sample_id, run_id),
                  FOREIGN KEY (run_id) REFERENCES runs (run_id),
                  FOREIGN KEY (sample_id) REFERENCES samples (sample_id)
              ); """,
        ]

        for table_sql in tables:
            cursor.execute(table_sql)
        conn.commit()

    @classmethod
    def process_file(cls, f: FileStorage, uploaded_at: str):
        """Processes a log file and inserts the data into the database."""
        lines = f.readlines()
        spec = None
        final_report = None
        run_id = None
        name = None
        sample_ids_to_write = set()
        for line in lines:
            line_data = json.loads(line)
            if "spec" in line_data:
                run_id = line_data["spec"]["run_id"]
                spec = line_data["spec"]
                for key, value in spec.items():
                    cls.insert_spec_data(
                        run_id=run_id,
                        key=key,
                        value=json.dumps(value),
                        commit=False,
                    )
            elif "final_report" in line_data:
                final_report = line_data["final_report"]
                for key, value in final_report.items():
                    cls.insert_final_report_data(
                        run_id=run_id,
                        key=key,
                        value=json.dumps(value),
                        commit=False,
                    )
            else:
                try:
                    event_type = line_data["type"]
                    event_id = line_data["event_id"]
                    sample_id = line_data["sample_id"]
                    data = line_data["data"]
                    created_at = line_data["created_at"]
                    sample_ids_to_write.add(sample_id)
                    if event_type == "metrics":
                        # manually add created_at as a metric
                        data["created_at"] = created_at
                        for key, value in data.items():
                            cls.insert_metric_data(
                                run_id=run_id,
                                sample_id=sample_id,
                                key=key,
                                value=json.dumps(value),
                                commit=False,
                            )
                    else:
                        cls.insert_event(
                            run_id=run_id,
                            sample_id=sample_id,
                            event_id=event_id,
                            event_type=event_type,
                            data=json.dumps(data),
                            created_at=created_at,
                            commit=False,
                        )
                except KeyError as e:
                    print(f"Error processing line: {e}")
                    raise e
        for sample_id in sample_ids_to_write:
            cls.insert_sample(
                run_id=run_id,
                sample_id=sample_id,
                commit=False,
            )
        assert run_id is not None
        assert spec is not None
        num_samples = len(sample_ids_to_write)
        if name is None:
            name = f"Run {run_id}"
        # only commit once at the end, once the whole file has been processed
        cls.insert_run(
            run_id=run_id,
            uploaded_at=uploaded_at,
            name=name,
            num_samples=num_samples,
            commit=True,
        )

    @classmethod
    def insert_run(cls, run_id, uploaded_at, name, num_samples, commit: bool = True):
        conn = cls.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO runs (run_id, uploaded_at, name, num_samples) VALUES (?, ?, ?, ?)",  # noqa: E501
            (run_id, uploaded_at, name, num_samples),
        )
        if commit:
            conn.commit()

    @classmethod
    def insert_spec_data(cls, run_id, key, value, commit: bool = True):
        conn = cls.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO spec_data (run_id, key, value) VALUES (?, ?, ?)",
            (run_id, key, value),
        )
        if commit:
            conn.commit()

    @classmethod
    def insert_final_report_data(cls, run_id, key, value, commit: bool = True):
        conn = cls.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO final_report_data (run_id, key, value) VALUES (?, ?, ?)",
            (run_id, key, value),
        )
        if commit:
            conn.commit()

    @classmethod
    def insert_metric_data(cls, run_id, sample_id, key, value, commit: bool = True):
        conn = cls.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO metric_data (run_id, sample_id, key, value) VALUES (?, ?, ?, ?)",
            (run_id, sample_id, key, value),
        )
        if commit:
            conn.commit()

    @classmethod
    def insert_sample(cls, run_id, sample_id, commit: bool = True):
        conn = cls.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO samples (run_id, sample_id) VALUES (?, ?)",
            (run_id, sample_id),
        )
        if commit:
            conn.commit()

    @classmethod
    def insert_event(
        cls, run_id, sample_id, event_id, event_type, data, created_at, commit: bool = True
    ):
        conn = cls.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO events (run_id, sample_id, event_id, event_type, data, created_at) VALUES (?, ?, ?, ?, ?, ?)",  # noqa: E501
            (run_id, sample_id, event_id, event_type, data, created_at),
        )
        if commit:
            conn.commit()

    @classmethod
    def get_run_name(cls, run_id: str) -> str:
        conn = cls.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM runs WHERE run_id = ?", (run_id,))
        rows = cursor.fetchall()
        assert len(rows) == 1
        run_name: str = rows[0]["name"]
        return run_name

    @classmethod
    def get_run_ids(cls):
        conn = cls.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT run_id FROM runs")
        return cursor.fetchall()

    @classmethod
    def get_sample_ids(cls, run_id) -> list[str]:
        conn = cls.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT sample_id FROM samples WHERE run_id = ?", (run_id,))
        rows = cursor.fetchall()
        return [row["sample_id"] for row in rows]

    @classmethod
    def get_raw_sampling_events(cls, run_id, sample_id) -> list[dict]:
        conn = cls.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM events WHERE run_id = ? AND sample_id = ? AND event_type = 'sampling'",  # noqa: E501
            (run_id, sample_id),
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    @classmethod
    def get_raw_specs(cls) -> dict:
        conn = cls.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM spec_data")
        rows = cursor.fetchall()
        # organise rows into a dict
        specs: dict[str, dict] = {}
        for row in rows:
            if row["run_id"] not in specs:
                specs[row["run_id"]] = {}
            specs[row["run_id"]][row["key"]] = json.loads(row["value"])
        return specs

    @classmethod
    def get_raw_spec(cls, run_id: str) -> dict:
        conn = cls.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM spec_data WHERE run_id = ?", (run_id,))
        rows = cursor.fetchall()
        # convert all rows to a single dict
        return {row["key"]: json.loads(row["value"]) for row in rows}

    @classmethod
    def get_raw_final_report(cls, run_id: str) -> dict:
        conn = cls.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM final_report_data WHERE run_id = ?", (run_id,))
        rows = cursor.fetchall()
        # convert all rows to a single dict
        raw_final_report: dict[str, Any] = {"run_id": run_id}
        raw_final_report["data"] = {row["key"]: json.loads(row["value"]) for row in rows}
        return raw_final_report

    @classmethod
    def get_raw_sample_metrics(cls, run_id: str, sample_id: str) -> Optional[dict]:
        conn = cls.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM metric_data WHERE run_id = ? AND sample_id = ?",  # noqa: E501
            (run_id, sample_id),
        )
        rows = cursor.fetchall()
        # we can get 0 if the sample is interrupted or it's 'match'
        if len(rows) == 0:
            return None
        return {row["key"]: json.loads(row["value"]) for row in rows}

    @classmethod
    def delete_run(cls, run_id: str) -> int:
        conn = cls.get_connection()
        cursor = conn.cursor()

        # List of tables to delete from, ordered to respect foreign key constraints
        tables = ["events", "spec_data", "final_report_data", "metric_data", "samples", "runs"]

        for table in tables:
            cursor.execute(f"DELETE FROM {table} WHERE run_id = ?", (run_id,))

        conn.commit()
        rows_deleted: int = cursor.rowcount
        return rows_deleted

    @classmethod
    def update_name(cls, run_id: str, name: str) -> int:
        conn = cls.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE runs SET name = ? WHERE run_id = ?", (name, run_id))
        conn.commit()
        rows_updated: int = cursor.rowcount
        return rows_updated

    @classmethod
    def get_raw_metadata(cls, run_id: str) -> dict:
        conn = cls.get_connection()
        cursor = conn.cursor()
        # first, get metadata from the runs table
        cursor.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
        rows = cursor.fetchall()
        assert len(rows) == 1
        data = dict(rows[0])
        # then, add metadata from the spec_data table
        cursor.execute("SELECT * FROM spec_data WHERE run_id = ?", (run_id,))
        rows = cursor.fetchall()
        for row in rows:
            data[row["key"]] = json.loads(row["value"])
        return data

    @classmethod
    def get_raw_metadata_list(cls) -> dict:
        conn = cls.get_connection()
        cursor = conn.cursor()
        # first, get metadata for each run_id from the runs table
        cursor.execute("SELECT * FROM runs")
        rows = cursor.fetchall()
        data = {row["run_id"]: dict(row) for row in rows}
        # then, add metadata from the spec_data table
        for run_id in data.keys():
            cursor.execute("SELECT * FROM spec_data WHERE run_id = ?", (run_id,))
            rows = cursor.fetchall()
            for row in rows:
                data[run_id][row["key"]] = json.loads(row["value"])
        return data
