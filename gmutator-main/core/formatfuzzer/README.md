# FormatFuzzer Wrapper
This is a python wrapper for [FormatFuzzer](https://github.com/uds-se/FormatFuzzer)
using [pybind11](https://pybind11.readthedocs.io/en/latest/index.html).

## Instructions
To build, run
```shell
invoke build
```
and wrapper for each format will appear under the "wrappers" folder.

To clean, run
```shell
invoke clean
```

To import as a module in Python, use
```python
from core.formatfuzzer.wrappers import pyff_{FORMAT_NAME}
```
Currently, there's only one method `generate_random()` which
generates random data with correct grammar.