from dataclasses import dataclass, field
from typing import List, Literal, Optional, Dict, Any


@dataclass
class ConversationSegment:
    speaker: str
    text: str
    timestamp_start: Optional[float] = None
    timestamp_end: Optional[float] = None


@dataclass
class ProjectMetadata:
    project_name: str = ""
    client_name: str = ""
    domain: str = ""


@dataclass
class FunctionalRequirement:
    id: str
    title: str
    description: str
    priority: Literal["Low", "Medium", "High"] = "Medium"
    actors: List[str] = field(default_factory=list)
    preconditions: List[str] = field(default_factory=list)
    postconditions: List[str] = field(default_factory=list)
    acceptance_criteria: List[str] = field(default_factory=list)
    source_quotes: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class NonFunctionalRequirement:
    id: str
    title: str
    description: str
    category: str = ""
    priority: Literal["Low", "Medium", "High"] = "Medium"
    source_quotes: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class Constraint:
    id: str
    description: str
    type: str = ""


@dataclass
class Assumption:
    id: str
    description: str


@dataclass
class Ambiguity:
    id: str
    type: Literal["missing_detail", "conflict", "vague_term", "implicit_requirement"]
    description: str
    severity: Literal["low", "medium", "high"] = "medium"
    section: str = ""
    evidence: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class FollowUpQuestion:
    id: str
    question: str
    priority: Literal["low", "medium", "high"] = "medium"
    linked_ambiguities: List[str] = field(default_factory=list)


@dataclass
class RequirementBundle:
    functional: List[FunctionalRequirement] = field(default_factory=list)
    non_functional: List[NonFunctionalRequirement] = field(default_factory=list)
    constraints: List[Constraint] = field(default_factory=list)
    assumptions: List[Assumption] = field(default_factory=list)


@dataclass
class PipelineState:
    metadata: ProjectMetadata = field(default_factory=ProjectMetadata)
    conversation: List[ConversationSegment] = field(default_factory=list)
    requirements: RequirementBundle = field(default_factory=RequirementBundle)
    ambiguities: List[Ambiguity] = field(default_factory=list)
    follow_up_questions: List[FollowUpQuestion] = field(default_factory=list)


