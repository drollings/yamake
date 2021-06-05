This jsonmake tool is meant to replace platform-specific Makefiles and
scripts.  Only the dependency tracking functionality is currently enabled.

It is lightweight, and its primary advantage over make is that targets
have both dependencies and provides, and provides allow for a duck-typing
style of abstraction.

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

Depending on how files can be imported from Nexus Mods, this could evolve
into a package-management solution, faster than most currently on Windows,
and an option for those playing the Witcher 3 through compatibility layers
on MacOS and Linux.

