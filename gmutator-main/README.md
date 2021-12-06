# GMutator
A grammar-based mutator plugin for AFL++. It scores each 
DOM(AST) leaf to learn what fields to mutate and 
increase code coverage.

## Prerequisites
1. You need to use Python 3.8 or later
   
2. Install required packages with `python3 -m pip install -r requirements.txt`
   
3. You need to have GCC compiler installed.
   
4. Check [formatfuzzer binding](/core/formatfuzzer)
   for more information about compiling c++ wrappers.
   
5. Make sure you're using our special version of AFL++ 
   at https://github.com/LWC-ECE653/AFLplusplus, otherwise
   havoc and stats may not work properly.
   
## How to run
1. Set up environmental variables
```shell
export PYTHONPATH={absolute path to this folder}
export AFL_PYTHON_MODULE={format to use}_mutator
```
   
2. Run AFL++ and it should automatically load this module

## How to add new formats
1. Find the template for your format at https://www.sweetscape.com/010editor/repository/templates/, 
   and put it into [templates](/core/templates) folder.

2. In [FormatFuzzer](https://github.com/uds-se/FormatFuzzer), run `./build.sh {format}`. 
   Once compilation succeeded, you should find a file with name `{format}.cpp`. Copy that
   file into [formatfuzzer formats](/core/formatfuzzer/formats) folder, and then re-compile
   [formatfuzzer binding](/core/formatfuzzer/README.md).
   
3. Make sure the template file has its name in uppercase, the cpp file has 
   its name in lowercase.
   
4. Add your new format to "FORMAT" enum under [core module](/core/__init__.py). Note that 
   the enum's name must be in uppercase, and the enum's value must be in lowercase.
   
5. Create a new python file with name "{format}_mutator.py". Copy the content 
   of [mp4_mutator](mp4_mutator.py) into this new file, and replace "mp4" with your new format.
   
## References
1. FormatFuzzer: https://github.com/uds-se/FormatFuzzer
2. PFP: https://pfp.readthedocs.io/en/latest/#
3. AFL++: https://github.com/AFLplusplus/AFLplusplus
4. 010 Editor -- Binary Templates: https://www.sweetscape.com/010editor/templates.html


