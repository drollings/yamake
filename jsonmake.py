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

Where at the current working directory, we expect a layerbuild.yaml file,
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

lReserved = ( '.git' )

## Utility functions

def is_dir(arg):
    return os.path.exists(arg) and stat.S_ISDIR(os.stat(arg)[stat.ST_MODE])


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

    lFinalizedFields = ('depends', 'provides')

    def Initialize(sBuildFile):
        # First we read in the explicit definitions
        with codecs.open(sBuildFile, 'r', 'utf_8') as build_file:
            input_str = ''.join(build_file.readlines())
            # print('DEFINITIONS:', input_str)

            o = json.loads(input_str)

            for key, value in o.items():
                Target(key, value)

        # Now we read the layers folder for implicitly defined simple mods that we don't need dependency info for.
        # By default, layers with a dlc or mods folder are read as stock, with few depends
        if 'LAYERS' in Target.config and is_dir(Target.config['LAYERS']):
            pathLayersDir = Path(Target.config['LAYERS'])
            
            lLayers = [ f for f in pathLayersDir.iterdir() if f.is_dir() ]
            lLayers.sort()
            
            for layerDir in lLayers:
                name = layerDir.parts[-1]

                if name[0] == '_' or name.find('_utf') >= 0 or name.find('_supplement') >= 0 or name in Target.index.keys():
                    # Skip those with explicit definitions
                    continue

                d = {}

                pathLayer = Path(layerDir)
                
                lTargets = [ f for f in pathLayer.glob('ro/dlc/*') if f.is_dir() ]
                lTargets.sort()
                if len(lTargets):
                    p = lTargets[0].parts
                    d['target'] = r'%(DLC)s/' + p[-1]
                else:
                    lTargets = [ f for f in pathLayer.glob('ro/mods/*') if f.is_dir() ]
                    lTargets.sort()
                    if len(lTargets):
                        p = lTargets[0].parts
                        d['target'] = r'%(MODS)s/' + p[-1]

                if not 'target' in d.keys():
                    continue
                
                Target(name, d)

        # This can only be done when we have the full index.
        for t in Target.lTargets:
            t.finalizeInit()
            
        base = Target.index['base']

        for t in Target.lTargets:
            if base in t._provides:
                Target.lBases.append(t)
                t.base = t
            if 'stock' in Target.index and Target.index['stock'] in t._provides:
                Target.lStocks.append(t)

            t.check_timestamp()
            
        if len(Target.lBases) == 1:
            Target.base = Target.lBases[0]
        if len(Target.lStocks) == 1:
            Target.stock = Target.lStocks[0]

        for t in Target.lTargets:
            l = [ depend for depend in t._depends if depend in Target.lBases ]
            if len(l) > 1:
                print("Target %s has multiple bases: %s" % (t.name, t._depends))
                sys.exit(1)
            elif len(l) == 1:
                t.base = l[0]


    def InitConfig(sConfigFile = None):
        for i in ( sConfigFile, "jsonmake_config.json", "%s/.config/layerbuild_config.json" % (os.path.expanduser("~")) ):
            if i and os.path.exists(i):
                with codecs.open(sConfigFile, 'r', 'utf_8') as config_file:
                    Target.config = json.load(config_file)


    def PropagateTimestampsToAmbiguous(target):
        if not target.timestamp:
            return
            
        for p in target._provides:
            if p.mtime is None and p.timestamp < target.timestamp:
                p.timestamp = target.timestamp
                Target.PropagateTimestampsToAmbiguous(p)

    ######################################################################
    # A general-use dependency map generated from a recursive algorithm that
    # assigns the depth of dependencies, thus assuring a given build order.
    def BuildQueue(lTargets, dPP):
        dDependencyMap = defaultdict(int)

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

        lStock = [ t for t in lQueue if t in Target.lStocks ]
        if len(lStock) > 1:
            print("More than one stock?", lStock)
            sys.exit(1)
        elif len(lStock):
            Target.stock = lStock[0]
        if 'stock' in Target.index and not Target.stock:
            print("No stock selected.")
            sys.exit(1)


        lQueue = [ t for t in lQueue if t != Target.stock ]
        
        if Target.stock and not Target.stock.timestamp:
            lQueue = [ Target.stock ] + lQueue

        return lQueue


    def Enqueue(lTargets):
        for t in lTargets:
            t.needed = True
        
        if not Target.base:
            lBases = [ t for t in Target.lBases if t.timestamp or t.needed]
            if len(lBases) > 1:
                print("Error attempting to use multiple bases: %s." % lBases)
                sys.exit(1)
                
                lBases = [ t for t in Target.lBases if t.timestamp ]
                print("%s is already installed as a base." % lBases[0].name)
                return False, None, None, None
    
            elif not len(lBases):
                print("No valid base selected.", Target.lBases)
                return False, None, None, None
            
            Target.base = lBases[0]

        # Set off a recursive determination of dependency depth.
        dPP = defaultdict(set)
        for t in Target.lTargets:
            for provided in t._provides:
                dPP[provided].add(t)

        lQueue = Target.BuildQueue(lTargets, dPP)
        # pprint(lQueue)

        lProvided = []
        for t in lQueue:
            if t._provides:
                lProvided += t.provides
        lProvided = list(set(lProvided))
        lProvided.sort()
        # print("PROVIDED:")
        # pprint(lProvided)
        
        lAmbiguous = [ t for t in lQueue if t.mtime is None ]

        ## TODO: Disambiguation from specified recipes must go here

        # for t in [ t for t in lQueue if t.mtime is None and t.timestamp is None ]:
        #     if len(t.depends):
        #         lDepends = [ d for d in t.depends if d.mtime is None ]
        #         if len(lDepends):
        #             lAmbiguous.append(t)
        #     else:
        #         lAmbiguous.append(t)

        # lQueue = [ t for t in lQueue if t not in Target.dProviders and t.mtime ]
        # lAmbiguous = [ t for t in lAmbiguous if t not in Target.dProviders ]
        
        return True, lQueue, lAmbiguous, dPP


    ############################################################    
    ## Run a build
    def RunCommand(options, args):
        # print('DEPENDENCIES')
        ## TODO: set timestamps according to whatever the target field identifies as
        ## TODO: iterate through provides and set timestamps

        if not len(args):
            return False, [ 'No targets given.' ]

        lTargets = [ Target.index[i] for i in args if i in Target.index ]

        result, lQueue, lAmbiguous, dPP = Target.Enqueue(lTargets)
        # pprint(lQueue)
        if not result:
            return False, []

        lOutput = []

        if len(lAmbiguous):        
            lOutput.append('%-36s %s' % ('AMBIGUOUS for %s' % (Target.base.name), 'POTENTIALLY PROVIDED BY'))
            for t in lAmbiguous:
                # lOutput.append('%-36s %-8.8s target: %-45s provides: %-40s depends: %s' % (t.name, str(t.timestamp), t.mtime, t._provides, t._depends))
                lProviders = [ p.name for p in dPP[t] ]
                lProviders.sort()
                lProviders = set(lProviders)
                lOutput.append('%-36s %s' % (t.name, ', '.join(lProviders)))

            return False, lOutput

        lOutput.append("SUCCESS: %s as base" % (Target.base.name) )
        for t in lQueue:
            # lOutput.append('%-36s %-8.8s target: %-45s provides: %-40s depends: %s' % (t.name, str(t.timestamp), t.mtime, t._provides, t._depends))
            lOutput.append('%-36s %-40s %s' % (t.name, t.mtime, t.getLayers()))

        return True, lOutput


    def JSONOutput():    
        print("{")
        lOutput = []
        lSaved = ( 'target', 'layers', 'depends', 'provides', 'clean', 'bootstrap', 'gitbuild', 'merge_branches' )

        for target in Target.lTargets:
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
        self.mtime = None
        self.base = None
        self.depends = None
        self.provides = None
        self._depends = None
        self._provides = None
        self.layers = None
        self.bootstrap = None
        self.clean = None
        self.gitbuild = None
        
        if params:
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

        # REMASTERED = Target.index['remastered']
        # if self == REMASTERED:
        # 	import pdb; pdb.set_trace()
        
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
        
        if len(lProviders) == 0 and self.mtime is None and self._depends:
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
        if self.mtime:
            fileentry = self.mtime % Target.config
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
            
    def build(self):
        # print('%s%-8s%s %s' % (CYN, 'BUILD', NRM, self.name))
        self.timestamp = time.time()
        self.needed = True

    def clean(self):
        # print('%s%-8s%s %s' % (YEL, 'CLEAN', NRM, self.name))
        pass




if __name__ == '__main__':
    import sys
    from optparse import OptionParser

    usage = 'usage: %prog [options] target layer1 layer2 layer3 ...'
    args_parser = OptionParser(usage)

    args_parser.add_option("-c", "--config", action="store", dest="config", type="string",
        help="Specify JSON containing configuration details", default="jsonmake_config.json")

    args_parser.add_option("", "--json", action="store", dest="build", type="string",
        help="Specify JSON containing a list of layers and build instructions", default='jsonmake.json')

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

    # if len(args) <= 1:
    #     print(_extra_doc)
    #     sys.exit(1)

    _, lOutput = Target.RunCommand(options, args[1:])
    print('\n'.join(lOutput))


