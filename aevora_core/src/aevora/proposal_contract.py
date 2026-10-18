"""Public machine-readable proposal grammar, not repair advice or authority."""
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field
from .models import PUBLIC_CONTEXT_FACTS

FactKey=Literal[tuple(sorted(PUBLIC_CONTEXT_FACTS))]
FactScalar=str|int|float|bool|None


class SourceReference(BaseModel):
    model_config=ConfigDict(extra='forbid')
    kind:Literal['Query','Decision','ObservedAction']
    id:str=Field(min_length=1,max_length=240,description='Actual graph identity returned in this scoped Run')


class CandidateProposal(BaseModel):
    model_config=ConfigDict(extra='forbid')
    candidate_key:str=Field(min_length=1,max_length=64,pattern=r'^[A-Za-z0-9][A-Za-z0-9_.@+\-]{0,63}$')
    title:str=Field(min_length=1,max_length=4000)
    strategy:str=Field(min_length=1,max_length=4000,description='Observed engineering principle as untrusted narrative')
    public_summary:str=Field(min_length=1,max_length=4000)
    necessary_conditions:dict[FactKey,list[FactScalar]]=Field(min_length=1,
        description='OBJECT mapping public semantic fact names to allowed scalar ARRAYS; NOT a list of sentences')
    inapplicable_conditions:dict[FactKey,list[FactScalar]]=Field(
        description='OBJECT of factual exclusion conditions. Empty object if none established; narrative limitations belong in limitations')
    scope:dict[FactKey,list[FactScalar]]=Field(min_length=1,
        description='OBJECT of bounded factual conditions from real context. Do not invent unknown factual values')
    unknown_fields:list[FactKey]=Field(max_length=32,
        description='Public fact NAMES whose values are unproved. Free-text uncertainty goes in limitations. Required unknown premises remain pending')
    limitations:list[str]=Field(max_length=32)
    source_references:list[SourceReference]=Field(max_length=32)
