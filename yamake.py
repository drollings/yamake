#!/bin/env python3

# Daniel Rollings
# June 3, 2021

import yamake_builder
import os

_extra_doc = """
A simple make/build system around layer directories and git meant to operate
on the following directory structure:

.
|- game
|- layers
| |- layer
|   |- ro
|   |- rw
|- repo

Where at the current working directory, we expect a yamake.yaml file,
and the shown directory layout where every layer's ro tree contains files to
link, and rw tree contains files to unlink in the destination if already
found, and then copy.

The repo folder should contain a git repository from which layers can be
built when needed.
"""

RED = '\033[1;31m'
GRN = '\033[1;32m'
YEL = '\033[1;33m'
BLU = '\033[1;34m'
MAG = '\033[0;35m'
CYN = '\033[0;36m'
WHI = '\033[1;37m'
NRM = '\033[0m'

ERROR = '[%sERROR%s]' % (RED, NRM)
WARNING = '[%sWARNING%s]' % (YEL, NRM)
SUCCESS = '[%sSUCCESS%s]' % (GRN, NRM)
DEBUG = '[%sDEBUG%s]' % (MAG, NRM)
INFO = '[%sINFO%s]' % (BLU, NRM)
EXEC = '[%sEXEC%s]' % (CYN, NRM)
START = '[%sSTART%s]' % (WHI, NRM)

DIVIDER = '------------------------------------------------------------------------------'
HASHDIVIDER = '##############################################################################'
SPACES = '                                                                                '
 
############################################################
# Check a build dependency
# Returns: True/False success code, list of string output
def BuildCLI(options, args):
    builder = yamake_builder.Builder()

    if options.json_output:
        return True, builder.JSONOutput()

    dProviders = builder.Initialize(options.build, options.config)

    print('%-80.80s' % HASHDIVIDER)
    lTargets = None
    if len(args):
        lTargets = [builder.index[i] for i in args if i in builder.index]
        print("%-22s Attempting build from %s: %s" % (START, options.build, args))
    
    result, lQueue, lAmbiguous = builder.Enqueue(lTargets, dProviders)

    if not result:
        return False, []

    lOutput = []

    if len(lAmbiguous):
        lOutput.append('%-80.80s' % HASHDIVIDER)
        lOutput.append('%-26s Can not resolve for %s based on targets %s\n' % (ERROR, builder.lEssentials, lTargets))
        lOutput.append('%-36s %s' % ('AMBIGUOUS', 'POTENTIALLY PROVIDED BY'))
        for t in lAmbiguous:
            lProviders = []
            if t in dProviders:
                lProviders = [p.name for p in dProviders[t]]
                lProviders.sort()
            sCause = ''
            if len(lProviders):
                lProviders.sort()
                sCause = ', '.join(lProviders)
            elif not t.exists and not t.actions:
                sCause = 'No target, no possible providers'
            lOutput.append('%-36s %s' % (t.name, sCause))

        lOutput.append('\n%-22s %s' % (INFO, 'DISAMBIGUATED'))
        for t in lQueue:
            if not t.exists:
                continue
            lOutput.append('%-36s %-40s %s' % (t.name, t.exists, t.GetLayers()))
        return False, lOutput

    lOutput.append('%-80.80s' % HASHDIVIDER)
    lOutput.append("%-22s %-22s %-28s %s" % (SUCCESS, "Build on %s" % builder.lEssentials, "FILE/DIR", "LAYERS TO WRITE"))
    for t in lQueue:
        lOutput.append('%-34s %-28s %s' % (t.name, t.exists, t.GetLayers()))

    return True, lOutput


def BuildGUI(options, args):
    import PySimpleGUIQt as sg
    
    # sg.Window(title="Hello World", layout=[[]], margins=(100, 50)).read()
    # sg.Window(title="Hello World", layout=[[]]).read()
    
    layout = [[sg.Text("Hello from PySimpleGUI")], [sg.Button("OK")]]
    
    # Create the window
    window = sg.Window("Demo", layout)
    
    # Create an event loop
    while True:
        event, values = window.read()
        # End program if user closes window or
        # presses the OK button
        if event == "OK" or event == sg.WIN_CLOSED:
            break
    
    window.close()


if __name__ == '__main__':
    import sys
    from optparse import OptionParser

    usage = 'usage: %prog [options] target layer1 layer2 layer3 ...'
    args_parser = OptionParser(usage)

    args_parser.add_option("-c", "--config", action="store", dest="config", type="string",
        help="Specify JSON containing configuration details", default="yamake-config.yaml")

    args_parser.add_option("-b", "--build", action="store", dest="build", type="string",
        help="Specify JSON containing a list of layers and build instructions", default="yamake.yaml")

    args_parser.add_option("-j", "--json-output", action="store_true", dest="json_output",
        help="Toggle JSON output", default=False)

    args_parser.add_option("-y", "--yaml-output", action="store_true", dest="yaml_output",
        help="Toggle YAML output", default=False)

    args_parser.add_option("-l", "--layers", action="store", dest="layers", type="string",
        help="Specify a layers folder", default=None)

    args_parser.add_option("", "--repo", action="store", dest="layers", type="string",
        help="Specify a layers folder", default=None)

    (options, args) = args_parser.parse_args(sys.argv)

    if not options.build and os.path.exists("yamake.yaml"):
        options.build = "yamake.yaml"

    if options.build and not os.path.exists(options.build):
        print("%s not found." % options.build)
        sys.exit(1)

    _, lOutput = BuildCLI(options, args[1:])
    print('\n'.join(lOutput))
