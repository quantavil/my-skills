"""Typed schemas for phase records and MCP receipts."""
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator


def validation_message(error):
    issue = error.errors()[0]
    location = '.'.join(map(str, issue['loc']))
    return f"{location}: {issue['msg']}" if location else issue['msg']


def unique(values):
    if len(values) != len(set(values)):
        raise ValueError('list contains duplicates')
    return values


ID_PATTERN = r'^[a-z0-9][a-z0-9_]*$'
Id = Annotated[str, StringConstraints(pattern=ID_PATTERN)]
Text = Annotated[str, StringConstraints(min_length=1)]
Strings = Annotated[list[Text], AfterValidator(unique)]
Positive = Annotated[int, Field(gt=0, strict=True)]
Hex64 = Annotated[str, StringConstraints(pattern=r'^[0-9a-f]{64}$')]
Artifact = Literal['png', 'xml', 'trace', 'state', 'network', 'semantics']
Dimension = Literal['visual', 'layout', 'behavior', 'navigation', 'persistence',
                    'platform', 'network', 'accessibility']
State = Literal['preflight', 'collecting_original', 'oracle_frozen', 'implementing',
                'comparing', 'correcting', 'automated_ready', 'human_accepted', 'blocked']


class Record(BaseModel):
    model_config = ConfigDict(strict=True, extra='allow')


class Scope(Record):
    summary: str
    unknowns: list[Any]


class PathRule(Record):
    glob: str
    components: Annotated[Strings, Field(min_length=1)]

    @field_validator('glob')
    @classmethod
    def safe_glob(cls, value):
        if not value or value.startswith('/') or '\\' in value or '..' in PurePosixPath(value).parts:
            raise ValueError('dependency path rule has an unsafe glob')
        return value


class DependencyGraph(Record):
    components: Annotated[list[Id], AfterValidator(unique)]
    path_rules: list[PathRule]
    component_edges: dict[Id, Strings]


class Checkpoint(Record):
    number: Annotated[int, Field(ge=1, le=999, strict=True)]
    id: Id
    fixture: str
    setup: str
    actions: Strings
    artifacts: Annotated[list[Artifact], Field(min_length=1), AfterValidator(unique)]
    required_dimensions: Annotated[list[Dimension], Field(min_length=1), AfterValidator(unique)]
    dependencies: Strings


class ReverseEngineering(Record):
    include_globs: Strings
    questions: list[Any]


class ContractModel(Record):
    schema_version: Literal[1]
    phase_id: Id
    revision: Positive
    scope: Scope
    platform: Literal['android_flutter', 'ios_flutter']
    fixtures: dict[Id, dict[str, Any]]
    dependency_graph: DependencyGraph
    checkpoints: list[Checkpoint]
    reverse_engineering: ReverseEngineering
    ownership: dict[str, Any]
    authorized_differences: list[Any]

    @model_validator(mode='after')
    def linked_ids(self):
        graph = self.dependency_graph
        components = set(graph.components)
        for rule in graph.path_rules:
            if set(rule.components) - components:
                raise ValueError('dependency path rule has unknown components')
        for source, targets in graph.component_edges.items():
            if source not in components or set(targets) - components:
                raise ValueError('component edge has unknown dependencies')
        numbers, identifiers = set(), set()
        for checkpoint in self.checkpoints:
            if checkpoint.number in numbers or checkpoint.id in identifiers:
                raise ValueError('duplicate checkpoint number or id')
            numbers.add(checkpoint.number)
            identifiers.add(checkpoint.id)
            if checkpoint.fixture not in self.fixtures:
                raise ValueError(f'checkpoint {checkpoint.id} references unknown fixture')
            if set(checkpoint.dependencies) - components:
                raise ValueError(f'checkpoint {checkpoint.id} has unknown dependency')
        return self


class HumanReview(Record):
    status: Literal['pending', 'accepted', 'changes_requested']
    history: list[Any]


class StatusModel(Record):
    schema_version: Literal[1]
    phase_id: Id
    phase_revision: Positive
    state: State
    checkpoints: dict[str, dict[str, Any]]
    preflight_revision: Positive | None
    original_manifest_revision: Positive | None
    active_clone_manifest_revision: Positive | None
    clone_manifest_revisions: list[Positive]
    invalidation_history: list[Any]
    human_review: HumanReview
    blockers: list[Any]


class ReceiptModel(Record):
    schema_version: Literal[1]
    capability: Literal['jadx', 'apktool', 'r2flutter', 'mobile-control']
    server: Text
    tool: Text
    tool_version: Text
    session_id: Text
    observed_at: str
    request_sha256: Hex64
    response_sha256: Hex64
    status: Literal['healthy']
    provenance: Literal['mcp']
    limitations: list[Any]
    target: dict[str, Any]
    probes: dict[str, bool] | None = None
    environment: dict[str, Any] | None = None
    screenshot_sha256: Hex64 | None = None
    supported: bool | None = None
    abi: str | None = None
    dart_profile: str | None = None

    @field_validator('server', 'tool', 'tool_version', 'session_id')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('receipt identity field must not be blank')
        return value

    @field_validator('observed_at')
    @classmethod
    def valid_observed_at(cls, value):
        try:
            moment = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            raise ValueError('MCP receipt observed_at must be an ISO timestamp') from None
        if moment.tzinfo is None:
            raise ValueError('MCP receipt observed_at must include a timezone')
        if (datetime.now(timezone.utc) - moment).total_seconds() < -300:
            raise ValueError('MCP receipt is dated in the future')
        return value
