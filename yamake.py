#!/bin/env python3

# Daniel Rollings
# June 3, 2021

"""
A simple make/build system around layer directories and git
"""

import os
import codecs
import yaml
import itertools

from pprint import pformat
from collections import defaultdict

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
BLU = '\033[1;35m'
MAG = '\033[0;35m'
CYN = '\033[0;36m'
NRM = '\033[0m'


############################################################
# The Target class should match the functionality of a Makefile target, with
# the option to subclass for more advanced scenarios.
############################################################

class Builder:
    def __init__(self):
        self.lTargets = []
        self.index = {}
        self.config = {}
        self.base = None
        self.baseFamily = None
        self.stock = None
        self.lBases = []
        self.lStocks = []
        self.dProviders = defaultdict(set)
        self.dBasesToFamilies = {}
        self.plugin = None

    def _initConfig(self, sConfigFile=None):
        for i in (sConfigFile, "yamake_config.yaml",
                  "%s/.config/yamake_config.yaml" % (os.path.expanduser("~"))):
            if i and os.path.exists(i):
                with codecs.open(sConfigFile, 'r', 'utf_8') as config_file:
                    self.config = yaml.safe_load(config_file)

                ############################################################
                # Now this gets interesting!  We're going to let JSON files
                # specify a Python plugin to load with hooks for task-specific
                # logic, if anything beyond the basics is required.
                # This build system just got super-extensible.
                ############################################################

                if 'handler' in self.config:
                    sPlugin = self.config['handler']

                    # TODO:  platform-independent determination of other paths
                    sys.path.append('.')
                    self.plugin = __import__(sPlugin)
        return self

    def initialize(self, sBuildFile, sConfigFile=None):
        self._initConfig(sConfigFile)

        # First we read in the explicit definitions
        with codecs.open(sBuildFile, 'r', 'utf_8') as build_file:
            input_str = ''.join(build_file.readlines())
            dLoad = yaml.safe_load(input_str)

            base = Target('base', self, {})
            stock = Target('stock', self, {'_provides': [base], 'provides': ['base']})

            for key, value in dLoad.items():
                Target(key, self, value)

        if self.plugin:
            self.plugin.pluginInitialize(self, Target)

        [t.finalizeInit(self) for t in self.lTargets]

        if self.plugin and 'pluginFinalize' in self.plugin.__dict__:
            self.plugin.pluginFinalize(Target)

        base = self.index['base']
        self.lBases = [t for t in self.lTargets if base in t._provides]
        for t in self.lBases:
            t.base = t

        stock = self.index['stock']
        self.lStocks = [t for t in self.lTargets if stock in t._provides]

        # Create a dictionary mapping bases to baseFamilies
        dBasesToFamilies = self.dBasesToFamilies
        lBases = self.lBases
        for b in lBases:
            baseFamily = b
            lProvidedBases = [t for t in b._provides if t != base and t in lBases]
            while lProvidedBases:
                baseFamily = lProvidedBases[0]
                lProvidedBases = [t for t in baseFamily._provides if t != base and t in lBases]
            dBasesToFamilies[b] = baseFamily

        for t in self.lTargets:
            # Ensure sane assignments of base and baseFamily
            lDepends = [depend for depend in t._depends if depend in self.lBases]
            if len(lDepends) > 1:
                raise SyntaxError("Target %s has multiple bases: %s" % (t.name, t._depends)).with_traceback(sys.exc_info()[2])
            elif len(lDepends) == 1:
                t.base = lDepends[0]
                t.baseFamily = dBasesToFamilies[t.base]

            # Check for any cyclic dependencies
            lDepends = list(t._depends)
            counter = 1
            while lDepends:
                if t in lDepends:
                    raise SyntaxError("CYCLIC DEPENDENCY %s, %s" % (t, lDepends)).with_traceback(sys.exc_info()[2])
                lastDepends = lDepends
                lDepends = [dep._depends for dep in lDepends if dep._depends]
                lDepends = list(set(list(itertools.chain.from_iterable(lDepends))))
                counter += 1
                if counter >= 10 or lDepends == lastDepends:
                    raise SyntaxError("CYCLIC DEPENDENCY").with_traceback(sys.exc_info()[2])

            # Check for any cyclic provision
            lProvides = list(t._provides)
            counter = 1
            while lProvides:
                if t in lProvides:
                    raise SyntaxError("CYCLIC PROVIDE %s, %s" % (t, lProvides)).with_traceback(sys.exc_info()[2])
                lastProvides = lProvides
                lProvides = [p._provides for p in lProvides if p._provides]
                lProvides = list(set(list(itertools.chain.from_iterable(lProvides))))
                counter += 1
                if counter >= 10 or lProvides == lastProvides:
                    raise SyntaxError("CYCLIC PROVIDE").with_traceback(sys.exc_info()[2])

        return self

    def jsonOutput(self):
        import json

        print("{")
        lOutput = []
        lSaved = ('target', 'layers', 'depends', 'provides', 'clean', 'bootstrap', 'gitbuild', 'merges')

        for target in self.lTargets:
            if target.name in ('base', 'stock'):
                continue
            d = {k: v for (k, v) in target.__dict__.items() if k in lSaved and v}
            lOutput.append('\t"%s": %s' % (target.name, json.dumps(d)))

        print(',\n'.join(lOutput))

        print("}")

    ######################################################################
    # For our purposes, we need only get the dependency depth, and build each
    # level of depth sequentially, though we could build its members
    # concurrently.
    # Returns:  a list of sets, each least index containing the targets that
    # had its offset in their dependency depth.
    def buildDependencyDepths(self, lTargets, dTimestamps):
        dDependencyMap = defaultdict(int)

        for target in lTargets:
            target.attemptQueue(builder, dTimestamps, dDependencyMap, 0)

        max = [i for i in dDependencyMap.values() if i is not None]
        max.sort()
        try:
            max = max[-1]

        # What, we've got nothing?
        except IndexError:
            return []

        lSets = []
        for i in range(0, max + 1):
            lSets.append([])

        for name, priority in dDependencyMap.items():
            lSets[priority].append(name)

        lSets = [set(i) for i in lSets]
        lSets.reverse()

        return lSets

    ############################################################
    # Check a build dependency
    # Returns: True/False success code, a list of targets in build order,
    # a list of ambiguous targets if any
    def enqueue(self, lTargets):
        dTimestamps = defaultdict(float)

        stock = self.index['stock']
        lStocks = builder.lStocks
        if len(lStocks) != 1:
            lStocks = [t for t in lStocks if stock in lTargets]
            if len(lStocks) > 1:
                raise SyntaxError("You can't specify more than one stock! %s" % lStocks).with_traceback(sys.exc_info()[2])
            elif not lStocks:
                raise SyntaxError("You must specify a stock target! %s" % lStocks).with_traceback(sys.exc_info()[2])
        elif not lStocks:
            raise SyntaxError("No target provides 'stock'").with_traceback(sys.exc_info()[2])

        [t.check_timestamp(dTimestamps) for t in self.lTargets]
        lTargetSet = set(lTargets)

        # Set off a recursive determination of dependency depth.
        dProviders = defaultdict(set)

        for t in self.lTargets:
            for provided in t._provides:
                dProviders[provided].add(t)
        self.dProviders = dProviders

        if self.plugin and 'PluginChooseBase' in self.plugin.__dict__:
            if not self.plugin.PluginChooseBase(self, lTargets):
                print("No valid base selected.", self.lBases)
                return False, None, None

        if self.base is None:
            lBases = [t for t in self.lBases if t in dTimestamps or t in lTargetSet]
            if len(lBases) > 1:
                print("Error attempting to use multiple bases: %s." % lBases)
                lBases = [t for t in self.lBases if t in dTimestamps]
                print("%s is already installed as a base." % lBases[0].name)
                return False, None, None
            elif not len(lBases):
                print("No valid base selected.")
                return False, None, None
            else:
                self.base = lBases[0]

        if self.baseFamily is None:
            base = self.base
            if base in self.dBasesToFamilies:
                self.baseFamily = self.dBasesToFamilies[base]
            else:
                self.baseFamily = base
            self.base = base

        lQueue = self.buildDependencyDepths(lTargetSet, dTimestamps)
        lQueue = list(itertools.chain.from_iterable(lQueue))

        lAmbiguous = [t for t in lQueue if t.target is None]

        return True, lQueue, lAmbiguous

    ############################################################
    # Check a build dependency
    # Returns: True/False success code, list of string output
    def buildCLI(self, options, args):
        if not len(args):
            return False, ['No targets given.']

        lTargets = [self.index[i] for i in args if i in self.index]
        result, lQueue, lAmbiguous = self.enqueue(lTargets)

        if not result:
            return False, []

        lOutput = []

        if len(lAmbiguous):
            lOutput.append('%-36s %s' % ('AMBIGUOUS for %s' % (self.base.name), 'POTENTIALLY PROVIDED BY'))
            for t in lAmbiguous:
                lProviders = [p.name for p in self.dProviders[t]]
                lProviders.sort()
                lProviders = set(lProviders)
                lOutput.append('%-36s %s' % (t.name, ', '.join(lProviders)))

            return False, lOutput

        lOutput.append("SUCCESS: %-27s %-40s %s" % ("%s as base" % self.base.name, "", "LAYERS TO WRITE"))
        for t in lQueue:
            lOutput.append('%-36s %-40s %s' % (t.name, t.target, t.getLayers()))

        return True, lOutput


# The Target class provides a target build layer or condition.
# It supplies depends and provides, and the sum of the depends
# being met by the available provides in the build recipe flag
# it as a valid build.
class Target:

    plugin = None
    bDebug = False

    ############################################################
    # Instance methods

    def __init__(self, name, builder, params):
        self.name = name
        builder.index[name] = self
        builder.lTargets.append(self)

        # self.timestamp = 0.0
        self.target = None
        self.base = None
        self.baseFamily = None
        self.depends = None
        self.provides = None
        self._depends = None
        self._provides = None
        self.layers = None
        self.bootstrap = None
        self.clean = None
        self.gitbuild = None

        if params and type(params) == dict:
            self.__dict__.update(params)

        # print('%s%-8s%s\t%s' % (YEL, 'INIT', NRM, str(self)))

    # This can only be done when we have the full index of targets.
    def finalizeInit(self, builder):
        if self.depends is None:
            self._depends = []
        else:
            self._depends = [builder.index[i] for i in self.depends]

        if self.provides is None:
            self._provides = []
        else:
            self._provides = [builder.index[i] for i in self.provides]

    def __str__(self):
        d = {k: v for (k, v) in self.__dict__.items() if k != 'name' and v}
        return("%-36s %s" % (self.name, pformat(d, width=140)))

    def __repr__(self):
        return(self.name)

    def getLayers(self):
        if not self.layers:
            return [self.name]
        return self.layers

    def check_timestamp(self, dTimestamps):
        if self.target:
            fileentry = self.target % builder.config
            # print("Checking existence of", fileentry, "for", self.name)
            if os.path.exists(fileentry):
                # print ("%s exists" % (fileentry))
                dTimestamps[self] = os.stat(fileentry).st_mtime

    # TODO - this is the nasty, brute-force version of what has to happen.
    # Clean this up!
    def attemptQueue(self, builder, dTimestamps, dDependencyMap, priority, lStack=None):
        bQueue = True
        base = builder.base
        bp = builder.base._provides
        dProviders = builder.dProviders

        lProviders = [p for p in dProviders[self] if p.base is None or p.base == base or p.base in bp]
        if len(lProviders) >= 1:
            lP = [p for p in lProviders if p.base == base]
            if len(lP) == 1:
                lProviders = lP

        if len(lProviders) >= 1:
            lP = [p for p in lProviders if p.base in bp]
            if len(lP) == 1:
                lProviders = lP

        if lStack is None:
            lStack = [self]
        elif self in lStack:
            # recursive checks of abstract targets should not loop
            return priority
        elif not self.target:
            lStack = lStack + [self]

        if len(lProviders) == 0 and self.target is None and self._depends:
            # Aha, an abstract target with dependencies!  This is our duck-typing use case.
            for dep in self._depends:
                dep.attemptQueue(builder, dTimestamps, dDependencyMap, priority + 1, lStack)
            bQueue = False

        elif len(lProviders) == 1:
            bQueue = False
            p = lProviders[0]
            if p in builder.lStocks:
                builder.stock = p

            if p != self:
                p.attemptQueue(builder, dTimestamps, dDependencyMap, priority + 1, lStack)
            else:
                # This strange case is reached when an ambiguous target
                # provides itself, but this is because they might need to be
                # listed along with other potential providers

                for dep in p._depends:
                    if dep == self:
                        continue
                    dep.attemptQueue(builder, dTimestamps, dDependencyMap, priority + 1, lStack)

        elif self._depends is not None:
            for dep in self._depends:
                if dep == self:
                    raise SyntaxError("%s is its own dependency???" % self.name).with_traceback(sys.exc_info()[2])

                if dTimestamps[dep] >= dTimestamps[self]:
                    dep.attemptQueue(builder, dTimestamps, dDependencyMap, priority + 1, lStack)

                elif not dTimestamps[self]:
                    print("Potential providers of %-30s" % (self.name))
                    for p in lProviders:
                        name = "'None'"
                        if p.base:
                            name = "'%s'" % p.base.name
                        print("\t%-20s base: %s %-20s" % (p.name, type(p.base), name))
                        if p in bp:
                            print("SHOULD WORK")
                        if p.base in bp:
                            print("SHOULD WORK")
                    raise SyntaxError().with_traceback(sys.exc_info()[2])

        if self != base and self in builder.lBases:
            bQueue = False

        if bQueue and (self.base is None or (self.base == base) or self.base in bp) and (not dTimestamps[self]) and dDependencyMap[self] < priority:
            dDependencyMap[self] = priority

        return priority


if __name__ == '__main__':
    import sys
    from optparse import OptionParser

    usage = 'usage: %prog [options] target layer1 layer2 layer3 ...'
    args_parser = OptionParser(usage)

    args_parser.add_option("-c", "--config", action="store", dest="config", type="string",
        help="Specify JSON containing configuration details", default="yamake_config.yaml")

    args_parser.add_option("-b", "--build", action="store", dest="build", type="string",
        help="Specify JSON containing a list of layers and build instructions", default='yamake.yaml')

    args_parser.add_option("-j", "--json-output", action="store_true", dest="json_output",
        help="Toggle JSON output", default=False)

    args_parser.add_option("-y", "--yaml-output", action="store_true", dest="yaml_output",
        help="Toggle YAML output", default=False)

    args_parser.add_option("-l", "--layers", action="store", dest="layers", type="string",
        help="Specify a layers folder", default=None)

    args_parser.add_option("", "--repo", action="store", dest="layers", type="string",
        help="Specify a layers folder", default=None)

    (options, args) = args_parser.parse_args(sys.argv)

    if not os.path.exists(options.build):
        print("%s not found." % options.build)
        sys.exit(1)

    builder = Builder().initialize(options.build, options.config)

    try:
        if options.json_output:
            builder.jsonOutput()
        else:
            _, lOutput = builder.buildCLI(options, args[1:])
            print('\n'.join(lOutput))
    finally:
        sys.exit(1)
