# Export ship loadout in Coriolis format

from collections import OrderedDict
import json
import os
from os.path import join
import re
import time

from config import config
import outfitting
import companion


# Map draft EDDN outfitting to Coriolis
# https://raw.githubusercontent.com/jamesremuscat/EDDN/master/schemas/outfitting-v1.0-draft.json
# http://cdn.coriolis.io/schemas/ship-loadout/1.json

ship_map = dict(companion.ship_map)
ship_map['Asp'] = 'Asp Explorer'

category_map = {
    'standard'  : 'standard',
    'internal'  : 'internal',
    'hardpoint' : 'hardpoints',
    'utility'   : 'utility',
}

slot_map = {
    'HugeHardpoint'    : 'hardpoints',
    'LargeHardpoint'   : 'hardpoints',
    'MediumHardpoint'  : 'hardpoints',
    'SmallHardpoint'   : 'hardpoints',
    'TinyHardpoint'    : 'utility',
    'Slot'             : 'internal',
}

standard_map = OrderedDict([	# in output order
    ('Armour',            'bulkheads'),
    ('Power Plant',       'powerPlant'),
    ('Thrusters',         'thrusters'),
    ('Frame Shift Drive', 'frameShiftDrive'),
    ('Life Support',      'lifeSupport'),
    ('Power Distributor', 'powerDistributor'),
    ('Sensors',           'sensors'),
    ('Fuel Tank',         'fuelTank'),
])

weaponmount_map = {
    'Fixed'     : 'Fixed',
    'Gimballed' : 'Gimballed',
    'Turreted'  : 'Turret',
}


# Modules that have a name as well as a group
bulkheads       = outfitting.armour_map.values()
scanners        = [x[0] for x in outfitting.stellar_map.values()]
countermeasures = [x[0] for x in outfitting.countermeasure_map.values()]
fixup_map = {
    'Advanced Plasma Accelerator'   : ('Plasma Accelerator', 'Advanced'),
    'Cytoscrambler Burst Laser'     : ('Burst Laser', 'Cytoscrambler'),
    'Enforcer Cannon'               : ('Multi-cannon', 'Enforcer'),
    'Frame Shift Drive Interdictor' : ('FSD Interdictor', None),
    'Imperial Hammer Rail Gun'      : ('Rail Gun', 'Imperial Hammer'),
    'Impulse Mine Launcher'         : ('Mine Launcher', 'Impulse'),
    'Mining Lance Beam Laser'       : ('Mining Laser', 'Mining Lance'),
    'Multi-Cannon'                  : ('Multi-cannon', None),
    'Pacifier Frag-Cannon'          : ('Fragment Cannon', 'Pacifier'),
    'Pack-Hound Missile Rack'       : ('Missile Rack', 'Pack-Hound'),
    'Pulse Disruptor Laser'         : ('Pulse Laser', 'Distruptor'),	# Note sp
    'Standard Docking Computer'     : ('Docking Computer', 'Standard Docking Computer'),
}


def export(data):

    querytime = config.getint('querytime') or int(time.time())

    ship = companion.ship_map.get(data['ship']['name'], data['ship']['name'])

    loadout = OrderedDict([	# Mimic Coriolis export ordering
        ('$schema',    'http://cdn.coriolis.io/schemas/ship-loadout/1.json#'),
        ('name',       ship_map.get(data['ship']['name'], data['ship']['name'])),
        ('ship',       ship_map.get(data['ship']['name'], data['ship']['name'])),
        ('components', OrderedDict([
            ('standard',   OrderedDict([(x,None) for x in standard_map.values()])),
            ('hardpoints', []),
            ('utility',    []),
            ('internal',   []),
        ])),
    ])

    # Correct module ordering relies on the fact that "Slots" in the data  are correctly ordered alphabetically.
    # Correct hardpoint ordering additionally relies on the fact that "Huge" < "Large" < "Medium" < "Small"
    for slot in sorted(data['ship']['modules']):

        v = data['ship']['modules'][slot]
        try:
            if not v:
                # Need to add nulls for empty slots. Assumes that standard slots can't be empty.
                for s in slot_map:
                    if slot.startswith(s):
                        loadout['components'][slot_map[s]].append(None)
                        break
                continue

            module = outfitting.lookup(v['module'])
            if not module: continue

            category = loadout['components'][category_map[module['category']]]
            thing = OrderedDict([
                ('class',  module['class']),
                ('rating', module['rating']),
            ])

            if module['name'] in bulkheads:
                # Bulkheads are just strings
                category['bulkheads'] = module['name']
            elif module['category'] == 'standard':
                # Standard items are indexed by "group" rather than containing a "group" member
                category[standard_map[module['name']]] = thing
            else:
                # All other items have a "group" member, some also have a "name"
                if module['name'] in scanners:
                    thing['group'] = 'Scanner'
                    thing['name'] = module['name']
                elif module['name'] in countermeasures:
                    thing['group'] = 'Countermeasure'
                    thing['name'] = module['name']
                elif module['name'] in fixup_map:
                    thing['group'], name = fixup_map[module['name']]
                    if name: thing['name'] = name
                else:
                    thing['group'] = module['name']

                if 'mount' in module:
                    thing['mount'] = weaponmount_map[module['mount']]
                if 'guidance' in module:
                    thing['missile'] = module['guidance'][0]	# not mentioned in schema

                category.append(thing)

        except AssertionError as e:
            if __debug__: print 'Loadout: %s' % e
            continue	# Silently skip unrecognized modules
        except:
            if __debug__: raise

    # Construct description
    string = json.dumps(loadout, indent=2)

    # Look for last ship of this type
    regexp = re.compile(re.escape(ship) + '\.\d\d\d\d\-\d\d\-\d\dT\d\d\.\d\d\.\d\d\.json')
    oldfiles = sorted([x for x in os.listdir(config.get('outdir')) if regexp.match(x)])
    if oldfiles:
        with open(join(config.get('outdir'), oldfiles[-1]), 'rU') as h:
            if h.read() == string:
                return	# same as last time - don't write

    # Write
    filename = join(config.get('outdir'), '%s.%s.json' % (ship, time.strftime('%Y-%m-%dT%H.%M.%S', time.localtime(querytime))))
    with open(filename, 'wt') as h:
        h.write(string)
