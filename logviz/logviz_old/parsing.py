import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


@dataclass(frozen=True)
class FunctionCall:
    name: str
    arguments: dict[str, str]
    return_value: str

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "arguments": self.arguments,
            "return_value": self.return_value,
        }


@dataclass(frozen=True)
class ChatCompletionMessage:
    role: str
    content: Optional[str]
    function_call: Optional[FunctionCall] = None

    def to_dict(self) -> dict:
        data: dict[str, Any] = {
            "role": self.role,
            "content": self.content,
        }

        if self.function_call is not None:
            data["function_call"] = self.function_call.to_dict()

        return data


@dataclass(frozen=True)
class SamplingEvent:
    run_id: str
    event_id: int
    sample_id: str
    prompt: list[ChatCompletionMessage]
    sampled: list[str]

    @staticmethod
    def from_dict(data: dict) -> "SamplingEvent":
        return SamplingEvent(
            run_id=data["run_id"],
            event_id=data["event_id"],
            sample_id=data["sample_id"],
            prompt=[
                ChatCompletionMessage(role=m["role"], content=m["content"])
                for m in data["data"]["prompt"]
            ],
            sampled=data["data"]["sampled"],
        )


@dataclass(frozen=True)
class FunctionCallEvent:
    run_id: str
    event_id: int
    sample_id: str
    name: str
    arguments: dict[str, str]
    return_value: str

    @staticmethod
    def from_dict(data: dict) -> "FunctionCallEvent":
        return FunctionCallEvent(
            run_id=data["run_id"],
            event_id=data["event_id"],
            sample_id=data["sample_id"],
            name=data["data"]["name"],
            arguments=data["data"]["arguments"],
            return_value=data["data"]["return_value"],
        )


def get_events(lines: list[dict]) -> list[SamplingEvent | FunctionCallEvent]:
    # pre-conditions
    assert isinstance(lines, list)
    assert all(isinstance(line, dict) for line in lines)

    # body
    events: list[SamplingEvent | FunctionCallEvent] = []

    for line in lines:
        data = None

        try:
            data = SamplingEvent.from_dict(line)
        except KeyError:
            pass

        try:
            data = FunctionCallEvent.from_dict(line)  # type: ignore
        except KeyError:
            pass

        if data is None:
            continue

        events.append(data)

    # post-conditions
    assert isinstance(events, list)
    assert all(isinstance(event, (SamplingEvent, FunctionCallEvent)) for event in events)

    return events


def _get_sampling_to_fn_call_mapping(
    events: list[SamplingEvent | FunctionCallEvent],
) -> dict[str, FunctionCallEvent]:
    # pre-conditions
    assert isinstance(events, list)
    assert all(isinstance(event, (SamplingEvent, FunctionCallEvent)) for event in events)

    # body
    events = sorted(events, key=lambda event: event.event_id)
    ctofn: dict[str, FunctionCallEvent] = dict()

    for event, other_event in zip(events, events[1:]):
        if not isinstance(event, SamplingEvent):
            continue

        if not isinstance(other_event, FunctionCallEvent):
            continue

        assert len(event.sampled) == 1
        assert event.event_id + 1 == other_event.event_id

        content = event.sampled[0]

        assert content not in ctofn

        ctofn[content] = other_event

    # post-conditions
    assert isinstance(ctofn, dict)
    assert all(isinstance(key, str) or key is None for key in ctofn.keys()), ctofn.keys()
    assert all(isinstance(value, FunctionCallEvent) for value in ctofn.values())

    return ctofn


def get_timeline(
    events: list[SamplingEvent | FunctionCallEvent],
) -> list[ChatCompletionMessage]:
    # pre-conditions
    assert isinstance(events, list)
    assert all(isinstance(event, (SamplingEvent, FunctionCallEvent)) for event in events)

    # body
    to_fn_call = _get_sampling_to_fn_call_mapping(events)
    longest_sampling_event = None

    for event in events:
        if not isinstance(event, SamplingEvent):
            continue

        if longest_sampling_event is None:
            longest_sampling_event = event

        if len(event.prompt) > len(longest_sampling_event.prompt):
            longest_sampling_event = event

    assert longest_sampling_event is not None

    timeline: list[ChatCompletionMessage] = []

    for m in longest_sampling_event.prompt:
        if not isinstance(m, ChatCompletionMessage):
            continue

        if m.content in to_fn_call:
            fn_call = FunctionCall(
                name=to_fn_call[m.content].name,
                arguments=to_fn_call[m.content].arguments,
                return_value=to_fn_call[m.content].return_value,
            )

            m = ChatCompletionMessage(
                role=m.role,
                content=m.content,
                function_call=fn_call,
            )

        timeline.append(m)

    last_sampled_message = ChatCompletionMessage(
        role="sampled",
        content=longest_sampling_event.sampled[0],
    )

    timeline.append(last_sampled_message)

    # post-conditions
    assert isinstance(timeline, list)
    assert all(isinstance(event, ChatCompletionMessage) for event in timeline)

    return timeline


def get_lines(fname: str) -> list[dict]:
    # pre-conditions
    fpath = Path(fname)

    if not fpath.exists():
        raise FileNotFoundError(f"File {fname} does not exist!")

    # body
    lines: list[dict] = []

    with open(fname, "r") as f:
        for line in f.readlines():
            line = line.strip()

            if line == "":
                continue

            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            lines.append(data)

    # post-conditions
    assert isinstance(lines, list)
    assert all(isinstance(line, dict) for line in lines)

    return lines
