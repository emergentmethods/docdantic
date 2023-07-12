# Docdantic

![PyPI - Python Version](https://img.shields.io/pypi/pyversions/docdantic?style=flat-square)

Docdantic is a Python library that enables the automatic generation of Markdown documentation from Pydantic v2 models. It works as an extension of the Markdown package, extracting model details and creating neat tables with model fields and their properties.


## Features

* Automatically generate tables of Pydantic v2 model fields with their details (name, type, required, default).
* Supports nested Pydantic v2 models.
* Configurable exclusion of specific fields from the documentation.


## Installation

```bash
pip install docdantic
```

## Usage

### Using the Docdantic Extension

To generate documentation directly from Markdown files, you can use the Docdantic extension. Simply include the `!docdantic: import.path.to.Model` directive in your Markdown text:

```markdown
# MyModel Reference

!docdantic: my_module.MyModel
```

Docdantic will replace the !docdantic directive with a table of model field details.

### Using Docdantic in Python Code

If you want to programmatically generate Markdown documentation from Pydantic v2 models, you can use Docdantic in your Python code. Here's an example:

```python
import markdown
from docdantic import Docdantic

markdown_text = "Here are the details of my model:\n\n!docdantic: your.model.path"
converted_text = markdown.markdown(markdown_text, extensions=[Docdantic()])

# `converted_text` will contain the Markdown text with the model documentation
```

You can include the `!docdantic: your.model.path` directive in your Markdown text as before, and the `markdown.markdown` method will process it using the Docdantic extension.

## Configuration

Docdantic allows you to exclude specific fields from the generated documentation by using the exclude configuration. You can provide a JSON object in the exclude field of the configuration to specify which fields to exclude. For example:

```markdown
!docdantic: my_module.MyModel
    {
        "exclude": {
            "MyModel": ["field1", "field2"]
        }
    }
```

In the example above, the fields `field1` and `field2` will be excluded from the documentation of the `MyModel` model. Notice the configuration has to be indented with 2-4 spaces or a tab.

## License

This project is licensed under the terms of the MIT license. See [LICENSE](LICENSE) for more details.