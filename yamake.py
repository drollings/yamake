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
        self.base = None
        self.baseFamily = None
        self.stock = None
        self.lBases = []
        self.lStocks = []
        self.dBasesToFamilies = {}
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

        base = self.index['base']
        self.lBases = set([t for t in self.lTargets if t is base or (t.provides and base in t.provides)])
        stock = self.index['stock']
        self.lStocks = set([t for t in self.lTargets if t is stock or (t.provides and stock in t.provides)])

        # stock = self.index['stock']
        # self.lStocks = [t for t in self.lTargets if t is stock or stock in t.provides]

        # Create a dictionary mapping bases to baseFamilies
        dBasesToFamilies = self.dBasesToFamilies
        lBases = self.lBases
        for b in lBases:
            baseFamily = b
            lProvidedBases = None
            if b.provides:
                lProvidedBases = [t for t in b.provides if t != base and t in lBases]
            while lProvidedBases:
                baseFamily = lProvidedBases[0]
                lProvidedBases = [t for t in baseFamily.provides if t != base and t in lBases]
            dBasesToFamilies[b] = baseFamily

        dProviders = defaultdict(set)

        for t in self.lTargets:
            # Ensure sane assignments of base and baseFamily
            lDepends = []
            if t.depends:
                lDepends = [depend for depend in t.depends if depend in self.lBases]
            if len(lDepends) > 1:
                raise SyntaxError("Target %s has multiple bases: %s" % (t.name, t.depends)).with_traceback(sys.exc_info()[2])
            elif len(lDepends) == 1:
                t.base = lDepends[0]
                t.baseFamily = dBasesToFamilies[t.base]

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

        print("{")
        lOutput = []
        lSaved = ('target', 'layers', 'depends', 'provides', 'clean', 'build')

        for target in self.lTargets:
            # if target.name in ('base', 'stock'):
            #     continue
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
        [t.CheckTimeStamp(dTimeStamps) for t in self.lTargets]
        
        if not lTargets:
            default = None
            if 'default' in self.index:
                default = self.index['default']
                
            if default and default.depends:
                lTargets = default.depends
                # print("%-26.26s Attempting default build: %s" % (START, lTargets))
            else:
                print("No targets specified, no default in build file.")
                return False, lOutput

        lTargetSet = set(lTargets)
        
        if 'any' in self.index and self.index['any'].depends:
            lTargetSet |= self.index['any'].depends

        stock = self.index['stock']
        lPossibleStocks = self.lStocks
        lStocks = [t for t in lPossibleStocks if (t in dTimeStamps or t in lTargets)]
        if len(lStocks) != 1:
            if len(lStocks) > 1:
                raise SyntaxError("You can't specify more than one stock! %s" % lStocks).with_traceback(sys.exc_info()[2])
            elif not lStocks:
                if len(lPossibleStocks) != 1:
                    raise SyntaxError("You must specify a stock target: %s" % lPossibleStocks).with_traceback(sys.exc_info()[2])
                else:
                    stock = list(lPossibleStocks)[0]
        elif not lPossibleStocks:
            raise SyntaxError("No target provides 'stock'").with_traceback(sys.exc_info()[2])

        if self.plugin and 'PluginChooseBase' in self.plugin.__dict__:
            if not self.plugin.PluginChooseBase(self, lTargets):
                print("No valid base selected in plugin.", self.lBases)
                return False, None, None

        if self.plugin and 'PluginChooseStock' in self.plugin.__dict__:
            if not self.plugin.PluginChooseStock(self, lTargets):
                print("No valid stock selected in plugin.", self.lBases)
                return False, None, None

        # print('TARGETS:', lTargetSet)
        # print('TIMESTAMPS', dTimeStamps)

        if self.base is None:
            lBases = [t for t in self.lBases if t in dTimeStamps or t in lTargetSet]
            if len(lBases) > 1:
                print("Error attempting to use multiple bases: %s." % lBases)
                lExistingBases = [t for t in self.lBases if t in dTimeStamps]
                if not lExistingBases:
                    print("No extant bases out of %s " % lBases)
                    return False, None, None
                if len(lExistingBases) == 1:
                    print("%s is already installed as a base." % lExistingBases[0].name)
                else:
                    print("Error attempting to use multiple bases: %s." % lExistingBases)
                    return False, None, None
            elif not len(lBases):
                if len(self.lBases) == 1:
                    self.base = self.lBases[0]
                else:
                    print("No valid base selected out of", lBases, self.lBases)
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
                        print('%-7.7s %sFOUND %s to resolve %s%s' % (SPACES, GRN, target.name, depend.name, NRM))
                        lAddToQueue.add(target)
                        lProvides.add(depend)
                        lFullProvides.add(depend)
                        lDepends.remove(depend)
                        break

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

    ############################################################
    # Check a build dependency
    # Returns: True/False success code, list of string output
    def BuildCLI(self, options, args, dProviders):
        print('%-80.80s' % HASHDIVIDER)
        lTargets = None
        if len(args):
            lTargets = [self.index[i] for i in args if i in self.index]
            print("%-22s Attempting build from %s: %s" % (START, options.build, args))
        
        result, lQueue, lAmbiguous = self.Enqueue(lTargets, dProviders)

        if not result:
            return False, []

        lOutput = []

        if len(lAmbiguous):
            lOutput.append('%-80.80s' % HASHDIVIDER)
            lOutput.append('%-26s Can not resolve for %s based on targets %s\n' % (ERROR, self.base.name, lTargets))
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
        lOutput.append("%-22s %-22s %-28s %s" % (SUCCESS, "Build on %s" % self.base.name, "FILE/DIR", "LAYERS TO WRITE"))
        for t in lQueue:
            lOutput.append('%-34s %-28s %s' % (t.name, t.exists, t.GetLayers()))

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

        self.exists = None
        self.base = None
        self.baseFamily = None
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

    def CheckTimeStamp(self, dTimeStamps):
        if self.exists:
            fileentry = self.exists % builder.config
            # print("Checking existence of", fileentry, "for", self.name)
            if os.path.exists(fileentry):
                # print ("%s exists" % (fileentry))
                if self.check_mtime:
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
            
    

    # TODO - this is the nasty, brute-force version of what has to happen.
    # Clean this up!
    def AttemptQueue(self, builder, dProviders, dTimeStamps, dDependencyMap, priority, lStack=None):
        bQueue = True
        base = builder.base
        bp = builder.base.provides
        stock = builder.stock
 
        lProviders = []
        if self in dProviders:
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
        elif not self.exists:
            lStack = lStack + [self]

        if len(lProviders) == 0 and self.exists is None and self.depends:
            # Aha, an abstract target with dependencies!  This is our duck-typing use case.
            for dep in self.depends:
                dep.attemptQueue(builder, dProviders, dTimeStamps, dDependencyMap, priority + 1, lStack)
            bQueue = False

        elif len(lProviders) == 1:
            bQueue = False
            p = lProviders[0]
            if p in builder.lStocks:
                builder.stock = p

            if p != self:
                p.attemptQueue(builder, dProviders, dTimeStamps, dDependencyMap, priority + 1, lStack)
            else:
                # This strange case is reached when an ambiguous target
                # provides itself, but this is because they might need to be
                # listed along with other potential providers

                for dep in p.depends:
                    if dep == self:
                        continue
                    dep.attemptQueue(builder, dProviders, dTimeStamps, dDependencyMap, priority + 1, lStack)

        elif self.depends is not None:
            for dep in self.depends:
                if dep == self:
                    raise SyntaxError("%s is its own dependency???" % self.name).with_traceback(sys.exc_info()[2])

                if dTimeStamps[dep] >= dTimeStamps[self]:
                    dep.attemptQueue(builder, dProviders, dTimeStamps, dDependencyMap, priority + 1, lStack)

                elif not dTimeStamps[self]:
                    print("Potential providers of %-30s" % (self.name))
                    for p in lProviders:
                        name = "'None'"
                        if p.base:
                            name = "'%s'" % p.base.name
                        print("\t%-22s base: %s %-20s" % (p.name, type(p.base), name))
                        if p in bp:
                            print("SHOULD WORK")
                        if p.base in bp:
                            print("SHOULD WORK")
                    raise SyntaxError().with_traceback(sys.exc_info()[2])

        if self != base and self in builder.lBases:
            bQueue = False

        if bQueue and (self.base is None or (self.base == base) or self.base in bp) and (not dTimeStamps[self]) and dDependencyMap[self] < priority:
            dDependencyMap[self] = priority

        return priority


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

    builder = Builder()
    dProviders = builder.Initialize(options.build, options.config)

    if options.json_output:
        builder.JSONOutput()
    else:
        _, lOutput = builder.BuildCLI(options, args[1:], dProviders)
        print('\n'.join(lOutput))

    if not _:
        sys.exit(1)
