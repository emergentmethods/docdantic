import re
import tabulate
import json
import importlib
from importlib.metadata import version
from collections import namedtuple
from pydantic import BaseModel
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined
from markdown import Markdown
from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor
from typing import Type, Any

__version__ = version(__package__)
ModelFieldInfo = namedtuple("ModelFieldInfo", "name type required default")


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
    return False


def get_default_string(field: FieldInfo):
    """
    Get a string representation of the default value of a field.

    :param field: Field to process.
    :return: String representation of the default value.
    """
    if field.default == PydanticUndefined:
        return "..."
    elif field.default is not None and is_pydantic_model(field.default):
        return str(field.default.model_dump())
    elif field.default is not None:
        return str(field.default)
    else:
        return ""

def get_annotation_string(field: FieldInfo):
    """
    Get a string representation of the field's type annotation.

    :param field: Field to process.
    :return: String representation of the field's annotation.
    """
    if field.annotation is None:
        return "None"

    return str(field.annotation.__name__)


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


def get_field_info(model: Any, config: dict = {}, models: dict | None = None):
    """
    Get information about the fields of a model.

    :param model: The model to inspect.
    :param config: Configuration for the inspection.
    :param models: Already inspected models to avoid circular references.
    :return: A dictionary with the model's field information.
    """
    if models is None:
        models = {}

    fields: list[ModelFieldInfo] = []
    model_name = model.__name__
    models[model_name] = fields

    for name, field in model.__fields__.items():
        if model_name in config.get("exclude", {}) and name in config["exclude"][model_name]:
            # Skip fields that are explicitly excluded
            continue

        annotation = get_annotation_string(field)
        default = get_default_string(field)
        required = str(field.is_required())

        if is_pydantic_model(field.annotation):
            annotation = submodel_link(annotation)
            get_field_info(field.annotation, config, models)

        fields.append(
            ModelFieldInfo(highlight_name(name), annotation, required, default)
        )

    return models


def extract_configuration(index, lines):
    """
    Extract configuration from the lines.

    :param index: Current index in the lines.
    :param lines: All lines of the document.
    :return: Configuration and new index.
    """
    config = {}  # default configuration
    json_string = ''

    # Define the regex pattern for checking the start of the string.
    # It checks for a tab or 2-4 spaces.
    tab_pattern = re.compile(r"^[ \t]{2,4}")

    # Check for configuration in the next lines
    while index + 1 < len(lines):
        next_line = lines[index + 1]

        # Check if line starts with the defined pattern
        if not re.match(tab_pattern, next_line):
            break  # end of configuration block

        json_string += next_line.strip()  # Remove leading and trailing spaces
        try:
            config = json.loads(json_string)  # Try to parse JSON
            index += 1  # Move to next line
        except json.JSONDecodeError:
            index += 1  # Continue if the JSON is not yet fully extracted
            continue  # If the current JSON string is not valid, ignore it and continue

    return config, index


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
                [list(field) for field in fields],
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
