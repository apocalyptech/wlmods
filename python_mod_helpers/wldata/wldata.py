#!/usr/bin/env python
# vim: set expandtab tabstop=4 shiftwidth=4:

# Copyright 2019-2022 Christopher J. Kucera
# <cj@apocalyptech.com>
# <http://apocalyptech.com/contact.php>
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of the development team nor the
#       names of its contributors may be used to endorse or promote products
#       derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL CJ KUCERA BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import os
import re
import sys
import json
import glob
import appdirs
import sqlite3
import subprocess
import configparser

from wlhotfixmod.wlhotfixmod import BVC, DependencyExpansion, PartSetExpansion

class WLData(object):
    """
    Class to assist in programmatically inspecting Wonderlands data as much as
    possible.  The first time this class is instantiated, it'll create a config
    file and then error out.  To use the class, populate at least the "filesystem"
    section of the config file (the path will be provided on the console).

    The "filesystem" section contains two config values:

        1) data_dir - This is a directory containing data extracted from the WL
           .pak files using UnrealPak.  It should also be processed so that the
           pathnames on the filesystem match the object names exactly.

        2) ueserialize_path - This is the path to a 'ueserialize' binary from the
           JohnWickParse project, used to serialize wonderlands .uasset/.umap files
           to a JSON object.  This is what's used to process the extracted data into
           a format we can work with, on an on-demand basis.

           I highly recommend you use my own JWP fork, available here:
           https://github.com/apocalyptech/JohnWickParse/releases

    The "database" section contains the single parameter "dbfile", which should be
    the path to the SQLite WL reference data, available at:

        http://apocalyptech.com/games/wl-refs/

    This is only required if you want to use the `get_refs_to()` or `get_refs_from()`
    methods of this class.
    """

    # Data serialization version requirements
    data_version = 27

    # Hardcoded BVA values
    bva_values = {
            # Character-specific weighting; varies with the count of players in the game.
            # The values here are the base weights for if nobody is currently using that
            # class.  We didn't have to do this for BL3 because that weighting happens
            # in the loot pools rather than inside the balances.
            '/Game/GameData/Loot/CharacterWeighting/Att_CharacterWeight_ArmorUsers_Barb': 0.25,
            '/Game/GameData/Loot/CharacterWeighting/Att_CharacterWeight_ArmorUsers_GunMage': 0.25,
            '/Game/GameData/Loot/CharacterWeighting/Att_CharacterWeight_ArmorUsers_Heavy': 0.25,
            '/Game/GameData/Loot/CharacterWeighting/Att_CharacterWeight_ArmorUsers_Knight': 0.25,
            '/Game/GameData/Loot/CharacterWeighting/Att_CharacterWeight_ArmorUsers_Light': 0.25,
            '/Game/GameData/Loot/CharacterWeighting/Att_CharacterWeight_ArmorUsers_Medium': 0.25,
            '/Game/GameData/Loot/CharacterWeighting/Att_CharacterWeight_ArmorUsers_Necro': 0.25,
            '/Game/GameData/Loot/CharacterWeighting/Att_CharacterWeight_ArmorUsers_Ranger': 0.25,
            '/Game/GameData/Loot/CharacterWeighting/Att_CharacterWeight_ArmorUsers_Rogue': 0.25,
            '/Game/PatchDLC/Indigo4/GameData/Loot/CharacterWeighting/Att_CharacterWeight_ArmorUsers_Shaman': 0.25,
            # Assuming we own DLC4 -- 0 otherwise
            '/Game/PatchDLC/Indigo4/GameData/Attributes/PlayerClass/Att_Licensed_Shaman': 1,
            }

    # Hardcoded part-category values
    cats_armor = [
            'WEIGHT',
            'CLASS',
            'SECONDARY BODY',
            'SECONDARY CLASS',
            'CLASS STAT',
            'SECONDARY CLASS STAT',
            'UNIQUE',
            'COMBO TYPE',
            'COMBO SKILL',
            'PLAYER STAT',
            'RARITY',
            ]

    cats_amulets = [
            'UNIQUE',
            'CLASS',
            'ELEMENT',
            'EFFECT',
            'RARITY',
            ]

    cats_rings = [
            'RARITY',
            'MAJOR',
            'MINOR',
            'UNIQUE',
            ]

    cats_wards = [
            'BODY',
            'RARITY',
            'UNIQUE',
            'AUGMENT',
            'ELEMENT',
            'MATERIAL',
            ]

    cats_spells = [
            'CAST TYPE',
            'DELIVERY',
            'MOD',
            'UNIQUE',
            'ENHANCEMENT',
            'ELEMENT',
            'RARITY',
            'MATERIAL',
            ]

    # Expansion Objects
    _expansion_parts = None
    _expansion_dependencies = None

    def __init__(self):
        """
        Initialize a WLData object.  Will create a sample config file if one
        is not already found.  Will require that the "filesystem" section be
        properly filled in, or we'll raise an exception.
        """

        config_dir = appdirs.user_config_dir('wldata')

        # Create the config dir if it doesn't exist
        if not os.path.exists(config_dir):
            os.makedirs(config_dir, exist_ok=True)

        # Create a sample INI file it if doesn't exist
        self.config_file = os.path.join(config_dir, 'wldata.ini')
        if not os.path.exists(self.config_file):
            config = configparser.ConfigParser()
            config['filesystem'] = {
                    'data_dir': 'CHANGEME',
                    'ueserialize_path': 'CHANGEME',
                    }
            config['database'] = {
                    'dbfile': 'CHANGEME',
                    }
            with open(self.config_file, 'w') as odf:
                config.write(odf)
            print('Created sample config file {}'.format(self.config_file))

        # Read in the config file and at least make sure we have filesystem
        # data available
        self.config = configparser.ConfigParser()
        self.config.read(self.config_file)
        self._enforce_config_section('filesystem')

        # Transition: our old 'mysql' category is now 'database', using SQLite
        if 'mysql' in self.config and 'database' not in self.config:
            self.config['database'] = {
                    'dbfile': 'CHANGEME',
                    }
            self.config['mysql']['notice'] = 'This mysql section is no longer used, in favor of the database section'
            with open(self.config_file, 'w') as odf:
                self.config.write(odf)
            print('Updated config file {} with new database section'.format(self.config_file))

        # Convenience var
        self.data_dir = self.config['filesystem']['data_dir']

        # Now the rest of the vars we'll use
        self.cache = {}
        self.balance_to_extra_anoints = None
        self.db = None
        self.curs = None

        # Some internal caches
        self.part_category_name_cache = {}

    def _enforce_config_section(self, section_name):
        """
        Raises an exception if the configuration section `section_name` hasn't
        been changed from its "CHANGEME" defaults.
        """
        if any([v == 'CHANGEME' for v in self.config[section_name].values()]):
            raise Exception('Populate the "{}" section in {} to continue'.format(
                section_name,
                self.config_file,
                ))

    def _connect_db(self):
        """
        Attempts to connect to the refs database, if we haven't already done so.
        This used to connect to a MySQL/MariaDB database but we've since switched
        to using SQLite.
        """
        if self.db is None:
            self._enforce_config_section('database')
            if not os.path.exists(self.config['database']['dbfile']):
                raise RuntimeError('Database file not found: {}'.format(self.config['database']['dbfile']))
            self.db = sqlite3.connect(self.config['database']['dbfile'])
            self.curs = self.db.cursor()

    def _serialize_path(self, base_path):
        """
        Attempts to serialize the given `base_path`.
        """
        try:
            # PyPy3 is still on 3.6, which doesn't have capture_output
            return subprocess.run([self.config['filesystem']['ueserialize_path'], 'serialize', base_path],
                    encoding='utf-8',
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    )
        except FileNotFoundError as e:
            first_label = 'Could not find JohnWickParse executable at: {}'.format(self.config['filesystem']['ueserialize_path'])
            print('')
            print('='*len(first_label))
            print(first_label)
            print('')
            print('Make sure that the path to JWP in the "filesystem" section in')
            print('{} is up to date!'.format(self.config_file))
            print('')
            sys.exit(1)

    def get_raw_file_path(self, path_name):
        """
        Returns the full filename to the specified `path_name`.  This can be used
        to read in data like CSS files and the like which wouldn't make sense to
        process with the rest of the class
        """
        return '{}{}'.format(self.data_dir, path_name)

    def get_data(self, obj_name):
        """
        Returns a JSON-serialized version of the object `obj_name`, if possible.
        May return None, either due to the object not existing, or if JohnWickParse
        can't actually produce a serialization for the object.  Results will be
        cached, so requesting the same object more than once will not result in
        re-parsing JSON content.
        """
        if obj_name not in self.cache:

            base_path = '{}{}'.format(self.data_dir, obj_name)
            json_file = '{}.json'.format(base_path)
            uasset_file = '{}.uasset'.format(base_path)
            umap_file = '{}.umap'.format(base_path)
            if not os.path.exists(json_file):
                self._serialize_path(base_path)
            if os.path.exists(json_file):
                with open(json_file) as df:
                    self.cache[obj_name] = json.load(df)
                if len(self.cache[obj_name]) > 0:
                    # Don't bother checking data version if we don't have actual datafiles
                    # to try and re-serialize.  Folks might be using a pre-serialized archive
                    # which only contains `.json`.
                    if os.path.exists(uasset_file) or os.path.exists(umap_file):
                        if '_apoc_data_ver' not in self.cache[obj_name][0] or self.cache[obj_name][0]['_apoc_data_ver'] < WLData.data_version:
                            # Regenerate if we have an old serialization
                            self._serialize_path(base_path)
                            with open(json_file) as df:
                                self.cache[obj_name] = json.load(df)
            else:
                self.cache[obj_name] = None

        return self.cache[obj_name]

    def find(self, base, prefix, exact=False):
        """
        Given a base object path `base`, recursively search through to find any
        objects with the prefix `prefix`.  Will match case-insensitively.  Will
        yield the object names as they're found.  If `exact` is `True`, this will
        only match on exact object names, rather than a prefix.
        """
        prefix_lower = prefix.lower()
        base_dir = '{}{}'.format(self.data_dir, base)
        results = []
        for (dirpath, dirnames, filenames) in os.walk(base_dir):
            obj_base = dirpath[len(self.data_dir):]
            for filename in filenames:
                if '.' in filename:
                    filename, ext = filename.rsplit('.', 1)
                else:
                    ext = None
                if ext != 'uasset' and ext != 'umap':
                    continue
                if exact:
                    if filename.lower() == prefix_lower:
                        yield os.path.join(obj_base, filename)
                else:
                    if filename.lower().startswith(prefix_lower):
                        yield os.path.join(obj_base, filename)

    def find_data(self, base, prefix):
        """
        Given a base object path `base`, recursively search through to find any
        objects with the prefix `prefix`.  Will match case-insensitively.  Will
        yield the JSON-serialized data of the objects (or None, if no serialization
        is possible) as they're found.
        """
        for obj_name in self.find(base, prefix):
            yield (obj_name, self.get_data(obj_name))

    def glob(self, glob_pattern):
        """
        Find classes which match the given `glob_pattern` and yield the
        object names which were found.
        https://en.wikipedia.org/wiki/Glob_(programming)
        """
        for filename in glob.glob('{}{}'.format(self.data_dir, glob_pattern)):
            if filename.endswith('.uasset') or filename.endswith('.umap'):
                yield filename[len(self.data_dir):].rsplit('.', 1)[0]

    def glob_data(self, glob_pattern):
        """
        Find classes which match the given `glob_pattern` and yield the
        serialized object data for each (or None if unavailable).
        https://en.wikipedia.org/wiki/Glob_(programming)
        """
        for obj_name in self.glob(glob_pattern):
            yield (obj_name, self.get_data(obj_name))

    def get_export_idx(self, obj_name, export_idx):
        """
        Given an object `obj_name`, return the specified export at `export_idx`, or
        None.
        """
        if export_idx == 0:
            return None
        data = self.get_data(obj_name)
        if export_idx > len(data):
            return None
        else:
            return data[export_idx-1]

    def get_exports(self, obj_name, export_type):
        """
        Given an object `obj_name`, return a list of serialized exports which match
        the type `export_type`.
        """
        exports = []
        data = self.get_data(obj_name)
        if data:
            for export in data:
                if export['export_type'] == export_type:
                    exports.append(export)
        return exports

    def get_refs_to(self, obj_name):
        """
        Find all object names which reference the given `obj_name`, and return
        a list of those objects.  Requires a database connection to the refs
        database.
        """
        self._connect_db()
        self.curs.execute("""select o2.name
                from ttwlobject o, ttwlrefs r, ttwlobject o2
                where
                    o.name=?
                    and o.id=r.to_obj
                    and o2.id=r.from_obj
                """, (obj_name,))
        return [row[0] for row in self.curs.fetchall()]

    def get_refs_to_data(self, obj_name):
        """
        Find all object names which reference the given `obj_name`, and yield
        tuples consisting of the object name and the serialized object data.
        Requires a database connection to the refs database.
        """
        for ref in self.get_refs_to(obj_name):
            yield (ref, self.get_data(ref))

    def get_refs_from(self, obj_name):
        """
        Find all object names which `obj_name` references, and return
        a list of those objects.  Requires a database connection to the refs
        database.
        """
        self._connect_db()
        self.curs.execute("""select o2.name
                from ttwlobject o, ttwlrefs r, ttwlobject o2
                where
                    o.name=?
                    and o.id=r.from_obj
                    and o2.id=r.to_obj
                """, (obj_name,))
        return [row[0] for row in self.curs.fetchall()]

    def get_refs_from_data(self, obj_name):
        """
        Find all object names which `obj_name` references, and yield tuples
        consisting of the object name and the serialized object data.  Requires
        a database connection to the refs database.
        """
        for ref in self.get_refs_from(obj_name):
            yield (ref, self.get_data(ref))

    def get_refs_objects_by_short_name(self, short_name):
        """
        Find all objects in our references database whose "short" object
        name (ie: the last path component) is `short_name`.  Requires a
        database connection to the refs database.
        """
        self._connect_db()
        self.curs.execute('select name from ttwlobject where name like ?',
                (f'%/{short_name}',))
        return [row[0] for row in self.curs.fetchall()]

    def datatable_lookup(self, table_name, row_name, col_name):
        """
        Given a `table_name`, `row_name`, and `col_name`, return the specified cell.
        """
        data = self.get_exports(table_name, 'DataTable')[0]
        if row_name in data and col_name in data[row_name]:
            return data[row_name][col_name]
        elif row_name in data and col_name == 'None' and 'Value' in data[row_name]:
            # This happens in Amulet part weights, if nowhere else.  Note the
            # nested BVC processing here.  Note too that this is almost certainly
            # a BVC struct, though we're not making assumptions here.
            return data[row_name]['Value']
        else:
            return None

    def process_bvc(self, bvc_obj, cur_dt=None):
        """
        Given a wlhotfixmod BVC object, return a value.  Optionally pass in `cur_dt`
        as the objet path to the currently-being-processed DataTable, in case a
        nested BVC ends up referring back to the DataTable with subobject-following
        syntax.
        """

        # BVC
        bvc = bvc_obj.bvc

        # DT
        if bvc_obj.dtv and bvc_obj.dtv.table != 'None':
            new_bvc = self.datatable_lookup(bvc_obj.dtv.table, bvc_obj.dtv.row, bvc_obj.dtv.value)
            if new_bvc is not None:
                if type(new_bvc) == dict:
                    bvc = round(self.process_bvc_struct(new_bvc, cur_dt=bvc_obj.dtv.table), 6)
                else:
                    bvc = new_bvc

        # BVA
        if bvc_obj.bva and bvc_obj.bva != 'None':
            attr_name = bvc_obj.bva
            if attr_name in self.bva_values:
                bvc = self.bva_values[attr_name]
            else:
                # Try to read the attr
                base = self.get_exports(attr_name, 'GbxAttributeData')
                if len(base) != 1:
                    raise Exception('bva: {}'.format(attr_name))
                if 'ValueResolver' not in base[0]:
                    raise Exception('bva: {}'.format(attr_name))
                lookup_export = base[0]['ValueResolver']['export']
                lookup = self.get_export_idx(attr_name, lookup_export)
                lookup_type = lookup['export_type']
                if lookup_type == 'ConstantAttributeValueResolver':
                    bvc = lookup['Value']['BaseValueConstant']
                    #print('{} -> {}'.format(attr_name, bvc))
                elif lookup_type == 'DataTableAttributeValueResolver':
                    table_name = lookup['DataTableRow']['DataTable'][1]
                    row = lookup['DataTableRow']['RowName']
                    col = lookup['Property']['ParsedPath']['PropertyName']
                    new_bvc = self.datatable_lookup(table_name, row, col)
                    if new_bvc is not None:
                        bvc = new_bvc
                    #print('{} -> {}'.format(attr_name, bvc))
                else:
                    raise Exception('Unknown bva type {} for {}'.format(lookup_type, attr_name))

        # AI
        if bvc_obj.ai and bvc_obj.ai != 'None':
            # Basically just gonna hardcode these things for now
            if bvc_obj.ai == '/Game/GameData/Balance/WeightingPlayerCount/Enemy_MajorUpgrade_PerPlayer':
                # This uses EAttributeInitializerUsageMode::Scale, and depends on both
                # player count and game mode (NVHM/TVHM).  This code's going to assume
                # 1-player NVHM, which is 1, so no actual changes.
                print('WARNING: Assuming 1-player NVHM while processing Enemy_MajorUpgrade_PerPlayer')
            elif bvc_obj.ai == '/Game/GameData/Loot/CharacterWeighting/Init_CharacterWeight_Armor_PetClasses_StatWeight':
                # No idea what this should be; I assume it probably resolves to something different depending
                # on if someone's got a companion active or not.  The class itself isn't super helpful to
                # myself, though.  TODO: UAssetGUI might be useful to dig into it a bit further...

                # ... also, this pops up a BUNCH, not going to report on it.
                #print('WARNING: Making a total guess at Init_CharacterWeight_Armor_PetClasses_StatWeight')
                pass
            else:
                raise Exception('Unknown AI: {}'.format(bvc_obj.ai))

        # BVS
        return bvc * bvc_obj.bvs

    def process_bvc_struct(self, data, cur_dt=None):
        """
        Given a serialized BVC/BVSC/etc structure, return a value.  Optionally
        pass in a `cur_dt` with the current DataTable path, if we're processing
        a BVC struct inside a DataTable.  (Nested BVCs may reference the same
        DataTable it's in using the `export` subobject-following syntax.  See
        /Game/Gear/Amulets/_Shared/_Design/GameplayAttributes/Tables/DataTable_Amulets_BaseValues
        for some examples of this (for instance, `Weight_Low_2X`)
        """

        return self.process_bvc(BVC.from_data_struct(data, cur_dt=cur_dt), cur_dt=cur_dt)

    def _cache_part_category_name(self, part_name, name):
        """
        Caches a part category name (stupid little func for code simplification)
        """
        self.part_category_name_cache[part_name] = name
        return name

    def guess_part_category_name(self, part_name, part_obj=None):
        """
        Given a `part_name`, try and guess what the category name is, for the parts category
        which this part lives in.  This may or may not be accurate depending on context,
        but it'll be the best we can do given the current part.  (Keep in mind that these
        category names are NOT really part of the base game data itself.  I've done a fair
        bit of tweaking so they "make sense," at least to myself.  The labels you see
        in the Item Inspector in-game are often pretty good guidelines but they're not
        always consistent.)  Optionally pass in an already-retrieved `part_obj` data
        structure, if you already have the object in-hand (though we cache those too,
        so it doesn't matter too much if we request it again here).
        """

        if part_name in self.part_category_name_cache:
            return self.part_category_name_cache[part_name]

        if not part_name or part_name == 'None':
            return self._cache_part_category_name(part_name, None)

        part_lower = part_name.lower()

        # First, a hardcode for a part that we currently can't serialize
        #if part_lower == '/game/gear/grenademods/_design/partsets/part_manufacturer/gm_part_manufacturer_06_pangolin':
        #    return self._cache_part_category_name(part_name, 'MANUFACTURER')

        # Hardcodes for some barrel types -- they report as Barrel Mods, but they're
        # actually fully-fledged barrels.  (The Cryo barrel here is actually set
        # properly, but we'll just do 'em all anyway.)
        if part_name.endswith('/Part_SM_TED_Barrel_Magic_Lightning') \
                or part_name.endswith('/Part_SM_TED_Barrel_Magic_Cryo') \
                or part_name.endswith('/Part_SM_TED_Barrel_Magic_Dark') \
                or part_name.endswith('/Part_SM_TED_Barrel_Magic_Fire') \
                or part_name.endswith('/Part_SM_TED_Barrel_Magic_Poison'):
            return self._cache_part_category_name(part_name, 'BARREL')

        # Grab the data itself and see if we can do anything with it.
        if part_obj is None:
            part_obj = self.get_data(part_name)
        for export in part_obj:
            if export['export_type'].startswith('BPInvPart_'):
                if 'PartInspectionTitleOverride' in export:
                    title_name = export['PartInspectionTitleOverride'][0][1]
                    title_obj = self.get_data(title_name)
                    ui_label = re.sub(r'\[/?.*?\]', '', title_obj[0]['Text']['string'])

                    # Some hardcoded overrides here
                    if ui_label.startswith('TRACKING '):
                        return self._cache_part_category_name(part_name, 'TRACKING METHOD')
                    elif ui_label.endswith(' WARD'):
                        return self._cache_part_category_name(part_name, 'WARD TYPE')
                    elif ui_label.endswith(' MODULE'):
                        return self._cache_part_category_name(part_name, 'RELOAD TYPE')
                    elif ui_label.startswith('UNDERBARREL '):
                        return self._cache_part_category_name(part_name, 'UNDERBARREL TYPE')
                    else:
                        return self._cache_part_category_name(part_name, ui_label)

                elif 'material' in part_lower or '_mat_' in part_lower \
                        or part_lower.endswith('_mat'):
                    return self._cache_part_category_name(part_name, 'MATERIAL')

                elif 'slidecap' in part_lower:
                    return self._cache_part_category_name(part_name, 'CAPS')

                elif 'underbarrel' in part_lower:
                    return self._cache_part_category_name(part_name, 'UNDERBARREL TYPE')

                elif 'magazine' in part_lower or '_mag_' in part_lower:
                    return self._cache_part_category_name(part_name, 'MAGAZINE')

                elif '_sight_' in part_lower:
                    return self._cache_part_category_name(part_name, 'SIGHT')

                elif '_trigger_' in part_lower:
                    return self._cache_part_category_name(part_name, 'BODY ACCESSORY')

                elif part_lower.endswith('/part_ar_cov_scopemount'):
                    return self._cache_part_category_name(part_name, 'RAIL')

                elif part_lower.endswith('/part_sg_jak_body') \
                        or part_lower.endswith('/part_ps_mal_body') \
                        or part_lower.endswith('/part_ps_vla_body'):
                    return self._cache_part_category_name(part_name, 'BODY')

                # These have the potential to match on stuff it shouldn't, will have
                # to be careful.  Material parts seem to already show MATERIAL properly,
                # which is good 'cause they'd match these otherwise.
                elif part_lower.endswith('_01_common') \
                        or part_lower.endswith('_02_uncommon') \
                        or part_lower.endswith('_03_rare') \
                        or part_lower.endswith('_04_veryrare') \
                        or part_lower.endswith('_05_legendary'):
                    return self._cache_part_category_name(part_name, 'RARITY')

                elif '_pincushiontype_' in part_lower or '_pincuhiontype_' in part_lower:
                    return self._cache_part_category_name(part_name, 'PINCUSHION')

                elif part_lower.endswith('/part_sr_hyp_tootherator'):
                    return self._cache_part_category_name(part_name, 'TOOTHERATOR')

                # This one's super annoying; looks like they're all visual pieces.
                # Found on Balance_AR_VLA_01_Common and probably other Vladof gear.
                elif part_lower.endswith('_frontsight') \
                        or part_lower.endswith('_frontsight2') \
                        or part_lower.endswith('_fs'):
                    return self._cache_part_category_name(part_name, 'FRONT SIGHT')

                elif part_lower.endswith('_ele_nonelemental') \
                        or part_lower.endswith('_ele_none'):
                    return self._cache_part_category_name(part_name, 'ELEMENTAL')

                elif part_lower.endswith('/part_sm_dal_mode_whiterider'):
                    return self._cache_part_category_name(part_name, 'WHITE RIDER')

                elif part_lower.endswith('/part_m_blunt_shieldbash'):
                    return self._cache_part_category_name(part_name, 'GREED WARDEN')

                elif part_lower.endswith('/part_m_blunt_hammerquake'):
                    return self._cache_part_category_name(part_name, 'PETTY TANTRUM')

                elif part_lower.endswith('/part_axe_blade_ragehandle'):
                    return self._cache_part_category_name(part_name, 'RAGE HANDLE')

                break

        return self._cache_part_category_name(part_name, None)

    def get_parts_category_name(self, part_names, balance_name, cat_idx):
        """
        Given a list of `part_names`, figure out the most reasonable category name to
        use for those parts.  `balance_name` and `cat_idx` are used for some hardcoded
        tiebreakers, when we can't auto-determine it.
        """

        # First up: if we're NOT dealing with a weapon, we're using some hardcoded
        # values, 'cause it's super annoying otherwise
        if '/Shield/' in balance_name or '/Shields/' in balance_name or '/Wards' in balance_name:
            return self.cats_wards[cat_idx]
        elif '/Pauldrons/' in balance_name:
            return self.cats_armor[cat_idx]
        elif '/Rings/' in balance_name:
            return self.cats_rings[cat_idx]
        elif '/Amulets/' in balance_name:
            return self.cats_amulets[cat_idx]
        elif '/SpellMods/' in balance_name:
            return self.cats_spells[cat_idx]

        # Construct a sort of label histogram
        valid_labels = {}
        for part_name in part_names:
            label = self.guess_part_category_name(part_name)
            if label:
                if label in valid_labels:
                    valid_labels[label] += 1
                else:
                    valid_labels[label] = 1

        # Pick the most-used one
        label_text = None
        label_max = -1
        contention = False
        for label, count in valid_labels.items():
            if count > label_max:
                contention = False
                label_max = count
                label_text = label
            elif count == label_max:
                contention = True

        # Resolve some contentions with hard-coded values, if we can
        if contention:
            if balance_name == '/Game/Gear/Weapons/AssaultRifles/Vladof/_Shared/_Design/_Unique/Donkey/Balance/Balance_AR_VLA_Donkey' and cat_idx == 10:
                # RAIL vs. IRON SIGHTS
                contention = False
                label_text = 'RAIL'
            if balance_name == '/Game/Gear/Weapons/SMGs/Tediore/_Shared/_Design/_Unique/FragmentRain/Balance/Balance_SM_TED_05_FragmentRain':
                # HYDRA ARCANISM vs. FERIORE ARCANISM
                contention = False
                label_text = 'ARCANISM'

        #    if balance_name == '/Game/Gear/Weapons/Pistols/Torgue/_Shared/_Design/_Unique/Nurf/Balance/Balance_PS_TOR_Nurf' and cat_idx == 1:
        #        # BODY ACCESSORY vs. BARREL ACCESSORY
        #        contention = False
        #        label_text = 'BODY ACCESSORY'
        #    elif balance_name == '/Game/Gear/Weapons/AssaultRifles/Vladof/_Shared/_Design/_Unique/Ogre/Balance/Balance_AR_VLA_Ogre' and cat_idx == 10:
        #        # IRON SIGHTS vs. RAIL
        #        contention = False
        #        label_text = 'RAIL'

        #print('{}, {}: {} (from {})'.format(balance_name, cat_idx, valid_labels, len(part_names)))

        # Return
        if contention:
            return None
        else:
            return label_text

    def get_extra_anoints(self, balance_name):
        """
        Given a `balance_name`, return a list of tuples, each with two elements:
          1) The GPartExpansion object providing extra anointments (or None)
          2) A list of anointments which that GPartExpansion is adding to the object.
        """

        # First, if we haven't read in the GPartExpansion data and created our lookup
        # object, do that.
        if not self.balance_to_extra_anoints:

            self.balance_to_extra_anoints = {}

            for expansion_name in [
                    # Nothing yet!
                    ]:

                # Construct a list of anointments which this GPartExpansion provides
                extra_anoints = []
                expansion_data = self.get_exports(expansion_name, 'InventoryGenericPartExpansionData')[0]
                for part in expansion_data['GenericParts']['Parts']:
                    extra_anoints.append((part['PartData'][1], BVC.from_data_struct(part['Weight'])))

                # Grab a list of balance collections which define the gear this expansion acts on.
                bal_collections = [expansion_data['InventoryBalanceCollection'][1]]
                for (extra, extra_data) in self.get_refs_to_data(bal_collections[0]):
                    if extra_data \
                            and extra_data[0]['export_type'] == 'InventoryBalanceCollectionData' \
                            and extra_data[0]['ParentCollection'][1] == bal_collections[0]:
                        bal_collections.append(extra)

                # Now loop through all balances and populate our dict
                for bal_collection in bal_collections:
                    collection = self.get_exports(bal_collection, 'InventoryBalanceCollectionData')[0]
                    if 'InventoryBalanceList' in collection:
                        for bal in collection['InventoryBalanceList']:
                            this_balance = bal['asset_path_name'].split('.')[0]
                            if this_balance not in self.balance_to_extra_anoints:
                                self.balance_to_extra_anoints[this_balance] = []
                            self.balance_to_extra_anoints[this_balance].append((expansion_name, extra_anoints))

        # Now, return the appropriate value
        if balance_name in self.balance_to_extra_anoints:
            return self.balance_to_extra_anoints[balance_name]
        else:
            return []

    def _load_expansions(self):
        """
        Loads in the new InventoryPartSetExpansionData/InventoryExcludersExpansionData
        data from the 2022-08-11 Wonderlands patch, needed for our Balance object to
        know about some gear properly.  This will look for objects prefixed with `EXPD_`
        across the whole data tree.  For now it looks like that's both sufficient and
        accurate enough for our needs, though if the data ever changes in the future,
        we may need to be more clever.  Note that there does not appear to be any main
        index of these expansion objects, so the recursive trawl seems necessary.

        This function ignores ItemPoolExpansionData objects entirely, which have been
        used for all Wonderlands DLC to expand ItemPools.
        """

        self._expansion_parts = {}
        self._expansion_dependencies = {}
        for obj_name, obj_data in sorted(self.find_data('/', 'EXPD_')):
            export = obj_data[0]
            # Would like to use match/case here but don't feel like forcing folks
            # to Python 3.10+
            if export['export_type'] == 'InventoryExcludersExpansionData':
                # First up: dependency/excluder expansions
                for target in export['TargetParts']:
                    target_obj = target[1]
                    if target_obj not in self._expansion_dependencies:
                        self._expansion_dependencies[target_obj] = DependencyExpansion(target_obj)
                    self._expansion_dependencies[target_obj].load_from_export(export)

            elif export['export_type'] == 'InventoryPartSetExpansionData':
                # Next: partset expansions
                partset_name = export['InventoryPartSet'][1]
                if partset_name not in self._expansion_parts:
                    self._expansion_parts[partset_name] = PartSetExpansion(partset_name)
                self._expansion_parts[partset_name].load_expansion_from_export(obj_name, export)

            elif export['export_type'] == 'ItemPoolExpansionData':
                # Ignoring these entirely at the moment, since I don't really alter ItemPools
                # based on on-disk data like we do for Balances (where the above two would be
                # useful to have)
                pass

            else:
                # Unknown!
                raise RuntimeError('Unknown expansion type "{}" in {}'.format(
                    export['export_type'],
                    obj_name,
                    ))

    @property
    def expansion_parts(self):
        """
        Retrieve our parsed Expansion PartSet dict.  Keys will be the PartSet being
        expanded, and the values will be wlhotfixmod.PartSetExpansion objects.
        Dynamically loads the data if we haven't already.
        """
        if self._expansion_parts is None:
            self._load_expansions()
        return self._expansion_parts

    @property
    def expansion_dependencies(self):
        """
        Retrieve our parsed Expansion dependency/excluder dict.  Keys will be the
        Parts being expanded, and the values will be wlhotfixmod.DependencyExpansion
        objects.  Dynamically loads the data if we haven't already.
        """
        if self._expansion_dependencies is None:
            self._load_expansions()
        return self._expansion_dependencies

