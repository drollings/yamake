#!/bin/env python3

# Daniel Rollings
# June 3, 2021


"""
A simple make/build system around layer directories and git
"""

_extra_doc = """
A simple make/build system around layer directories and git meant to operate
on the following directory structure:

. 
|- game
|- layers
| |- layer 
|   |- ro
|   \- rw
|- repo

Where at the current working directory, we expect a tinymake.json file,
and the shown directory layout where every layer's ro tree contains files to
link, and rw tree contains files to unlink in the destination if already
found, and then copy.

The repo folder should contain a git repository from which layers can be
built when needed.
"""

# TODO:  Either make this wrap the redo framework at https://github.com/apenwarr/redo
# or port it to rust once functional.


YEL='\033[1;33m'
CYN='\033[0;36m'
GRN='\033[1;32m'
RED='\033[1;31m'
NRM='\033[0m'
    
import os, stat, shutil
import time
import string
import codecs
import json

from pprint import pprint, pformat
from pathlib import Path
from collections import defaultdict


############################################################
# The Target class should match the functionality of a Makefile target, with
# the option to subclass for more advanced scenarios.
############################################################

class Target:

    ############################################################    
    ## Static members and methods
    ############################################################    

    lTargets = []
    index = {}
    config = {}
    base = None
    stock = None
    lBases = []
    lStocks = []
    dProviders = defaultdict(set)
    plugin = None
    

    def InitConfig(sConfigFile = None):
        for i in ( sConfigFile, "tinymake_config.json", "%s/.config/tinymake_config.json" % (os.path.expanduser("~")) ):
            if i and os.path.exists(i):
                with codecs.open(sConfigFile, 'r', 'utf_8') as config_file:
                    Target.config = json.load(config_file)

                ############################################################
                # Now this gets interesting!  We're going to let JSON files
                # specify a Python plugin to load with hooks for task-specific
                # logic, if anything beyond the basics is required.
                # This build system just got super-extensible.
                ############################################################
            
                if 'handler' in Target.config:
                    sPlugin = Target.config['handler']

                    ## TODO:  platform-independent determination of path
                    sys.path.append('.')
                    Target.plugin = __import__(sPlugin)


    def Initialize(sBuildFile):
        # First we read in the explicit definitions
        with codecs.open(sBuildFile, 'r', 'utf_8') as build_file:
            input_str = ''.join(build_file.readlines())
            # print('DEFINITIONS:', input_str)

            dLoad = json.loads(input_str)

            base = Target('base', {})
            stock = Target('stock', { '_provides': [ base ], 'provides': [ 'base' ] })

            for key, value in dLoad.items():
                Target(key, value)

            if Target.plugin:
                Target.plugin.PluginInitialize(Target)

            for t in Target.lTargets:
                t.finalizeInit()

            if Target.plugin and 'PluginFinalize' in Target.plugin.__dict__:
                Target.plugin.PluginFinalize(Target, lQueue)
                
            for t in Target.lTargets:
                if base in t._provides:
                    Target.lBases.append(t)
                    t.base = t
                if stock in t._provides:
                    Target.lStocks.append(t)

            lStocks = Target.lStocks
            if len(lStocks) > 1:
                print("More than one stock?", lStocks)
                sys.exit(1)
            elif len(lStocks):
                Target.stock = lStocks[0]
            if 'stock' in Target.index and not Target.stock:
                print("No stock selected.")
                sys.exit(1)

            [ t.check_timestamp() for t in Target.lTargets ]

            for t in Target.lTargets:
                l = [ depend for depend in t._depends if depend in Target.lBases ]
                if len(l) > 1:
                    print("Target %s has multiple bases: %s" % (t.name, t._depends))
                    sys.exit(1)
                elif len(l) == 1:
                    t.base = l[0]


    ######################################################################
    # A general-use dependency map generated from a recursive algorithm that
    # assigns the depth of dependencies, thus assuring a given build order.
    def BuildQueue(lTargets, dPP):
        dDependencyMap = defaultdict(int)

        if Target.plugin and 'PluginChooseBase' in Target.plugin.__dict__:
            if not Target.plugin.PluginChooseBase(Target, lTargets, dPP):
                print("No valid base selected.", Target.lBases)
                sys.exit(1)
        else:
            if Target.base is None:
                Target.base = Target.index['base']

        for target in lTargets:
            target.queue(dDependencyMap, 0, dPP)

        max = [ i for i in dDependencyMap.values() if i is not None ]
        max.sort()
        try:
            max = max[-1]
        except IndexError:	# What, we've got nothing?
            return []

        lSets = []
        for i in range(0, max + 1):
            lSets.append( [] )
        
        for name, priority in dDependencyMap.items():
            lSets[priority].append(name)

        lSets = [ set(i) for i in lSets ]
        lSets.reverse()
        
        lQueue = []
        for l in lSets:
            lQueue += list(l)

        if Target.plugin and 'PluginBuildQueue' in Target.plugin.__dict__:
            _, lQueue = Target.plugin.PluginBuildQueue(Target, lQueue)

        return lQueue


    def Enqueue(lTargets):
        for t in lTargets:
            t.needed = True
        
        # Set off a recursive determination of dependency depth.
        dPP = defaultdict(set)
        for t in Target.lTargets:
            for provided in t._provides:
                dPP[provided].add(t)

        lQueue = Target.BuildQueue(lTargets, dPP)

        if Target.plugin and 'PluginEnqueueTargets' in Target.plugin.__dict__:
            _, lQueue = Target.plugin.PluginEnqueueTargets(Target, lQueue)
        
        lProvided = []
        for t in lQueue:
            if t._provides:
                lProvided += t.provides
        lProvided = list(set(lProvided))
        lProvided.sort()
        
        lAmbiguous = [ t for t in lQueue if t.target is None ]

        return True, lQueue, lAmbiguous, dPP


    ############################################################    
    ## Check a build dependency
    def BuildQueueCLI(options, args):
        if not len(args):
            return False, [ 'No targets given.' ]

        lTargets = [ Target.index[i] for i in args if i in Target.index ]

        result, lQueue, lAmbiguous, dPP = Target.Enqueue(lTargets)

        if not result:
            return False, []

        lOutput = []

        if len(lAmbiguous):        
            lOutput.append('%-36s %s' % ('AMBIGUOUS for %s' % (Target.base.name), 'POTENTIALLY PROVIDED BY'))
            for t in lAmbiguous:
                # lOutput.append('%-36s %-8.8s target: %-45s provides: %-40s depends: %s' % (t.name, str(t.timestamp), t.target, t._provides, t._depends))
                lProviders = [ p.name for p in dPP[t] ]
                lProviders.sort()
                lProviders = set(lProviders)
                lOutput.append('%-36s %s' % (t.name, ', '.join(lProviders)))

            return False, lOutput

        lOutput.append("SUCCESS: %s as base" % (Target.base.name) )
        for t in lQueue:
            # lOutput.append('%-36s %-8.8s target: %-45s provides: %-40s depends: %s' % (t.name, str(t.timestamp), t.target, t._provides, t._depends))
            lOutput.append('%-36s %-40s %s' % (t.name, t.target, t.getLayers()))

        return True, lOutput


    def JSONOutput():    
        print("{")
        lOutput = []
        lSaved = ( 'target', 'layers', 'depends', 'provides', 'clean', 'bootstrap', 'gitbuild', 'merge_branches' )

        for target in Target.lTargets:
            if target.name in ('base', 'stock' ):
                continue
            d = { k:v for (k,v) in target.__dict__.items() if k in lSaved and v }
            # lOutput.append('"%s": %s' % (target.name, json.dumps(d)))
            lOutput.append('\t"%s": %s' % (target.name, json.dumps(d)))

        print(',\n'.join(lOutput))

        print("}")

    ############################################################    
    ## Instance methods

    def __init__(self, name, params):
        self.name = name
        Target.index[name] = self
        Target.lTargets.append(self)
        
        self.timestamp = 0.0
        self.needed = False
        self.target = None
        self.base = None
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
    def finalizeInit(self):
        if self.depends is None:
            self._depends = []
        else:
            self._depends = [ Target.index[i] for i in self.depends ]

        if self.provides is None:
            self._provides = []
        else:
            self._provides = [ Target.index[i] for i in self.provides ]
            
    def __str__(self):
        d = { k:v for (k,v) in self.__dict__.items() if k != 'name' and v }
        return("%-36s %s" % (self.name, pformat(d, width=140)))

    def __repr__(self):
        return(self.name)

    def getLayers(self):
        if not self.layers:
            return [ self.name ]
        return self.layers

    def queue(self, dDependencyMap, priority, dPP):
        bQueue = True
        base = Target.base
        bp = Target.base._provides

        lProviders = [ p for p in dPP[self] if p.base is None or p.base == base or p.base in bp ]
        if len(lProviders) >= 1:
            l = [ p for p in lProviders if p.base == base ]
            if len(l) == 1:
                lProviders = l
        
        if len(lProviders) >= 1:
            l = [ p for p in lProviders if p.base in bp ]
            if len(l) == 1:
                lProviders = l

        if len(lProviders) == 1:
            bQueue = False
            p = lProviders[0]
            if p in Target.lStocks:
                Target.stock = p

            if p != self:
                p.queue(dDependencyMap, priority + 1, dPP)
            else:
                # This strange case is reached when an ambiguous target
                # provides itself, but this is because they might need to be
                # listed along with other potential providers

                for dep in p._depends:
                    if dep == self:
                        continue
                    dep.queue(dDependencyMap, priority + 1, dPP)
        
        if len(lProviders) == 0 and self.target is None and self._depends:
            for dep in self._depends:
                if dep == self:
                    continue
                dep.queue(dDependencyMap, priority + 1, dPP)
            bQueue = False

        if self._depends is not None:
            for dep in self._depends:
                if dep == self:
                    print("%s is its own dependency???" % self.name)
                    sys.exit(1)

                if dep.timestamp >= self.timestamp:
                    dep.queue(dDependencyMap, priority + 1, dPP)

                elif not self.timestamp:
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
                    sys.exit(1)

        if self != base and self in Target.lBases:
            bQueue = False
            
        if bQueue and (self.base is None or (self.base == base) or self.base in bp) and (not self.timestamp) and dDependencyMap[self] < priority:
            dDependencyMap[self] = priority
            
        return priority

    def check_timestamp(self):
        if self.target:
            fileentry = self.target % Target.config
            # print("Checking existence of", fileentry, "for", self.name)
            if os.path.exists(fileentry):
                # print ("%s exists" % (fileentry))
                self.timestamp = os.stat(fileentry).st_mtime
                self.needed = True
                # print("\t%s" % t.timestamp)
            return True

        elif self._depends:
            l = [ i for i in self._depends if i.check_timestamp() ]
            if not len(l):
                return True
        
        return False
            

if __name__ == '__main__':
    import sys
    from optparse import OptionParser

    usage = 'usage: %prog [options] target layer1 layer2 layer3 ...'
    args_parser = OptionParser(usage)

    args_parser.add_option("-c", "--config", action="store", dest="config", type="string",
        help="Specify JSON containing configuration details", default="tinymake_config.json")

    args_parser.add_option("", "--json", action="store", dest="build", type="string",
        help="Specify JSON containing a list of layers and build instructions", default='tinymake.json')

    args_parser.add_option("-j", "--json-output", action="store_true", dest="json_output",
        help="Toggle JSON output", default=False)

    args_parser.add_option("-l", "--layers", action="store", dest="layers", type="string",
        help="Specify a layers folder", default=None)

    args_parser.add_option("", "--repo", action="store", dest="layers", type="string",
        help="Specify a layers folder", default=None)

    (options, args) = args_parser.parse_args(sys.argv)
    
    if not os.path.exists(options.build):
        print("%s not found." % options.build)
        sys.exit(1)

    Target.InitConfig(options.config)
    Target.Initialize(options.build)

    if options.json_output:
        Target.JSONOutput()
        sys.exit(0)

    _, lOutput = Target.BuildQueueCLI(options, args[1:])
    print('\n'.join(lOutput))


