The yamake tool is currently a Python script that uses YAML files to replace platform-specific Makefiles and scripts.  Only the dependency tracking functionality is currently enabled.  It is lightweight and built for extensibility, and its primary advantage over make apart from cleaner syntax and cross-platform potential is that its targets have both dependencies and provides, and this allows for a duck-typing style of abstraction over any means of establishing mtime or readiness.  The first test use case is managing Witcher 3 mods on Linux, but the tool isn't specific to that use case.

If you need a mature tool for this sort of thing, I recommend meson or redo, or even ansible.

A yamake_config.yaml file is sought at the current working directory, or in ~/.config - or it can be manually specified.  It should contain all variables specific to the user's machine, which are referenced in the yamake.yaml which should be usable to anyone with the layers directory and git repo initialized.

Handlers imported as plugins are specified in the configuration file, and they are intended to contain both optional expansions of the dependency tracking, and also any function that manipulate the data or write to disk.  This is so that the YAML can be coupled to implementations of extensions referenced in their structure.
