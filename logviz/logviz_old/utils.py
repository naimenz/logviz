import ast
import os
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import jsonlines


class Prompt(ABC):
    @abstractmethod
    def render_prompt(self) -> Iterable[dict[str, str]]:
        pass

    @abstractmethod
    def contains(self, keyword: str) -> bool:
        pass


@dataclass
class ChatPrompt(Prompt):
    data: list[dict[str, str]]

    def render_prompt(self) -> Iterable[dict[str, str]]:
        return self.data

    def contains(self, keyword: str) -> bool:
        combined_prompt = "".join([prompt["content"] for prompt in self.data])
        return keyword in combined_prompt


@dataclass
class BasePrompt(Prompt):
    data: str

    def render_prompt(self) -> Iterable[dict[str, str]]:
        return [{"role": "base-prompt", "content": self.data}]

    def contains(self, keyword: str) -> bool:
        return keyword in self.data


class AbstractLogLine(ABC):
    """Abstract class for log lines"""


@dataclass
class LogLine(AbstractLogLine):
    run_id: str
    created_by: str
    created_at: str


@dataclass
class LogFinalReport(AbstractLogLine):
    final_report: dict


@dataclass
class LogSpec(LogLine):
    spec: dict


@dataclass
class LogSampling(LogLine):
    event_id: int
    sample_id: str
    prompt: Prompt
    sampled: str | list[str]

    def render_prompt(self):
        return self.prompt.render_prompt()


@dataclass
class LogMetrics(LogLine):
    event_id: int
    sample_id: str
    data: dict  # we don't know what each eval will record


@dataclass
class LogPage:
    sample_id: str  # each page will correspond to a sample
    samples: list[LogSampling]
    metrics: LogMetrics
    final_report: LogFinalReport | None = None
    log_spec: LogSpec | None = None


def load_jsonl(path_to_jsonl: str) -> list[dict]:
    """Load a jsonl file into a list of dicts
    Making a separate function so we can catch errors with the jsonl loading"""
    path = Path(path_to_jsonl)
    assert path.exists(), f"Path {path_to_jsonl} does not exist"
    with jsonlines.open(path_to_jsonl) as reader:
        return list(reader)


def parse_log_lines(jsonl_dicts: list[dict]) -> list[AbstractLogLine]:
    """Parse jsonl dicts into LogLine objects"""
    log_lines = []
    for line in jsonl_dicts:
        assert isinstance(line, dict), f"Expected dict, got {type(line)}"
        log_line: AbstractLogLine
        if "final_report" in line:
            log_line = LogFinalReport(
                final_report=line["final_report"],
            )

        elif "spec" in line:
            log_line = LogSpec(
                run_id=line["spec"]["run_id"],
                created_by=line["spec"]["created_by"],
                created_at=line["spec"]["created_at"],
                spec=line["spec"],
            )

        elif "type" in line:
            if line["type"] == "sampling":
                # parse prompt into ChatPrompt or BasePrompt depending on datatype
                prompt: Prompt
                if isinstance(line["data"]["prompt"], str):
                    prompt = BasePrompt(data=line["data"]["prompt"])
                elif isinstance(line["data"]["prompt"], list):
                    prompt = ChatPrompt(data=line["data"]["prompt"])
                else:
                    raise ValueError(
                        f"Unknown type for prompt type: {type(line['data']['prompt'])}"
                    )

                log_line = LogSampling(
                    run_id=line["run_id"],
                    created_by=line["created_by"],
                    created_at=line["created_at"],
                    event_id=line["event_id"],
                    sample_id=line["sample_id"],
                    prompt=prompt,
                    sampled=line["data"]["sampled"],
                )
            elif line["type"] in ["metrics", "match"]:
                log_line = LogMetrics(
                    run_id=line["run_id"],
                    created_by=line["created_by"],
                    created_at=line["created_at"],
                    event_id=line["event_id"],
                    sample_id=line["sample_id"],
                    data=line["data"],
                )
            else:
                print(f"Unknown line type: {line['type']}")
                continue

        else:
            print(f"Unknown line type: {line}")
            continue
        log_lines.append(log_line)
    return log_lines


def build_trajectories(log_lines: list[AbstractLogLine]):
    """Starting with pages, modify the sorted_samples to
    build a single trajectory for each sample_id"""
    pages = build_pages(log_lines)
    for page in pages:
        seen_texts: dict[str, str] = dict()
        samples = page.samples
        combined_sample_messages = []
        message_index = 0
        for sample in reversed(samples):
            # adding non-duplicate sample messages
            assert isinstance(sample.prompt, ChatPrompt)
            for message in sample.prompt.data:
                role_with_i = f"{message_index} | {message['role']}"
                if message["content"] in seen_texts:
                    duplicate_message = seen_texts[message["content"]]
                    combined_sample_messages.append(
                        {"role": role_with_i, "content": f"[duplicate of {duplicate_message}]"}
                    )
                else:
                    combined_sample_messages.append(
                        {"role": role_with_i, "content": message["content"]}
                    )
                    seen_texts[message["content"]] = role_with_i
                message_index += 1
            # adding the sampled text as an 'assistant' message
            assert len(sample.sampled) == 1, f"Expected 1 sampled text, got {len(sample.sampled)}"
            combined_sample_messages.append(
                {"role": f"{message_index} | assistant", "content": sample.sampled[0]}
            )
            message_index += 1
        # TODO (ian): work out why this is a type error
        page.samples = [ChatPrompt(data=combined_sample_messages)]  # type: ignore
    return pages


def build_pages(
    log_lines: list[AbstractLogLine],
    sort_descending: bool = True,
) -> list[LogPage]:
    """Take the individual jsonl lines and group them by sample_id, then
    separate out the sampling from the metrics"""
    sampling_data: dict[str, list[LogSampling]] = defaultdict(list)
    metrics_data: dict[str, LogMetrics] = dict()
    final_report: LogFinalReport | None = None
    log_spec: LogSpec | None = None
    for line in log_lines:
        if isinstance(line, LogSpec):
            log_spec = line
        elif isinstance(line, LogFinalReport):
            final_report = line
        elif isinstance(line, LogMetrics):
            metrics_data[line.sample_id] = line
        elif isinstance(line, LogSampling):
            sampling_data[line.sample_id].append(line)
        else:
            raise ValueError(f"Unknown line type {type(line)}")

    # build the actual LogPage objects from the page data
    pages = []
    keys = list(sampling_data.keys())
    if set(keys) != set(metrics_data.keys()):
        print(f"Warning: {len(keys)} samples, but {len(metrics_data)} metrics")
    for sample_id in keys:
        # TODO: use casting here?
        samples: list[LogSampling] = sampling_data[sample_id]  # type: ignore
        # make dummy metrics if we don't have any
        if sample_id not in metrics_data:
            metrics = LogMetrics(
                run_id="",
                created_by="",
                created_at="",
                event_id=0,
                sample_id=sample_id,
                data={"note": "no metrics found for this sample!"},
            )
        else:
            metrics: LogMetrics = metrics_data[sample_id]  # type: ignore
        assert isinstance(samples, list), f"samples is {type(samples)}"
        assert all(isinstance(s, LogSampling) for s in samples), f"samples is {type(samples)}"
        assert isinstance(metrics, LogMetrics), f"metrics is {type(metrics)}"

        if sort_descending:
            sorted_samples = sorted(samples, key=lambda x: -x.event_id)
        else:
            sorted_samples = sorted(samples, key=lambda x: x.event_id)
        page = LogPage(
            sample_id=sample_id,
            samples=sorted_samples,
            metrics=metrics,
            log_spec=log_spec,
            final_report=final_report,
        )
        pages.append(page)
    return sorted(pages, key=lambda x: int(x.sample_id.split(".")[-1]))


def filter_pages(
    pages: list[LogPage],
    search_metrics: str | None = None,
    keywords: str | None = None,
) -> list[LogPage]:
    target_metrics = ast.literal_eval(search_metrics) if search_metrics else None
    target_keywords = keywords.split(",") if keywords else None
    filtered_pages = []
    for page in pages:
        include_page = True
        # check for matching metrics
        metrics = page.metrics
        sorted_samples = page.samples
        if target_metrics:
            for key in target_metrics:
                if key not in metrics.data:
                    print(f"Warning: {key} not in metrics")
                else:
                    # Only add pages that match the metric search
                    if metrics.data[key] != target_metrics[key]:
                        include_page = False
        # check for matching keywords
        if target_keywords:
            for keyword in target_keywords:
                if all(not sample.prompt.contains(keyword) for sample in sorted_samples):
                    include_page = False

        if include_page:
            filtered_pages.append(page)
    return filtered_pages


def get_lines(path: str) -> list[dict]:
    # pre-conditions
    assert os.path.exists(path)

    with jsonlines.open(path) as reader:
        lines = [obj for obj in reader if obj.get("type") == "sampling"]

    for obj in lines:
        assert isinstance(obj, dict)
        assert "data" in obj
        assert "prompt" in obj["data"]
        assert isinstance(obj["data"]["prompt"], list)

    # body
    sorted_lines = sorted(
        lines,
        key=lambda obj: len(obj["data"]["prompt"]),
        reverse=True,
    )

    # post-conditions
    assert all("data" in obj for obj in sorted_lines)
    assert all("prompt" in obj["data"] for obj in sorted_lines)
    assert all("sampled" in obj["data"] for obj in sorted_lines)

    return sorted_lines
