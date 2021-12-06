#!/usr/bin/env python

from invoke import task
from os import listdir
from os.path import isfile, join
from string import Template

formats_dir = "formats"

def get_format_cpp_files():
    return [f for f in listdir(formats_dir) if isfile(join(formats_dir, f)) and '.cpp' in f]

@task
def clean(c, docs=False, bytecode=False, extra=''):
    c.run("rm -r wrappers/*.so")

@task
def build(c, docs=False):
    for cpp_file in get_format_cpp_files():
        format_name = cpp_file.split('.')[0]

        with open('pybind11.template', 'r') as f:
            src = Template(f.read())
            binding = src.substitute({'format': format_name})

        with open('pyformatfuzzer.cpp', 'w') as f:
            f.write(binding)

        c.run(f"g++ -O3 -Wall -shared -std=c++17 "
              f"-fPIC $(python3 -m pybind11 --includes) "
              f"-I . pyformatfuzzer.cpp fuzzer.cpp {formats_dir}/{format_name}.cpp "
              f"-o wrappers/pyff_{format_name}$(python3-config --extension-suffix)")

        c.run("rm pyformatfuzzer.cpp")