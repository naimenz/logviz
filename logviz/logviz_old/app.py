from flask import Flask, redirect, render_template, request

from logviz.logviz_old.utils import (
    build_pages,
    build_trajectories,
    filter_pages,
    load_jsonl,
    parse_log_lines,
)

app = Flask(__name__)


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/favicon.ico")
def favicon():
    return ""


@app.route("/search")
def search():
    query = request.args.get("query")
    # load a different page
    assert query is not None
    return redirect(query)


@app.route("/metric_search")
def metric_search():
    """Redirect to the main log url but with the search metrics added to the URL.

    Metric search is currently pretty hacky. It works by passing a dictionary of metrics
    and target values as a string that is then parsed with ast.literal_eval.

    Example:
        If Sample Metrics looks like this:
            Data: {'NR_correct': True, 'CR_correct': True, 'IR_correct': True}
        and I want samples where CR_correct is True and IR_correct is False,
        I would enter the following string in the 'Search metrics' box:
            {'CR_correct': True, 'IR_correct': False}
    """
    referrer = request.args.get("referrer")
    search_metrics = request.args.get("search_metrics")
    # load a different page
    # TODO: fix this parsing
    assert referrer is not None
    base_url = referrer.split("?")[0]
    redirect_url = f"{base_url}?search_metrics={search_metrics}"
    print(f"{redirect_url = }")
    return redirect(redirect_url)


@app.route("/keyword_search")
def keyword_search():
    referrer = request.args.get("referrer")
    keywords = request.args.get("keywords")
    # load a different page
    # TODO: fix this parsing
    assert referrer is not None
    base_url = referrer.split("?")[0]
    redirect_url = f"{base_url}?keywords={keywords}"
    print(f"{redirect_url = }")
    return redirect(redirect_url)


@app.route("/<path:path_to_jsonl>")
def view_sampling(
    path_to_jsonl: str,
):
    path_to_jsonl = "/" + path_to_jsonl
    page_idx = int(request.args.get("page", 1)) - 1
    search_metrics = request.args.get("search_metrics", None)
    keywords = request.args.get("keywords", None)
    try:
        jsonl_dicts = load_jsonl(path_to_jsonl)
        log_lines = parse_log_lines(jsonl_dicts)
        all_pages = build_pages(log_lines)
        pages = filter_pages(all_pages, search_metrics=search_metrics, keywords=keywords)
        print(f"Loaded {len(pages)} pages with sample ids {', '.join(p.sample_id for p in pages)}")
    except Exception as e:
        raise e
    page = pages[page_idx] if 0 <= page_idx < len(pages) else None
    return render_template(
        "log.html",
        page_content=page,
        page=page_idx,
        total_pages=len(pages),
        path_to_jsonl=path_to_jsonl,
        search_metrics=search_metrics,
        keywords=keywords,
    )


@app.route("/timeline/<path:fpath>")
def view_timeline(fpath: str):
    from logviz.logviz_old.parsing import get_events, get_lines, get_timeline

    new_fpath = "/" + fpath
    lines = get_lines(new_fpath)
    events = get_events(lines)
    sample_ids = set(event.sample_id for event in events)

    assert len(sample_ids) != 0, "No samples found"
    assert len(sample_ids) == 1, "Timeline currently at most supports one sample id"

    timeline = get_timeline(events)
    messages = [m.to_dict() for m in timeline]

    return render_template("timeline.html", messages=messages)


@app.route("/task.v1/<path:path_to_jsonl>")
def view_task_v1(path_to_jsonl: str):
    """Updated version of 'view_tasks'.
    This time we use the standard separation of each prompt, but by default we hide all the messages
    and only show the sampled action
    (we also reverse the samples so that the order makes more sense)
    """
    path_to_jsonl = "/" + path_to_jsonl
    page_idx = int(request.args.get("page", 1)) - 1
    try:
        jsonl_dicts = load_jsonl(path_to_jsonl)
        log_lines = parse_log_lines(jsonl_dicts)
        pages = build_pages(log_lines, sort_descending=False)

        print(f"Loaded {len(pages)} pages with sample ids {', '.join(p.sample_id for p in pages)}")
    except Exception as e:
        raise e
    page = pages[page_idx] if 0 <= page_idx < len(pages) else None

    return render_template(
        "task_v1.html",
        page_content=page,
        page=page_idx,
        total_pages=len(pages),
        path_to_jsonl=path_to_jsonl,
    )


@app.route("/task/<path:path_to_jsonl>")
def view_task(path_to_jsonl: str):
    """We have to be somewhat opinionated about which messages to show.
    My plan is to show only the first occurrence of each message, and give the
    number for that message whenever it repeats"""
    path_to_jsonl = "/" + path_to_jsonl
    page_idx = int(request.args.get("page", 1)) - 1
    try:
        jsonl_dicts = load_jsonl(path_to_jsonl)
        log_lines = parse_log_lines(jsonl_dicts)
        pages = build_trajectories(log_lines)
        print(f"Loaded {len(pages)} pages with sample ids {', '.join(p.sample_id for p in pages)}")
    except Exception as e:
        raise e
    page = pages[page_idx] if 0 <= page_idx < len(pages) else None
    return render_template(
        "task.html",
        page_content=page,
        page=page_idx,
        total_pages=len(pages),
        path_to_jsonl=path_to_jsonl,
    )
