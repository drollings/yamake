import os
import stat

# from pprint import pprint, pformat
from pathlib import Path

"""Caedmil, gwynnbleid."""

# Utility functions


def is_dir(arg):
    return os.path.exists(arg) and stat.S_ISDIR(os.stat(arg)[stat.ST_MODE])

# The handler which implicitly initializes layers not already covered by the YAML
def pluginInitialize(builder):
    # Now we read the layers folder for implicitly defined simple mods that we don't need dependency info for.
    # By default, layers with a dlc or mods folder are read as stock, with few depends
    if 'LAYERS' in builder.config and is_dir(builder.config['LAYERS']):
        pathLayersDir = Path(builder.config['LAYERS'])

        lLayers = [f for f in pathLayersDir.iterdir() if f.is_dir()]
        lLayers.sort()
        
        dReturn = {}

        for layerDir in lLayers:
            name = layerDir.parts[-1]

            if name[0] == '_' or name.find('_utf') >= 0 or name.find('_supplement') >= 0 or name in builder.index.keys():
                # Skip those with explicit definitions
                continue

            d = {}

            pathLayer = Path(layerDir)

            lTargets = [f for f in pathLayer.glob('ro/dlc/*') if f.is_dir()]
            lTargets.sort()
            if len(lTargets):
                p = lTargets[0].parts
                d['exists'] = r'%(DLC)s/' + p[-1]
            else:
                lTargets = [f for f in pathLayer.glob('ro/mods/*') if f.is_dir()]
                lTargets.sort()
                if len(lTargets):
                    p = lTargets[0].parts
                    d['exists'] = r'%(MODS)s/' + p[-1]

            if 'exists' not in d.keys():
                continue
                
            dReturn[name] = d

        return dReturn
    else:
        return dict()

# TODO:  handlers for Witcher mod unpacking, cooking/uncooking, bundle management.