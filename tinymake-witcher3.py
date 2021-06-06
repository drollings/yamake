import os, stat, shutil
import time
import string
import codecs
import json

from pprint import pprint, pformat
from pathlib import Path
from collections import defaultdict


"""Caedmil, gwynnbleid."""


## Utility functions

def is_dir(arg):
    return os.path.exists(arg) and stat.S_ISDIR(os.stat(arg)[stat.ST_MODE])


def PluginInitialize(Target):
    # print()	# A friendly hello when you want to verify plugin load.

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


def PluginBuildQueue(Target, lQueue):
    # TODO - if we're going to work in more detail with the load order,
    # or try for concurrency, this is the place to fit that logic.  For
    # now, a list seems to work.

    lQueue = [ t for t in lQueue if t != Target.stock ]

    if Target.stock and not Target.stock.timestamp:
        lQueue = [ Target.stock ] + lQueue

    return True, lQueue


def PluginChooseBase(Target, lTargets, dPP):
    if Target.base is None:
        lBases = [ t for t in Target.lBases if t.timestamp or t.needed]
        if len(lBases) > 1:
            print("Error attempting to use multiple bases: %s." % lBases)
            return False
            
            lBases = [ t for t in Target.lBases if t.timestamp ]
            print("%s is already installed as a base." % lBases[0].name)
            return False

        elif not len(lBases):
            return False

        Target.base = lBases[0]
        return True

    return False
    
        
