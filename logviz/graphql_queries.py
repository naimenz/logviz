import json
from functools import wraps
from time import time
from typing import Callable, Optional, ParamSpec, TypeVar

import graphene

from logviz.database import Database

# generic types for function
Param = ParamSpec("Param")
RetType = TypeVar("RetType")


def timing(f: Callable[Param, RetType]) -> Callable[Param, RetType]:
    @wraps(f)
    def wrap(*args, **kw):
        ts = time()
        result = f(*args, **kw)
        te = time()
        print("func:%r took: %2.4f sec" % (f.__name__, te - ts))
        return result

    return wrap  # type: ignore  # (I think the typing works out)


class RunConfig(graphene.ObjectType):
    completion_fns = graphene.List(graphene.String)
    seed = graphene.Int()


class Spec(graphene.ObjectType):
    run_id = graphene.String(required=True)
    completion_fns = graphene.List(graphene.String)
    eval_name = graphene.String()
    base_eval = graphene.String()
    split = graphene.String()
    run_config = graphene.Field(RunConfig)
    created_at = graphene.String()


class Metadata(graphene.ObjectType):
    run_id = graphene.String(required=True)
    name = graphene.String()
    uploaded_at = graphene.String()
    completion_fns = graphene.List(graphene.String)
    eval_name = graphene.String()
    base_eval = graphene.String()
    split = graphene.String()
    created_at = graphene.String()
    num_samples = graphene.Int()


class FinalReport(graphene.ObjectType):
    run_id = graphene.String(required=True)
    data = graphene.JSONString()


class ChatMessage(graphene.ObjectType):
    role = graphene.String(required=True)
    content = graphene.String()
    name = graphene.String()


class SamplingEventData(graphene.ObjectType):
    prompt = graphene.List(ChatMessage)
    sampled = graphene.List(graphene.String)


class SamplingEvent(graphene.ObjectType):
    run_id = graphene.String(required=True)
    sample_id = graphene.String(required=True)
    event_id = graphene.Int(required=True)
    type = graphene.String(required=True)
    data = graphene.Field(SamplingEventData)


class SampleMetrics(graphene.ObjectType):
    run_id = graphene.String(required=True)
    sample_id = graphene.String(required=True)
    data = graphene.JSONString()


class SamplePage(graphene.ObjectType):
    """A sample page is a collection of sampling events and the sample metrics."""

    run_id = graphene.String(required=True)
    sample_id = graphene.String()
    page_id = graphene.Int(required=True)
    sampling_events = graphene.List(SamplingEvent)
    sample_metrics = graphene.Field(SampleMetrics)


class Query(graphene.ObjectType):
    spec = graphene.Field(Spec, run_id=graphene.String(required=True))
    specs = graphene.List(Spec)
    metadata = graphene.Field(Metadata, run_id=graphene.String(required=True))
    metadata_list = graphene.List(Metadata)
    sample_ids = graphene.List(graphene.String, run_id=graphene.String(required=True))
    sampling_event = graphene.Field(
        SamplingEvent,
        run_id=graphene.String(required=True),
        event_id=graphene.Int(required=True),
    )
    sampling_events = graphene.List(
        SamplingEvent,
        run_id=graphene.String(required=True),
        sample_id=graphene.String(required=True),
    )
    all_sampling_events = graphene.List(SamplingEvent, run_id=graphene.String(required=True))

    sample_metrics = graphene.Field(
        SampleMetrics,
        run_id=graphene.String(required=True),
        sample_id=graphene.String(required=True),
    )
    all_metrics = graphene.List(SampleMetrics, run_id=graphene.String(required=True))
    sample_page = graphene.Field(
        SamplePage,
        run_id=graphene.String(required=True),
        page_id=graphene.Int(required=True),
    )
    sample_pages = graphene.List(SamplePage, run_id=graphene.String(required=True))
    final_report = graphene.Field(FinalReport, run_id=graphene.String(required=True))
    final_reports = graphene.List(FinalReport)

    @timing
    def resolve_spec(self, info, run_id: str) -> Optional[Spec]:
        raw_spec = Database.get_raw_spec(run_id)
        return _from_raw_spec(raw_spec)

    @timing
    def resolve_metadata(self, info, run_id: str) -> Optional[Metadata]:
        raw_metadata = Database.get_raw_metadata(run_id)
        return _from_raw_metadata(raw_metadata)

    @timing
    def resolve_metadata_list(self, info) -> list[Metadata]:
        raw_metadata_list = Database.get_raw_metadata_list()
        return [_from_raw_metadata(rm) for rm in raw_metadata_list.values()]

    @timing
    def resolve_specs(self, info) -> list[Spec]:
        raw_specs = Database.get_raw_specs()
        specs = [_from_raw_spec(s) for s in raw_specs.values()]
        return specs

    @timing
    def resolve_sample_ids(self, info, run_id: str) -> list[str]:
        return Database.get_sample_ids(run_id)

    @timing
    def resolve_sampling_events(self, info, run_id: str, sample_id: str) -> list[SamplingEvent]:
        return _get_sampling_events(run_id, sample_id)

    @timing
    def resolve_sample_metrics(self, info, run_id: str, sample_id: str) -> Optional[SampleMetrics]:
        return _get_sample_metrics(run_id, sample_id)

    @timing
    def resolve_sample_page(self, info, run_id: str, page_id: int) -> Optional[SamplePage]:
        # NOTE: subtracting 1 from page id before passing to backend
        backend_page_id = page_id - 1
        sample_ids = Database.get_sample_ids(run_id)
        target_sample_id = sorted(sample_ids)[backend_page_id]

        sample_page = _get_sample_page_from_sample_id(run_id, target_sample_id, backend_page_id)
        assert sample_page.page_id == backend_page_id
        return sample_page

    @timing
    def resolve_sample_pages(self, info, run_id: str) -> list[SamplePage]:
        sample_ids = Database.get_sample_ids(run_id)
        pages = []
        for page_id, sample_id in enumerate(sorted(sample_ids)):
            page = _get_sample_page_from_sample_id(run_id, sample_id, page_id)
            pages.append(page)
        return pages

    @timing
    def resolve_final_report(self, info, run_id: str) -> Optional[FinalReport]:
        raw_final_report = Database.get_raw_final_report(run_id)
        return _from_raw_final_report(raw_final_report)


schema = graphene.Schema(query=Query, auto_camelcase=False)


def _get_sampling_events(run_id: str, sample_id: str) -> list[SamplingEvent]:
    raw_sampling_events = Database.get_raw_sampling_events(run_id, sample_id)
    events = [_from_raw_sampling_event(e) for e in raw_sampling_events]
    return events


def _get_sample_metrics(run_id: str, sample_id: str) -> Optional[SampleMetrics]:
    raw_metrics = Database.get_raw_sample_metrics(run_id, sample_id)
    if raw_metrics is None:
        return None
    metrics = SampleMetrics(
        run_id=run_id,
        sample_id=sample_id,
        data=raw_metrics,
    )  # type: ignore  # (pylance doesn't understand graphene)
    return metrics


def _get_sample_page_from_sample_id(run_id: str, sample_id: str, page_id: int) -> SamplePage:
    """Get the samples that correspond to a given sample_id, along with the metrics."""
    sampling_events = _get_sampling_events(run_id, sample_id)
    sample_page = SamplePage(
        run_id=run_id,
        sample_id=sample_id,
        page_id=page_id,
        sampling_events=sampling_events,
        sample_metrics=_get_sample_metrics(run_id, sample_id),
    )  # type: ignore  # (pylance doesn't understand graphene)
    return sample_page


@timing
def _from_raw_final_report(raw_final_report: dict) -> FinalReport:
    return FinalReport(
        run_id=raw_final_report["run_id"],
        data=raw_final_report["data"],
    )  # type: ignore  # (pylance doesn't understand graphene)


@timing
def _from_raw_spec(raw_spec: dict) -> Spec:
    run_config = RunConfig(
        completion_fns=raw_spec["run_config"]["completion_fns"],
        seed=raw_spec["run_config"]["seed"],
    )  # type: ignore  # (pylance doesn't understand graphene)

    spec = Spec(
        run_id=raw_spec["run_id"],
        completion_fns=raw_spec["completion_fns"],
        eval_name=raw_spec["eval_name"],
        base_eval=raw_spec["base_eval"],
        split=raw_spec["split"],
        run_config=run_config,
        created_at=raw_spec["created_at"],
    )  # type: ignore  # (pylance doesn't understand graphene)

    return spec


@timing
def _from_raw_sampling_event(raw_event: dict) -> SamplingEvent:
    raw_data = json.loads(raw_event["data"])
    # TODO (ian): make a cleaner distinction between chat and base models
    try:
        prompt = []
        for message in raw_data["prompt"]:
            prompt.append(
                ChatMessage(
                    role=message["role"],
                    content=message["content"],
                    name=message.get("name"),
                )  # type: ignore  # (pylance doesn't understand graphene)
            )
    except TypeError as e:  # indicates base model
        print(f"KeyError: {e}")
        prompt = [ChatMessage(role="prompt", content=raw_data["prompt"])]  # type: ignore

    data = SamplingEventData(
        prompt=prompt,
        sampled=raw_data["sampled"],
    )  # type: ignore  # (pylance doesn't understand graphene)

    event = SamplingEvent(
        run_id=raw_event["run_id"],
        event_id=raw_event["event_id"],
        sample_id=raw_event["sample_id"],
        type=raw_event["event_type"],
        data=data,
    )  # type: ignore  # (pylance doesn't understand graphene)

    return event


@timing
def _from_raw_metadata(raw_metadata: dict) -> Metadata:
    return Metadata(
        run_id=raw_metadata["run_id"],
        name=raw_metadata["name"],
        completion_fns=raw_metadata["completion_fns"],
        uploaded_at=raw_metadata["uploaded_at"],
        eval_name=raw_metadata["eval_name"],
        base_eval=raw_metadata["base_eval"],
        split=raw_metadata["split"],
        created_at=raw_metadata["created_at"],
        num_samples=raw_metadata["num_samples"],
    )  # type: ignore  # (pylance doesn't understand graphene)
