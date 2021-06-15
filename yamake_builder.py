#!/bin/env python3

# Daniel Rollings
# June 3, 2021

"""
A simple make/build system around layer directories and git
"""

import os
import codecs
import yaml
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
        self.plugin = None

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

                if 'handler' in self.config:
                    sPlugin = self.config['handler']

                    # TODO:  platform-independent determination of other paths
                    sys.path.append('.')
                    self.plugin = __import__(sPlugin)
        return self

    def Initialize(self, sBuildFile, sConfigFile=None):
        if sConfigFile:
            self._initConfig(sConfigFile)

        # First we read in the explicit definitions
        with codecs.open(sBuildFile, 'r', 'utf_8') as build_file:
            input_str = ''.join(build_file.readlines())
            dLoad = yaml.safe_load(input_str)

            base = Target('base', self, {})
            stock = Target('stock', self, {})
            all = Target('all', self, {})
            clean_all = Target('clean_all', self, {})

            for key, value in dLoad.items():
                Target(key, self, value)

        if self.plugin:
            self.plugin.pluginInitialize(self, Target)

        [t.finalizeInit(self) for t in self.lTargets]

        if self.plugin and 'pluginFinalize' in self.plugin.__dict__:
            self.plugin.pluginFinalize(Target)

        # base = self.index['base']
        # self.lBases = set([t for t in self.lTargets if t is base or (t.provides and base in t.provides)])
        # stock = self.index['stock']
        # self.lStocks = set([t for t in self.lTargets if t is stock or (t.provides and stock in t.provides)])

        # stock = self.index['stock']
        # self.lStocks = [t for t in self.lTargets if t is stock or stock in t.provides]

        # Create a dictionary mapping bases to baseFamilies
        dEssentialsToFamilies = self.dEssentialsToFamilies
        lEssentials = self.lEssentials
        for b in lEssentials:
            baseFamily = b
            lProvidedEssentials = None
            if b.provides:
                lProvidedEssentials = [t for t in b.provides if t != base and t in lEssentials]
            while lProvidedEssentials:
                baseFamily = lProvidedEssentials[0]
                lProvidedEssentials = [t for t in baseFamily.provides if t != base and t in lEssentials]
            dEssentialsToFamilies[b] = baseFamily

        dProviders = defaultdict(set)

        for t in self.lTargets:
            # Ensure sane assignments of base and baseFamily
            lDepends = []
            if t.depends:
                lDepends = [depend for depend in t.depends if depend in self.lEssentials]
            if len(lDepends) > 1:
                raise SyntaxError("Target %s has multiple bases: %s" % (t.name, t.depends)).with_traceback(sys.exc_info()[2])
            elif len(lDepends) == 1:
                t.base = lDepends[0]
                t.baseFamily = dEssentialsToFamilies[t.base]

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
    def MakeBuildDependencyDepths(self, lTargets, dProviders, dTimeStamps):
        dDependencyMap = defaultdict(int)

        for target in lTargets:
            target.attemptQueue(builder, dProviders, dTimeStamps, dDependencyMap, 0)

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
    def Enqueue(self, lTargets, dProviders):
        dTimeStamps = defaultdict(float)
        [t.CheckTimeStamp(self, dTimeStamps) for t in self.lTargets]
        
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
        
        if 'any' in self.index and self.index['any'].depends:
            lTargetSet |= self.index['any'].depends

        """
        essential = self.index['essential']
        lPossibleEssentials = self.lEssentials
        lEssentials = [t for t in lPossibleEssentials if (t in dTimeStamps or t in lTargets)]
        if len(lEssentials) != 1:
            if len(lEssentials) > 1:
                raise SyntaxError("You can't specify more than one essential! %s" % lEssentials).with_traceback(sys.exc_info()[2])
            elif not lEssentials:
                if len(lPossibleEssentials) != 1:
                    raise SyntaxError("You must specify a essential target: %s" % lPossibleEssentials).with_traceback(sys.exc_info()[2])
                else:
                    essential = list(lPossibleEssentials)[0]
        elif not lPossibleEssentials:
            raise SyntaxError("No target provides 'essential'").with_traceback(sys.exc_info()[2])

        # print('TARGETS:', lTargetSet)
        # print('TIMESTAMPS', dTimeStamps)

        if self.essential is None:
            lEssentials = [t for t in self.lEssentials if t in dTimeStamps or t in lTargetSet]
            if len(lEssentials) > 1:
                print("Error attempting to use multiple essentials: %s." % lEssentials)
                lExistingEssentials = [t for t in self.lEssentials if t in dTimeStamps]
                if not lExistingEssentials:
                    print("No extant essentials out of %s " % lEssentials)
                    return False, None, None
                if len(lExistingEssentials) == 1:
                    print("%s is already installed as a essential." % lExistingEssentials[0].name)
                else:
                    print("Error attempting to use multiple essentials: %s." % lExistingEssentials)
                    return False, None, None
            elif not len(lEssentials):
                if len(self.lEssentials) == 1:
                    self.essential = list(self.lEssentials)[0]
                else:
                    print("No valid essential selected out of", lEssentials, self.lEssentials)
                    return False, None, None
            else:
                self.essential = lEssentials[0]

        if self.essentialFamily is None:
            essential = self.essential
            if essential in self.dEssentialsToFamilies:
                self.essentialFamily = self.dEssentialsToFamilies[essential]
            else:
                self.essentialFamily = essential
            self.essential = essential
        """

        # print('%-15.15s %s' % ('lTargetSet', lTargetSet))

        lQueueSet = lTargetSet
        lProvides = set(list(chain.from_iterable([t.provides for t in lQueueSet if t.provides])))
        lDepends = set(list(chain.from_iterable([t.depends for t in lQueueSet if t.depends])))
        lAbstracts = set([t for t in lQueueSet | lDepends if t.IsAbstract()])
        lDepends |= lAbstracts
        lQueueSet -= lAbstracts
        lFullProvides = lQueueSet | lProvides
        
        lD = set(list(chain.from_iterable([t.depends for t in lDepends if t.depends])))
        lP = set(list(chain.from_iterable([t.provides for t in lProvides if t.provides])))

        # print('%-15.15s %s' % ('lQueueSet', lQueueSet))
        # print('%-15.15s %s' % ('lAbstracts', lAbstracts))
        # print('%-15.15s %s' % ('lDepends', lDepends))
        # print('%-15.15s %s' % ('lProvides', lProvides))
        # print('%-15.15s %s' % ('lD', lD))
        # print('%-15.15s %s' % ('lP', lP))

        counter = 10
        lAddToQueue = set()
        while lDepends or (lP and lP != lProvides) or (lD and lD != lDepends):
            # print('%-80.80s' % ('%-3.3s %s %s' % (HASHDIVIDER, 'dependency resolution', HASHDIVIDER)))
            # print('\tlP', lP)
            while lP and lP != lProvides:
                # print('\tlP loop', lP)
                lProvides |= lP
                lFullProvides = lQueueSet | lProvides
                lP = set(list(chain.from_iterable([t.provides for t in lFullProvides if t.provides and t.Depends() & lFullProvides])))
                lP -= lProvides
            # print('\tlP loop done', lP)
            # print('%-80.80s' % DIVIDER)
            # print('\tlD', lD)
            lDepends -= lFullProvides

            while lD and lD != lDepends:
                # print('\tlD loop', lD)
                lDepends |= lD
                lD = set(list(chain.from_iterable([t.depends for t in lDepends if t.depends is not None or t.Depends() & lFullProvides])))
                lD -= lDepends
            # print('\tlD loop done', lD)
            # print('%-80.80s' % DIVIDER)

            lFullProvides = lQueueSet | lProvides
            # print('%-15.15s %s' % ('lQueueSet', lQueueSet))
            # print('%-15.15s %s' % ('lDepends', lDepends))
            # print('%-15.15s %s' % ('lFullProvides', lFullProvides))

            # print('%-15.15s %s' % ('lDepends - lAbstracts', lDepends - lAbstracts))
            lAbstractDepends = set([t for t in lDepends if t.IsAbstract()])
            lFoundTargets = set()
            if lAbstractDepends:
                # print('--- loop on lAbstractDepends %s' % lAbstractDepends)
                for depend in [d for d in lAbstractDepends if d in dProviders]:
                    target = None
                    lPP = set(dProviders[depend])
                    # print('\tProvider candidates for %s: %s' % (depend.name, lPP))
                    lTestSets = [
                        lPP & lQueueSet,
                        lPP & ((lProvides | lQueueSet) - lAbstracts),
                        lPP,
                        lPP - lFullProvides,
                        lPP - lAbstractDepends,
                        lPP - lAbstracts,
                        lPP - (lAbstracts | lFullProvides) 
                    ]

                    for testSet in lTestSets:
                        # print('\tProvider candidates for %s: %s' % (depend.name, testSet))
                        if len(testSet) == 1:
                            target = list(testSet)[0]
                            break
                        
                    if not target:
                        # Ooof.  We have to try even harder, pick through the non-abstract depends for each candidate.
                        for pp in lPP:
                            ppDepends = pp.Depends()
                            ppNonAbstractDepends = set([t for t in ppDepends if not t.IsAbstract()])
                            # print('\tProvider candidate for %s: %s %s %s' % (depend.name, pp.name, ppDepends, ppNonAbstractDepends))
                            if ppNonAbstractDepends & lQueueSet:
                                target = pp
                                break
                            if ppNonAbstractDepends & lFullProvides:
                                target = pp
                                break
                            if ppDepends & lQueueSet:
                                target = pp
                                break
                            if ppDepends & lFullProvides:
                                target = pp
                                break
                    
                    if target:
                        lFoundTargets.add(target)
                        
                if lFoundTargets:
                    if len(lFoundTargets) == 1:
                        # print('%-7.7s %sFOUND %s to resolve %s%s' % (SPACES, GRN, list(lFoundTargets)[0].name, depend.name, NRM))
                        lAddToQueue |= lFoundTargets
                        lProvides.add(depend)
                        lFullProvides.add(depend)
                        lDepends.remove(depend)


            # print('%-80.80s' % DIVIDER)
            
            lAddToQueue |= set([t for t in lDepends if not t.IsAbstract() and t.Depends() <= lFullProvides])
            
            if lAddToQueue:
                # print('%-15.15s %s' % ('lAddToQueue', lAddToQueue))
                lQueueSet |= lAddToQueue
                # lDepends |= lAbstracts | set(list(chain.from_iterable([t.depends for t in lQueueSet if t.depends])))

                lAbstracts = set([t for t in lQueueSet | lDepends if t.IsAbstract()])
                lDepends |= lAbstracts
                lQueueSet -= lAbstracts
                lFullProvides |= lQueueSet

                lAddToQueue = set()

            lFullProvides |= lQueueSet | lProvides
            lAbstracts = set([t for t in lFullProvides | lDepends if t.IsAbstract()])
            lDepends -= lFullProvides | lQueueSet

            # Make sure lD and lP are only holding things we haven't picked up yet.
            lP |= set(list(chain.from_iterable([t.provides for t in lQueueSet if t.provides])))
            lP -= lFullProvides

            lD |= set(list(chain.from_iterable([t.depends for t in lQueueSet if t.depends])))
            lD -= lDepends
            lD -= lFullProvides

            # print('%-80.80s' % (DIVIDER))
            # print('%-15.15s %s' % ('lQueueSet', lQueueSet))
            # print('%-15.15s %s' % ('lAbstracts', lAbstracts))
            # print('%-15.15s %s' % ('lDepends', lDepends))
            # print('%-15.15s %s' % ('lProvides', lProvides))
            # print('%-15.15s %s' % ('lD', lD))
            # print('%-15.15s %s' % ('lP', lP))
            counter -= 1
            if counter <= 0:
                break
            
        # print('%-80.80s' % (HASHDIVIDER))
        # print('%-15.15s %s' % ('lQueueSet', lQueueSet))
        # print('%-15.15s %s' % ('lDepends', lDepends))
        
        return True, lQueueSet, lDepends


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
        self.essentials = set()
        self.essentialFamily = defaultdict(dict)
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
            
    

