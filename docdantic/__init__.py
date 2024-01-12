import re
import tabulate
import importlib
import json
from enum import Enum
from types import UnionType, NoneType
from importlib.metadata import version
from collections import namedtuple
from markdown import Markdown
from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor
from pydantic.version import VERSION as PYDANTIC_VERSION
from pydantic import BaseModel
from typing import Any, Type, Union, Literal, Generic, TypeVar, get_origin, get_args

T = TypeVar("T")

if PYDANTIC_VERSION.startswith("1."):
    from pydantic.fields import Undefined as PydanticUndefined  # type: ignore
    from pydantic.generics import GenericModel  # type: ignore
    _model_dump = lambda model, *args, **kwargs: model.dict(*args, **kwargs)
    _get_field_annotation = lambda field: field.type_
    _get_required = lambda field: field.required
    _get_fields = lambda model: model.__fields__
else:
    from pydantic_core import PydanticUndefined  # type: ignore
    GenericModel = Generic
    _model_dump = lambda model, *args, **kwargs: model.model_dump(*args, **kwargs)
    _get_field_annotation = lambda field: field.annotation
    _get_required = lambda field: field.is_required()
    _get_fields = lambda model: model.model_fields

__version__ = version(__package__)
ModelFieldInfo = namedtuple("ModelFieldInfo", "name type required default")


def is_typing_union(obj: Any) -> bool:
    """
    Check if the given object is a typing.Union.

    :param obj: Object to check.
    :return: True if the object is a typing.Union, False otherwise.
    """
    return get_origin(obj) is Union


def is_typing_literal(obj: Any) -> bool:
    """
    Check if the given object is a typing.Literal.

    :param obj: Object to check.
    :return: True if the object is a typing.Literal, False otherwise.
    """
    return get_origin(obj) is Literal


def is_pydantic_model(obj: Type | None) -> bool:
    """
    Check if the given object is a Pydantic model.

    :param obj: Object to check.
    :return: True if the object is a Pydantic model, False otherwise.
    """
    if obj is None:
        return False
    if isinstance(obj, (list, tuple)):
        return any(is_pydantic_model(o) for o in obj)
    if isinstance(obj, type) and issubclass(obj, BaseModel):
        return True
    if isinstance(obj, BaseModel):
        return True
    return False


def submodel_link(sub_model: str):
    """
    Create a Markdown link to the given submodel.

    :param sub_model: Name of the submodel.
    :return: Markdown link to the submodel.
    """
    sub_model_slug = sub_model.lower()
    return f'[{sub_model}](#{sub_model_slug})'


def highlight_name(name: str):
    """
    Highlight a name using Markdown bold syntax.

    :param name: Name to highlight.
    :return: Highlighted name.
    """
    return f"**{name}**"


def import_class(path: str):
    """
    Import a class from a module given its full path.

    :param path: Full path to the class (module.Class).
    :return: The class if found, None otherwise.
    """
    split = path.rsplit(".", 1)

    if len(split) < 2:
        raise ValueError(f"Invalid path: {path}")

    module_name, class_name = split
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError:
        return None

    return getattr(module, class_name, None)


def extract_configuration(index, lines):
    """
    Extract configuration from the lines starting from a given index.
    The configuration must be indented by at least two spaces.

    :param index: Current index in the lines.
    :param lines: All lines of the document.
    :return: Configuration and new index.
    """
    config = {}
    json_string = ''
    capture = False
    braces_count = 0

    # Define the regex pattern to match at least 2 spaces of indentation.
    indent_pattern = re.compile(r"^\s{2,}")

    for current_index, line in enumerate(lines[index:], start=index):
        if indent_pattern.match(line):
            stripped_line = line.strip()

            if '{' in stripped_line:
                braces_count += stripped_line.count('{')
                if not capture:
                    capture = True

            if capture:
                json_string += stripped_line

            if '}' in stripped_line:
                braces_count -= stripped_line.count('}')
                if braces_count <= 0:
                    break
        elif capture:
            # Break if indentation is less than 2 and we are already capturing.
            break

    try:
        config = json.loads(json_string)
    except json.JSONDecodeError as e:
        print("Error parsing JSON:", e)

    # Adjust the index to point to the line after the JSON block
    return config, current_index + 1


def get_default_string(default: Any):
    """
    Get a string representation of the default value of a field.

    :param field: Field to process.
    :return: String representation of the default value.
    """
    if default == PydanticUndefined:
        return "..."
    elif default is not None and is_pydantic_model(default):
        return str(_model_dump(default))
    elif isinstance(default, Enum):
        return str(default.value)
    elif default is not None:
        return str(default)
    else:
        return ""


def get_annotation_string(annotation: Any):
    """
    Get a string representation of the annotation of a field.

    :param annotation: Annotation to process.
    :return: String representation of the annotation.
    """
    if annotation is None or isinstance(annotation, NoneType) or annotation is NoneType:
        return "None"
    elif isinstance(annotation, UnionType) or is_typing_union(annotation):
        return f"Union[{', '.join([get_annotation_string(a) for a in get_args(annotation)])}]"
    elif is_typing_literal(annotation):
        return f"Literal[{', '.join([repr(a) for a in get_args(annotation)])}]"
    elif is_pydantic_model(annotation):
        return submodel_link(annotation.__name__)

    return str(annotation.__name__)


def get_field_info(
    model: Any,
    config: dict | None = None,
    models: dict | None = None
) -> dict[str, list[ModelFieldInfo]]:
    """
    Get information about the fields of a model.

    :param model: The model to inspect.
    :param config: Configuration for the inspection.
    :param models: Already inspected models to avoid circular references.
    :return: List of fields of the model.
    """
    if models is None:
        models = {}
    if config is None:
        config = {}

    fields: list[ModelFieldInfo] = []
    model_name = model.__name__

    if model_name in config.get("exclude", {}) and config["exclude"][model_name] == "*":
        # Skip models that are explicitly excluded
        return {}

    models[model_name] = fields

    for name, field in _get_fields(model).items():
        if model_name in config.get("exclude", {}) and name in config["exclude"][model_name]:
            # Skip fields that are explicitly excluded
            continue

        annotation = _get_field_annotation(field)
        annotation_str = get_annotation_string(annotation)
        default = get_default_string(field.default)
        required = str(_get_required(field))

        if is_pydantic_model(annotation):
            get_field_info(annotation, config, models)
        elif is_typing_union(annotation):
            for arg in get_args(annotation):
                if is_pydantic_model(arg):
                    get_field_info(arg, config, models)

        fields.append(
            ModelFieldInfo(highlight_name(name), annotation_str, required, default)
        )

    return models


def render_table(model_path: str, config: dict) -> str:
    """
    Render a table with the fields of a model.

    :param model_path: Full path to the model.
    :param config: Configuration for the generation.
    :return: Rendered table or an empty string if the model was not found.
    """
    model = import_class(model_path)

    if model:
        field_info = get_field_info(model, config)

        tables = {
            cls: tabulate.tabulate(
                [
                    (field.name, field.type, field.required, field.default,)
                    for field in fields
                ],
                headers=["Name", "Type", "Required", "Default"],
                tablefmt="github"
            )
            for cls, fields in field_info.items()
        }

        return '\n'.join(
            f"\n### {cls}\n\n{table}\n"
            for cls, table in tables.items()
        )

    print(f"Found no Model at `{model_path}`")
    return ""


def process_line(index: int, lines: list[str]):
    """
    Process a line and generate a table if needed.

    :param index: Current index in the lines.
    :param lines: All lines of the document.
    :return: Processed line and new index.
    """
    line = lines[index]
    if match := re.match(r"^\!docdantic: (.*)$", line):
        model_path = match.group(1)
        model_config, index = extract_configuration(index, lines)
        table = render_table(model_path, model_config)
        if table:
            return table, index  # Return index to update loop counter
    return line, index


class DocdanticPreprocessor(Preprocessor):
    def __init__(self, markdown: Markdown):
        super().__init__(markdown)

    def run(self, lines: list[str]):
        parsed_lines = []
        index = 0

        while index < len(lines):
            processed_line, index = process_line(index, lines)
            parsed_lines.append(processed_line)
            index += 1

        return parsed_lines


class Docdantic(Extension):
    def extendMarkdown(self, markdown: Markdown):  # pragma: no cover
        markdown.preprocessors.register(
            item=DocdanticPreprocessor(markdown),
            name="docdantic",
            priority=999
        )


def makeExtension(*_, **__):  # pragma: no cover
    return Docdantic()
