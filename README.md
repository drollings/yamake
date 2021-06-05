This jsonmake tool is currently a Python script that uses JSON files to 
replace platform-specific Makefiles and scripts.  Only the dependency 
tracking functionality is currently enabled.

If you need a mature tool for this sort of thing, I recommend meson or redo.

It is lightweight, and its primary advantage over make apart from cleaner 
syntax and cross-platform potential is that its targets have both dependencies 
and provides, and this allows for a duck-typing style of abstraction.

The first use case is managing Witcher 3 mods on Linux, but the tool isn't 
specific to that use case.

In the current working directory, we expect a jsonmake.json, 
and the shown directory layout.  Each layer's ro tree contains files to
link, and rw tree contains files to unlink in the destination if already
found, and then copy.

The repo folder should contain a git repository from which layers can be
built when needed.

A jsonmake_config.json file is sought at the current working directory,
or in ~/.config - or it can be manually specified.  It should contain all
variables specific to the user's machine, which are referenced in the
jsonmake.json which should be usable to anyone with the layers directory
and git repo initialized.
