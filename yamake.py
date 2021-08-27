#!/bin/env python3

# Daniel Rollings
# June 3, 2021

"""
A simple make/build system around layer directories and git
"""

import os
import codecs
import yaml
import sys
from itertools import chain

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

def lsset(s):
    l = [ repr(i) for i in s ]
    l.sort()
    return ' '.join(l)
 
############################################################
# The Target class should match the functionality of a Makefile target, with
# the option to subclass for more advanced scenarios.
############################################################

class Builder:
    def __init__(self):
        self.lTargets = []
        self.index = {}
        self.config = {}
        self.baseFamily = None
        self.lEssentials = set()
        self.dEssentialsToFamilies = defaultdict(Target, {})
        self.config = None
        self.plugin = None
        self.debug_output = False

    def _initConfig(self, sConfigFile=None):
        for i in (sConfigFile, "yamake-config.yaml",
                  "%s/.config/yamake-config.yaml" % (os.path.expanduser("~"))):
            if i and os.path.exists(i):
                with codecs.open(sConfigFile, 'r', 'utf_8') as config_file:
                    self.config = yaml.safe_load(config_file)

                ############################################################
                # Now this gets interesting!  We're going to let JSON files
                # specify a Python plugin to load with hooks for task-specific
                # logic, if anything beyond the basics is required.
                # This build system just got super-extensible.
                ############################################################

                if 'PLUGIN' in self.config:
                    sPlugin = self.config['PLUGIN']

                    # TODO:  platform-independent determination of other paths
                    sys.path.append('.')
                    self.plugin = __import__(sPlugin)

        print(pformat(self.config))
        return self

    def Initialize(self, sBuildFile, sConfigFile=None):
        if sConfigFile:
            self._initConfig(sConfigFile)

        # First we read in the explicit definitions
        with codecs.open(sBuildFile, 'r', 'utf_8') as build_file:
            input_str = ''.join(build_file.readlines())
            dLoad = yaml.safe_load(input_str)

            # base = Target('base', self, {})
            # stock = Target('stock', self, {})
            # all = Target('all', self, {})
            # clean_all = Target('clean_all', self, {})

            for key, value in dLoad.items():
                Target(key, self, value)

        if self.plugin and 'pluginInitialize' in self.plugin.__dict__:
            dReturn = self.plugin.pluginInitialize(self)
            for key, value in dReturn.items():
                Target(key, self, value)
            l = self.lTargets
            l.sort()
            
        self.lEssentials = set([t for t in self.lTargets if t.essential])

        [t.finalizeInit(self) for t in self.lTargets]

        if self.plugin and 'pluginTargetFinalize' in self.plugin.__dict__:
            self.plugin.pluginTargetFinalize(Target)

        # base = self.index['base']
        # self.lBases = set([t for t in self.lTargets if t is base or (t.provides and base in t.provides)])
        # stock = self.index['stock']
        # self.lStocks = set([t for t in self.lTargets if t is stock or (t.provides and stock in t.provides)])

        # stock = self.index['stock']
        # self.lStocks = [t for t in self.lTargets if t is stock or stock in t.provides]

        dProviders = defaultdict(set)

        for t in self.lTargets:
            # Ensure sane assignments of base and baseFamily
            # lDepends = []
            # if t.depends:
            #     lDepends = [depend for depend in t.depends if depend in self.lEssentials]
            # if len(lDepends) > 1:
            #     raise SyntaxError("Target %s has multiple essentials: %s" % (t.name, t.depends)).with_traceback(sys.exc_info()[2])
            # elif len(lDepends) == 1:
            #     t.base = lDepends[0]
            #     t.baseFamily = dEssentialsToFamilies[t.base]

            # Check for any cyclic dependencies
            lDepends = t.depends
            counter = 1
            while lDepends:
                if t in lDepends:
                    raise SyntaxError("CYCLIC DEPENDENCY %s, %s" % (t, lDepends)).with_traceback(sys.exc_info()[2])
                lastDepends = lDepends
                lDepends = [dep.depends for dep in lDepends if dep.depends]
                lDepends = list(set(list(chain.from_iterable(lDepends))))
                counter += 1
                if counter >= 10 or lDepends == lastDepends:
                    raise SyntaxError("CYCLIC DEPENDENCY").with_traceback(sys.exc_info()[2])

            # Check for any cyclic provision
            lProvides = t.provides
            if lProvides:
                for provider in lProvides:
                    dProviders[provider].add(t)

            while lProvides:
                if t in lProvides:
                    raise SyntaxError("CYCLIC PROVIDE %s, %s" % (t, lProvides)).with_traceback(sys.exc_info()[2])
                lastProvides = lProvides
                lProvides = [p.provides for p in lProvides if p.provides]
                lProvides = list(set(list(chain.from_iterable(lProvides))))
                if lProvides == lastProvides:
                    raise SyntaxError("CYCLIC PROVIDE").with_traceback(sys.exc_info()[2])

        dFullProviders = {}

        # Now set the full depth of provides
        for target, lProviders in dProviders.items():
            lNewSet = set()
            lNewSet |= lProviders
            lP = set(list(chain.from_iterable([dProviders[p] for p in lNewSet if p in dProviders])))
            lP -= lNewSet
            while lP:
                lNewSet |= lP
                lP = set(list(chain.from_iterable([dProviders[p] for p in lNewSet if p in dProviders])))
                lP -= lNewSet
            dFullProviders[target] = lNewSet

        # Create a dictionary mapping essentials to families
        dEssentialsToFamilies = self.dEssentialsToFamilies
        lEssentials = self.lEssentials
        for b in lEssentials:
            baseFamily = b
            lProvidedEssentials = None
            if b.provides:
                lProvidedEssentials = [t for t in b.provides if t in lEssentials]
            while lProvidedEssentials:
                baseFamily = lProvidedEssentials[0]
                lProvidedEssentials = [t for t in baseFamily.Provides() if t in lEssentials]
            dEssentialsToFamilies[b] = baseFamily

        return dFullProviders

    def JSONOutput(self):
        import json

        lOutput = ["{"]
        lSaved = ('target', 'layers', 'depends', 'provides', 'clean', 'actions', 'essential', 'check_mtime')

        for target in self.lTargets:
            # if target.name in ('base', 'stock'):
            #     continue
            d = {k: v for (k, v) in target.__dict__.items() if k in lSaved and v}
            lOutput.append('\t"%s": %s' % (target.name, json.dumps(d)))

        lOutput.append("}")
        return lOutput

    ######################################################################
    # For our purposes, we need only get the dependency depth, and build each
    # level of depth sequentially, though we could build its members
    # concurrently.
    # Returns:  a list of sets, each least index containing the targets that
    # had its offset in their dependency depth.
    def OrderByDepends(self, lTargets, lQueueSet, lEssentials, dProviders, debug_output = False):
        lDepths = [list(set([t for t in lQueueSet & lEssentials if not t.depends]))]
        lDepths.append(list(set([t for t in lQueueSet & lEssentials if t.depends])))
        lProvides = lQueueSet & lEssentials
        lProvides |= set(list(chain.from_iterable([t.provides for t in lProvides if t.provides])))
        lDepends = lQueueSet - lProvides

        if debug_output:
            print('%-78.78s' % ('OrderByDepends %s' % HASHDIVIDER))
            print('\tlDepends', lsset(lDepends))
            print('\tlProvides', lsset(lProvides))

        count = 10
        lP = set()
        lDepends -= lP
        lD = set(list(chain.from_iterable([t.depends for t in lDepends if t.depends is not None])))

        while lDepends or lD or lP:
            if debug_output:
                print('%-78.78s' % ('lDepends loop %s' % DIVIDER))
                print('\tlDepends', lsset(lDepends))
                print('\tlD', lsset(lD))
                print('\tlP', lsset(lP))

            while lP and lP != lProvides:
                if debug_output:
                    print('\t--- lP', (lP), '\tlProvides', lProvides)
                lProvides |= lP
                lP = set(list(chain.from_iterable([t.provides for t in lProvides if t.provides])))
                lP -= lProvides
                lDepends -= lProvides
                lD -= lProvides

            l = set([t for t in lDepends if not t.depends or t.Depends() <= lProvides]) 
            l &= lQueueSet
            if l:
                lAdd = list(l)
                lAdd.sort()
                lDepths.append(lAdd)
                lDepends -= l
                lProvides |= l
            
            if debug_output:
                print('\t--- lDepends', lDepends)
            while lD and lD != lDepends:
                if debug_output:
                    print('\t--- lD', (lD))
                lDepends |= lD
                lD = set(list(chain.from_iterable([t.depends for t in lDepends if t.depends is not None])))
                lD -= lDepends
                lD -= lProvides

            lP |= set(list(chain.from_iterable([t.provides for t in lProvides if t.provides])))
            lP -= lProvides 

            count -= 1            
            if not count:
                break

        if debug_output:
            print('\tlD', lsset(lD))
            print('\tlProvides', lsset(lProvides))
            print('%-78.78s' % ('lDepths %s' % DIVIDER))
            for i in lDepths:
                print('\t%s' % i)

        lReturn = [t for t in chain.from_iterable([t for t in lDepths]) if not t.IsAbstract()]
        return lReturn

    ############################################################
    # Check a build dependency
    # Returns: True/False success code, a list of targets in build order,
    # a list of ambiguous targets if any
    def Enqueue(self, lTargets, dProviders, debug_output = False):
        if not lTargets:
            default = None
            if 'default' in self.index:
                default = self.index['default']
                
            if default and default.depends:
                lTargets = default.depends
                # print("%-26.26s Attempting default build: %s" % (START, lTargets))
            else:
                return False, lOutput

        lTargetSet = set(lTargets)
        
        # Get "any" and "essential" targets accounted for
        if 'any' in self.index and self.index['any'].depends:
            lTargetSet |= self.index['any'].depends

        lEssentials = set()
        for essential in self.lEssentials:
            lEssentials |= dProviders[essential]

        if debug_output:
            print('%-15.15s %s' % ('lTargetSet', lTargetSet))

        lQueueSet = lTargetSet
        lProvides = set(list(chain.from_iterable([t.provides for t in lQueueSet if t.provides])))
        lDepends = set(list(chain.from_iterable([t.depends for t in lQueueSet if t.depends])))
        lAbstracts = set([t for t in lQueueSet | lDepends if t.IsAbstract()])
        lDepends |= lAbstracts
        lQueueSet -= lAbstracts
        lFullProvides = lQueueSet | lProvides

        # lD and lP act as sets of new additions for lDepends and lProvides, respectively.
        # They are looped over until emptied.        
        lD = set(list(chain.from_iterable([t.depends for t in lDepends if t.depends])))
        lP = set(list(chain.from_iterable([t.provides for t in lProvides if t.provides])))

        if debug_output:
            print('%-78.78s' % ('Enqueue %s' % HASHDIVIDER))
            print('%-15.15s %s' % ('lQueueSet', lsset(lQueueSet)))
            print('%-15.15s %s' % ('lAbstracts', lsset(lAbstracts)))
            print('%-15.15s %s' % ('lDepends', lsset(lDepends)))
            print('%-15.15s %s' % ('lProvides', lsset(lProvides)))
            print('%-15.15s %s' % ('lFullProvides', lsset(lFullProvides)))
        
        lChosenEssentials = lFullProvides & lEssentials
        lChosenEssentials |= self.lEssentials & set(list(chain.from_iterable([t.provides for t in lChosenEssentials if t.provides])))
        lExcludedEssentials = lEssentials - lChosenEssentials

        if debug_output:
            print('%s%-15.15s%s %s' % (WHI, 'lChosenEssentials', NRM, lsset(lChosenEssentials)))
            print('%s%-15.15s%s %s' % (WHI, 'lExcludedEssentials', NRM, lsset(lExcludedEssentials)))
        

        # The counter shouldn't be needed, but preventing infinite loops in the case of malformed YAML is nice.
        counter = 5

        lAddToQueue = set()

        if debug_output:
            print('%-78.78s' % ('Enqueue lDepends loop %s' % HASHDIVIDER))

        # We should be able to empty out lDepends, lD, and lP to get to a complete recipe.
        while lDepends or (lP and lP != lProvides) or (lD and lD != lDepends):
            # First, work out all the provides from lP to the  best depth possible.
            if debug_output:
                print('%-78.78s' % ('%-3.3s %s %s' % (DIVIDER, 'dependency resolution', DIVIDER)))
                print('\tlP', lP, 'lProvides', lProvides)

            while lP and lP != lProvides:
                if debug_output:
                    print('\tlP loop', 'lP', lsset(lP), 'lProvides', lsset(lProvides))
                lProvides |= lP
                lFullProvides = lQueueSet | lProvides
                lP = set(list(chain.from_iterable([t.provides for t in lFullProvides if t.provides])))
                lP -= lProvides 

            if debug_output:
                print('\tlP loop done', 'lP', lsset(lP), 'lProvides', lsset(lProvides))
                print('%-80.80s' % DIVIDER)

            lDepends -= lFullProvides

            # Second, get all the new dependencies from lD.
            if debug_output:
                print('\tlD', lD, 'lDepends', lDepends)

            while lD and lD != lDepends:
                if debug_output:
                    print('\tlD loop', 'lD', lsset(lD), 'lDepends', lsset(lDepends))
                lDepends |= lD
                lD = set(list(chain.from_iterable([t.depends for t in lDepends if t.depends is not None or t.Depends() & lFullProvides])))
                lD -= lDepends

            if debug_output:
                print('\tlD loop done', 'lD', lsset(lD), '\n\tlDepends', lsset(lDepends))
                print('%-80.80s' % DIVIDER)

            lFullProvides = lQueueSet | lProvides

            if debug_output:
                print('%-15.15s %s' % ('lQueueSet', lsset(lQueueSet)))
                print('%-15.15s %s' % ('lDepends', lsset(lDepends)))
                print('%-15.15s %s' % ('lProvides', lsset(lProvides)))
                print('%-15.15s %s' % ('lFullProvides', lsset(lFullProvides)))

            # See if we have a single possible choice of providers for any dependencies
            for depend in lDepends:
                lPP = set()

                # If not abstract, or its dependencies satisfied, it can provide itself
                # if not depend.IsAbstract() or depend.depends and depend.Depends() <= lFullProvides:
                if depend.IsAbstract():
                    if depend.depends and depend.Depends() <= lFullProvides:
                        lPP |= set([depend])
                    # print('\t%sSeeking provider for %s:%s %s' % (MAG, repr(depend), NRM, lPP))

                    # Fetch the list of other targets that provide this
                    if depend in dProviders:
                        lPP |= set([t for t in dProviders[depend] if not t.depends or (t.Depends() & lChosenEssentials)])
                        
                    # print('\t%sSeeking provider for %s:%s %s' % (MAG, repr(depend), NRM, lPP))
                    
                    if len(lPP) > 1 and lEssentials & lPP:
                        lPP -= lExcludedEssentials | lAbstracts

                    # print('\t%sSeeking provider for %s:%s %s' % (MAG, repr(depend), NRM, lPP))
                elif depend not in lFullProvides:
                    lPP |= set([depend])
                    
                if not lPP:
                    continue
                    
                if lPP & lProvides and len(lPP & lProvides) == 1:
                    if debug_output:
                        print('\t%sDisambiguated for %s:%s' % (GRN, repr(depend), NRM), lPP & lFullProvides)
                    lAddToQueue |= lPP & lProvides
                    continue

                if len(lPP) != 1:
                    lPP = set([t for t in lPP if t.depends and t.Depends() & lFullProvides])
                    # print('\t%sSeeking provider for %s:%s %s' % (MAG, repr(depend), NRM, lPP))

                if len(lPP) != 1:
                    lPP = set([t for t in lPP if t.depends and t.Depends() & lQueueSet])
                    # print('\t%sSeeking provider for %s:%s %s' % (MAG, repr(depend), NRM, lPP))

                if len(lPP) == 1:
                    if debug_output:
                        print('\t%sDisambiguated for %s:%s' % (GRN, repr(depend), NRM), lPP)
                    lAddToQueue |= lPP
                    continue

                # print('\t%sAMBIGUOUS FOR %s:%s %s' % (YEL, repr(depend), NRM, lPP))

            # print('%-15.15s %s' % ('lDepends - lAbstracts', lDepends - lAbstracts))
            # print('%-80.80s' % DIVIDER)

            if debug_output:
                print('%-78.78s' % ('Enqueue post disambiguation %s' % DIVIDER))
                print('%-15.15s %s' % ('lQueueSet', lsset(lQueueSet)))
                print('%-15.15s %s' % ('lDepends', lsset(lDepends)))
                print('%-15.15s %s' % ('lProvides', lsset(lProvides)))
                print('%-15.15s %s' % ('lFullProvides', lsset(lFullProvides)))

            lAddToQueue |= set([t for t in lDepends if t.IsAbstract() == False and t not in lFullProvides and t.Depends() <= lFullProvides])

            if debug_output:
                print('%-78.78s' % ('Enqueue final lAddToEqueue %s' % DIVIDER))
                print('%-15.15s %s' % ('lQueueSet', lsset(lQueueSet)))
                print('%-15.15s %s' % ('lDepends', lsset(lDepends)))
                print('%-15.15s %s' % ('lProvides', lsset(lProvides)))
                print('%-15.15s %s' % ('lFullProvides', lsset(lFullProvides)))
                print('%-80.80s' % DIVIDER)

            # Set logic to add to the queue and update sets accordingly
            if lAddToQueue:
                # print('%s%-15.15s%s %s' % (CYN, 'lAddToQueue', NRM, lAddToQueue))
                lQueueSet |= lAddToQueue
                lAbstracts = set([t for t in lQueueSet | lDepends if t.IsAbstract()])
                lQueueSet -= lAbstracts
                lFullProvides |= lQueueSet
                lDepends |= lAbstracts - lFullProvides

                if lFullProvides:
                    lDepends -= set([t for t in lDepends if t.IsAbstract() and t.depends and t.Depends() <= lFullProvides])

                lAddToQueue = set()
            else:
                counter = 0

            lFullProvides |= lQueueSet | lProvides
            lAbstracts = set([t for t in lFullProvides | lDepends if t.IsAbstract()])
            lDepends -= lFullProvides | lQueueSet

            # Make sure lD and lP are only holding things we haven't picked up yet.
            lP |= set(list(chain.from_iterable([t.provides for t in lQueueSet if t.provides])))
            lP -= lFullProvides

            lD |= set(list(chain.from_iterable([t.depends for t in lQueueSet if t.depends])))
            lD -= lDepends
            lD -= lFullProvides

            if debug_output:
                print('%-15.15s %s' % ('lQueueSet', lsset(lQueueSet)))
                print('%-15.15s %s' % ('lAbstracts', lsset(lAbstracts)))
                print('%-15.15s %s' % ('lDepends', lsset(lDepends)))
                print('%-15.15s %s' % ('lProvides', lsset(lProvides)))
                print('%-15.15s %s' % ('lFullProvides', lsset(lFullProvides)))
                print('%-15.15s %s' % ('lQ lEssentials', lsset(lQueueSet & lEssentials)))
                print('%-15.15s %s' % ('lD', lD))
                print('%-15.15s %s' % ('lP', lP))

            counter -= 1
            if counter <= 0:
                break

        lDepends -= set([t for t in lDepends if t.IsAbstract() and t.depends and t.Depends() <= lFullProvides])

        if debug_output:
            print('%-80.80s' % (DIVIDER))
            print('%-15.15s %s' % ('lQueueSet', lQueueSet))
            print('%-15.15s %s' % ('lDepends', lDepends))
        return True, lQueueSet, lDepends, lEssentials, lFullProvides


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

        self.exists = None
        self.essential = False
        self.depends = None
        self.provides = None
        self.layers = None
        self.actions = None
        self.clean = None
        self.mtime = None	# If we have some approximation to an mtime, the function name goes here

        if params and type(params) == dict:
            self.__dict__.update(params)

        # print('%s%-8s%s\t%s' % (YEL, 'INIT', NRM, str(self)))

    # This can only be done when we have the full index of targets.
    def finalizeInit(self, builder):
        if self.depends and type(self.depends) != set:
            self.depends = set([builder.index[i] for i in self.depends])

        if self.provides and type(self.provides) != set:
            self.provides = set([builder.index[i] for i in self.provides])

    def __str__(self):
        d = {k: v for (k, v) in self.__dict__.items() if k != 'name' and v}
        return("%-36s %s" % (self.name, pformat(d, width=140)))

    def __repr__(self):
        return(self.name)

    def __lt__(self, other):
        return self.name < other.name

    def GetLayers(self):
        if not self.layers:
            return [self.name]
        return self.layers

    def CheckTimeStamp(self, builder, dTimeStamps):
        if self.exists:
            fileentry = self.exists % builder.config
            # print("Checking existence of", fileentry, "for", self.name)
            if os.path.exists(fileentry):
                # print ("%s exists" % (fileentry))
                if self.mtime:
                    dTimeStamps[self] = os.stat(fileentry).st_mtime
                else:
                    dTimeStamps[self] = 1.0
                
    def Depends(self):
        if not self.depends:
            return set()
        return self.depends
    
    def AbstractDepends(self):
        if not self.depends:
            return set()
        return set([d for d in self.depends if d.IsAbstract()])
    
    def NonAbstractDepends(self):
        if not self.depends:
            return set()
        return set([d for d in self.depends if not d.IsAbstract()])
    
    def Provides(self):
        if not self.provides:
            return set()
        return self.provides
    
    def IsAbstract(self):
        if self.exists or self.actions or self.layers:
            return False
        return True
            
    
############################################################
# Check a build dependency
# Returns: True/False success code, list of string output
def BuildCLI(options, args):
    builder = Builder()

    if options.json_output:
        return True, builder.JSONOutput()

    dProviders = builder.Initialize(options.build, options.config)

    lTargets = None
    if len(args):
        lTargets = [builder.index[i] for i in args if i in builder.index]
        print("%-22s Attempting build from %s: %s" % (START, options.build, args))
    elif 'default' in builder.index and builder.index['default'].depends:
        print('DEFAULT TARGETS:', pformat(builder.index['default'].depends))
        lTargets = builder.index['default'].depends
        print("%-22s Attempting build from %s: default" % (START, options.build))

    if options.debug_output and builder.lEssentials:
        print('ESSENTIALS:')
        for e in builder.lEssentials:
            if e in dProviders:
                print(repr(e), str(dProviders[e]))
            else:
                print(repr(e))
    
    result, lQueueSet, lAmbiguous, lEssentials, lFullProvides = builder.Enqueue(lTargets, dProviders, options.debug_output)

    if not result:
        return False, []

    lOutput = []

    lOutput.append('%-80.80s' % HASHDIVIDER)
    if len(lAmbiguous):
        lOutput.append('%-16s Can not resolve for %s based on targets %s' % (ERROR, builder.lEssentials, lTargets))
        lOutput.append('%-34s %s' % ('AMBIGUOUS', 'POTENTIALLY PROVIDED BY'))
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
            lOutput.append('%-34s %s' % (t.name, sCause))

        return False, lOutput

    lOutput.append("%-22s %-22s %-28s %s" % (SUCCESS, '', "FILE/DIR", "LAYERS TO WRITE"))

    lOrdered = builder.OrderByDepends(lTargets, lQueueSet, lEssentials, dProviders)

    for t in lOrdered:
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

    args_parser.add_option("", "--debug", action="store_true", dest="debug_output",
        help="Toggle debugging output", default=False)

    args_parser.add_option("-l", "--layers", action="store", dest="layers", type="string",
        help="Specify a layers directory", default=None)

    args_parser.add_option("", "--repo", action="store", dest="layers", type="string",
        help="Specify a git repo directory", default=None)

    (options, args) = args_parser.parse_args(sys.argv)

    if not options.build and os.path.exists("yamake.yaml"):
        options.build = "yamake.yaml"

    if options.build and not os.path.exists(options.build):
        print("%s not found." % options.build)
        sys.exit(1)

    result, lOutput = BuildCLI(options, args[1:])
    print('\n'.join(lOutput))
    if not result:
        sys.exit(1)
