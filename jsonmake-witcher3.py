import os, stat, shutil
import time
import string
import codecs
import json

from pprint import pprint, pformat
from pathlib import Path
from collections import defaultdict


## Utility functions

def is_dir(arg):
    return os.path.exists(arg) and stat.S_ISDIR(os.stat(arg)[stat.ST_MODE])


def Initialize(Target):
    print("Caedmil, gwynnbleid.")
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



def EnqueueTargets(Target, lTargets):
    if not Target.base:
        lBases = [ t for t in Target.lBases if t.timestamp or t.needed]
        if len(lBases) > 1:
            print("Error attempting to use multiple bases: %s." % lBases)
            return False, None
            
            lBases = [ t for t in Target.lBases if t.timestamp ]
            print("%s is already installed as a base." % lBases[0].name)
            return False, None

        elif not len(lBases):
            print("No valid base selected.", Target.lBases)
            return False, None
        
        Target.base = lBases[0]

    return True, lTargets


def BuildQueue(Target, lQueue):
    lStock = [ t for t in lQueue if t in Target.lStocks ]
    if len(lStock) > 1:
        print("More than one stock?", lStock)
        sys.exit(1)
    elif len(lStock):
        Target.stock = lStock[0]
    if 'stock' in Target.index and not Target.stock:
        print("No stock selected.")
        sys.exit(1)

    if Target.stock and not Target.stock.timestamp:
        lQueue = [ Target.stock ] + lQueue

    return lQueue


