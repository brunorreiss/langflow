import inspect
from typing import TYPE_CHECKING, AsyncIterator, Awaitable, Callable, ClassVar, Generator, Iterator, List, Optional

import yaml
from loguru import logger
from pydantic import BaseModel

from langflow.schema.schema import Record
from langflow.template.field.base import Input, Output

from .custom_component import CustomComponent

if TYPE_CHECKING:
    from langflow.graph.vertex.base import Vertex


def recursive_serialize_or_str(obj):
    try:
        if isinstance(obj, dict):
            return {k: recursive_serialize_or_str(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [recursive_serialize_or_str(v) for v in obj]
        elif isinstance(obj, BaseModel):
            return {k: recursive_serialize_or_str(v) for k, v in obj.model_dump().items()}
        elif isinstance(obj, (AsyncIterator, Generator, Iterator)):
            # Turn it into something readable that does not
            # contain memory addresses
            # without consuming the iterator
            # return list(obj) consumes the iterator
            # return f"{obj}" this generates '<generator object BaseChatModel.stream at 0x33e9ec770>'
            # it is not useful
            return "Unconsumed Stream"
    except Exception:
        return str(obj)


class Component(CustomComponent):
    inputs: Optional[List[Input]] = None
    outputs: Optional[List[Output]] = None
    code_class_base_inheritance: ClassVar[str] = "Component"

    def set_attributes(self, params: dict):
        for key, value in params.items():
            if key in self.__dict__:
                raise ValueError(f"Key {key} already exists in {self.__class__.__name__}")
            setattr(self, key, value)

    async def build_results(self, vertex: "Vertex"):
        build_results = {}

        if hasattr(self, "outputs"):
            for output in self.outputs:
                # Build the output if it's connected to some other vertex
                # or if it's not connected to any vertex
                if not vertex.outgoing_edges or output.name in vertex.edges_source_names:
                    method: Callable | Awaitable = getattr(self, output.method)
                    result = method()
                    # If the method is asynchronous, we need to await it
                    if inspect.iscoroutinefunction(method):
                        result = await result
                    build_results[output.name] = result
        self.build_results = build_results
        return build_results

    def custom_repr(self):
        # ! Temporary REPR
        # Since all are dict, yaml.dump them
        if isinstance(self.build_results, dict):
            _build_results = recursive_serialize_or_str(self.build_results)
            try:
                custom_repr = yaml.dump(_build_results)
            except Exception as e:
                logger.error(f"Error while dumping build_result: {e}")
                custom_repr = str(self.build_results)

        if custom_repr is None and isinstance(self.build_results, (dict, Record, str)):
            custom_repr = self.build_results
        if not isinstance(custom_repr, str):
            custom_repr = str(custom_repr)
        return custom_repr