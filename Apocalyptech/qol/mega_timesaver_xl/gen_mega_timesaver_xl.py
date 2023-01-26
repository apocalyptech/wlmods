#!/usr/bin/env python3
# vim: set expandtab tabstop=4 shiftwidth=4:

# Copyright 2021-2023 Christopher J. Kucera
# <cj@apocalyptech.com>
# <https://apocalyptech.com/contact.php>
#
# This Wonderlands Hotfix Mod is free software: you can redistribute it
# and/or modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation, either version 3 of
# the License, or (at your option) any later version.
#
# This Wonderlands Hotfix Mod is distributed in the hope that it will
# be useful, but WITHOUT ANY WARRANTY; without even the implied
# warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this Wonderlands Hotfix Mod.  If not, see
# <https://www.gnu.org/licenses/>.

import sys
import argparse
sys.path.append('../../../python_mod_helpers')
from wldata.wldata import WLData
from wlhotfixmod.wlhotfixmod import Mod, BVC

parser = argparse.ArgumentParser(
        description='Generates Mega TimeSaver XL',
        )
parser.add_argument('-v', '--verbose',
        action='store_true',
        help='Be verbose about what we\'re processing',
        )
args = parser.parse_args()
verbose = args.verbose

# There's a lot going on in this mod, but in general there's just a few classes
# of tweaks that I'm making.  This should cover like 95% of the mod.  Here's a
# brief summary:
#
#  - ParticleSystems
#    There's a few cases where a ParticleSystem might determine the timing of
#    something, and others where it just ends up looking weird if you don't
#    speed it up.  Digistruct effects tend to use these, and stuff like the
#    steam while Barista Bot pours coffee in Metridian Metroplex, or the liquid
#    pouring in the brewery in Cankerwood.  There's a lot of values which need
#    to be tweaked to speed up a ParticleSystem -- I've got that wrapped up in
#    a `scale_ps()` function.
#
#  - AnimSequences
#    These are little individual bits of animations, and if that's all you've
#    got to work with, they tend to require a number of tweaks inside them to
#    get the timing right.  I'm using an `AS()` class to wrap all that up.  There's
#    some weird interactions between the majority of the attrs and the
#    `SequenceLength` inside the AnimSequence which I've never figured out.  Some
#    AnimSequences end up glitching out if you scale SequenceLength along with
#    everything else, but others require you to scale it if you want the overall
#    timings to update properly.  Go figure.  The vehicle-related animations in
#    particular are very finnicky, and I've had to balance between an animation
#    which seems to freeze up versus having it *look* fine but leave the vehicle
#    uncontrollable for a bit afterwards.  Note that the AS class expects you to
#    fill in `scale` and `seqlen_scale` *after* instantiation, due to how we're
#    processing these.
#
#  - InteractiveObjects
#    Most of the stuff you interact with in the game is an InteractiveObject (IO),
#    sometimes prefixed by "Blueprint" (BPIO).  Speeding these up requires hitting
#    a lot of internal attrs (much like AnimSequences), but at least these don't
#    suffer from the same weird SequenceLength problems that AnimSequences do.  For
#    some objects, in addition to tweaking the "main" IO object itself, the
#    map-specific instances of the IO might also need some tweaking to account for the
#    reduced runtime.  So you'll see a bunch of level-specific object types have an
#    IO tweak and then also some custom map tweaks further down in the file.  Scaling
#    for these objects is helped out a bit by an `IO()` class, though the actual
#    scaling's done outside the class.
#
#  - GbxLevelSequenceActors
#    As a potential alternative to both AnimSequence and InteractiveObject tweaking,
#    the game sometimes uses sequences to kick off one or more of those, and there
#    may be a GbxLevelSequenceActor which kicks that off.  I didn't really discover
#    these until pretty late in the mod development, but when they're available,
#    they seem much more reliable (and simpler!) than editing AnimSequence and
#    InteractiveObject objects directly.  They've got a `SequencePlayer` sub-object
#    attached which has a very convenient `PlayRate` attr, so all I need to do is
#    set that and I'm golden.  I suspect there are quite a few AS/IO tweaks
#    that I'm doing which would be better done via this method.  (I'm pretty sure
#    there are plenty of AS/IO objects which don't live inside a sequence, so we'd
#    have to be doing some direct tweaks anyway, though.)
#
#  - Bytecode Tweaks
#    Finally, the other main class of tweaks in here is altering blueprint bytecode,
#    generally just to shorten `Delay` opcodes.  There's plenty of times where even
#    if you have all the AS/IO/whatever stuff sped up, you'll end up with blueprint-
#    enforced delays.  Tracking these down is a "fun" process sometimes; see my
#    UAssetAPI fork: https://github.com/apocalyptech/UAssetAPI/
#
# Other than all that, there's the usual amount of "custom" tweaking for other
# stuff, which should be pretty straightforward so long as you've got object
# serializations available.  Elevators all share a common set of attrs, as do the
# NPC walk/sprint speed stuff.  I've tried to keep things at least somewhat
# commented, so hopefully the comments here will help out if you're curious about
# something!

mod = Mod('mega_timesaver_xl.wlhotfix',
        'Mega TimeSaver XL',
        'Apocalyptech',
        [
            "Speeds up animations throughout the game.",
            "",
            "THIS IS A WORK IN PROGRESS!  Please report any game-breaking bugs",
            "to me, but some animations are bound to remain at their original",
            "speed.",
        ],
        contact='https://apocalyptech.com/contact.php',
        lic=Mod.CC_BY_SA_40,
        v='0.9.0',
        cats='qol',
        )

###
### Some global scaling params follow.  For the *most* part, you can alter practically
### everything in the mod by altering these few variables, though there's some
### hardcoded stuff occasionally, and note that some timings are more fragile than
### others.  Some "complex" animations and sequences might be somewhat touchy about
### the precise timing, and I've done some manual tweaking to line things up in a few
### cases.  Nudging these global vars up or down could knock some of that out of
### alignment.  Vehicle animations in particular are already a bit weird and don't
### even work perfectly at 2x.  Dialogue skips probably become more likely as the
### scales goes up, too, particularly on the character movement scale.
###

# How much to improve speed
global_scale = 4

# ... but I want to do doors a *bit* more
door_scale = 5

# Character movement speed
global_char_scale = 1.4

# Minimum serialization version to allow.  Stock JWP doesn't serialize CurveFloats
# correctly, so the mod'll be invalid unless using apocalyptech's fork, of at least
# this version.  (Honestly we probably require more than v19 at this point -- I
# think there's some previously-unserializable objects we probably rely on now.
# Still, that should at least fail the generation instead of producing incorrect
# output, so we'll just leave it at v19 for now.)
min_apoc_jwp_version = 19

# Data obj
data = WLData()

def scale_ps(mod, data, hf_type, hf_target, ps_name, scale, notify=False):
    """
    Function to attempt to scale all components of a ParticleSystem object.
    At time of writing, this is hardly being used by anything -- I'd written
    it for Typhon's digistruct animation in Tazendeer Ruins, and it turns
    out that maybe we didn't even have to (the critical timing tweak looks
    like it was probably an ubergraph bytecode change to the call to his
    dialogue line).  Anyway, we've got a few other instances of editing
    ParticleSystems in here, which should maybe get ported over to using
    this, once I've got an opportunity to re-test 'em.

    `mod` and `data` should be the relevant Mod and BL3Data objects.

    `hf_type` and `hf_target` should be the initial hotfix params -- so far,
    we've only needed Mod.LEVEL for `hf_type`.

    `ps_name` is the path to the ParticleSystem object

    `scale` is the scale to use ("scale" is actually kind of a bad name here;
    we're actualy dividing, not multiplying)

    `notify` can be passed in to set the notify flag on the hotfixes, too,
    but so far that's never been necessary
    """
    done_work = False
    ps_obj = data.get_data(ps_name)
    for export in ps_obj:
        if export['export_type'] == 'ParticleSystem':
            for emitter_idx, emitter_obj in enumerate(export['Emitters']):
                emitter = ps_obj[emitter_obj['export']-1]
                for lod_idx, lod_obj in enumerate(emitter['LODLevels']):
                    lod = ps_obj[lod_obj['export']-1]
                    lod_attr = f'Emitters.Emitters[{emitter_idx}].Object..LODLevels.LODLevels[{lod_idx}].Object..'
                    if 'TypeDataModule' in lod:
                        tdm_obj = lod['TypeDataModule']
                        tdm = ps_obj[tdm_obj['export']-1]
                        if 'EmitterInfo' in tdm and 'MaxLifetime' in tdm['EmitterInfo']:
                            done_work = True
                            mod.reg_hotfix(hf_type, hf_target,
                                    ps_name,
                                    f'{lod_attr}TypeDataModule.Object..EmitterInfo.MaxLifetime',
                                    round(tdm['EmitterInfo']['MaxLifetime']/scale, 6),
                                    notify=notify,
                                    )
                    if 'RequiredModule' in lod:
                        reqmod_obj = lod['RequiredModule']
                        reqmod = ps_obj[reqmod_obj['export']-1]
                        reqmod_attr = f'{lod_attr}RequiredModule.Object..'
                        for attr in [
                                'EmitterDuration',
                                'EmitterDelay',
                                ]:
                            if attr in reqmod:
                                done_work = True
                                mod.reg_hotfix(hf_type, hf_target,
                                        ps_name,
                                        f'{reqmod_attr}{attr}',
                                        round(reqmod[attr]/scale, 6),
                                        notify=notify,
                                        )
                    for module_idx, module_obj in enumerate(lod['Modules']):
                        module = ps_obj[module_obj['export']-1]
                        module_attr = f'{lod_attr}Modules.Modules[0].Object..'
                        if 'Lifetime' in module:
                            for attr in ['MinValue', 'MaxValue']:
                                if attr in module['Lifetime']:
                                    done_work = True
                                    mod.reg_hotfix(hf_type, hf_target,
                                            ps_name,
                                            f'{module_attr}Lifetime.{attr}',
                                            round(module['Lifetime'][attr]/scale, 6),
                                            notify=notify,
                                            )
                            if 'Table' in module['Lifetime'] and 'Values' in module['Lifetime']['Table']:
                                for value_idx, value in enumerate(module['Lifetime']['Table']['Values']):
                                    done_work = True
                                    mod.reg_hotfix(hf_type, hf_target,
                                            ps_name,
                                            f'{module_attr}Lifetime.Table.Values.Values[{value_idx}]',
                                            round(value/scale, 6),
                                            notify=notify,
                                            )
                            if 'Distribution' in module['Lifetime']:
                                dist_obj = module['Lifetime']['Distribution']
                                dist = ps_obj[dist_obj['export']-1]
                                if 'Constant' in dist:
                                    done_work = True
                                    mod.reg_hotfix(hf_type, hf_target,
                                            ps_name,
                                            f'{module_attr}Lifetime.Distribution.Object..Constant',
                                            round(dist['Constant']/scale, 6),
                                            notify=notify,
                                            )

            break

    # Report if we didn't actually get any work
    if not done_work:
        print(f'WARNING: ParticleSystem had no edits: {ps_name}')

mod.header('Item Pickups')

# Defaults:
#  /Game/GameData/GameplayGlobals
#  - MassPickupMaxDelay: 0.075
#  - MassPickupMaxPullAmount: 6
#  - MassPickupMaxTotalDelay: 1.5
#  - MassPickupMinDelay: 0.06
#  - MassPickupRadius: 400
#  /Game/Pickups/_Shared/_Design/AutoLootContainerPickupFlyToSettings
#  - MaxLifetime: 2.5
#  - SpinSpeed: (pitch=0, yaw=200, roll=200)
#  - LinearSpeed: 750
#  - LinearAcceleration: 650

mod.comment('Mass Pickup Delay (honestly not sure if these have much, if any, effect)')
for var, value in [
        ('MassPickupMaxDelay', 0.075/3),
        ('MassPickupMaxTotalDelay', 1.5/3),
        ('MassPickupMinDelay', 0.06/3),
        ]:
    mod.reg_hotfix(Mod.PATCH, '',
            '/Game/GameData/GameplayGlobals',
            var,
            round(value, 6))
mod.newline()

mod.comment('Pickup flight speeds (likewise, I suspect many of these don\'t actually do much)')
mod.comment('The `AutoLootContainer` ones definitely do help, at least.')
for obj_name in [
        'AutoLootContainerPickupFlyToSettings',
        'ContainerEchoLogPickupFlyToSettings',
        'ContainerPickupFlyToSettings',
        'DroppedEchoLogPickupFlyToSettings',
        'DroppedPickupFlyToSettings',
        ]:
    full_obj_name = f'/Game/Pickups/_Shared/_Design/{obj_name}'
    obj_data = data.get_exports(full_obj_name, 'PickupFlyToData')[0]
    if 'LinearSpeed' in obj_data:
        speed = obj_data['LinearSpeed']
    else:
        # This seems to be the default
        speed = 1000
    mod.reg_hotfix(Mod.PATCH, '',
            full_obj_name,
            'LinearSpeed',
            speed*2)
    mod.reg_hotfix(Mod.PATCH, '',
            full_obj_name,
            'LinearAcceleration',
            obj_data['LinearAcceleration']*2)
mod.newline()

# TODO: Test/adapt this as needed
if False:
    # Make Fast Travel + Teleport digistruct animations disappear
    # (note that the death respawn is totally separate from this, and handled via
    # some AnimSequence tweaks above)
    mod.header('Fast Travel / Teleport Animation Disable')

    # A bunch of silliness in here, when I was looking at bundling this separately
    # as its own mod and was considering multiple versions.  In the end, this just
    # hardcodes an effective disabling of the whole sequence, and I could omit
    # various bits of math.  But whatever, the work is done -- leaving it as-is.
    default_duration = 6.5
    default_unlock = 5.5
    default_teleport = 1.5
    unlock_scale = default_unlock/default_duration
    teleport_scale = default_teleport/default_duration

    # 0.5 - Effectively disables it
    # 2 - Quite short, but still gets a tiny bit of the tunnel
    new_duration = 0.5

    min_timers = min(default_teleport, new_duration)

    mod.reg_hotfix(Mod.PATCH, '',
            '/Game/PlayerCharacters/_Shared/_Design/Travel/Action_TeleportEffects.Default__Action_TeleportEffects_C',
            'Duration',
            new_duration,
            )

    # Adjust delay on unlocking resources (whatever that means; haven't figured out
    # what's not available when "locked")
    mod.bytecode_hotfix(Mod.PATCH, '',
            '/Game/PlayerCharacters/_Shared/_Design/Travel/Action_TeleportEffects',
            'ExecuteUbergraph_Action_TeleportEffects',
            1119,
            default_unlock,
            max(min_timers, round(new_duration*unlock_scale, 6)),
            )

    # Adjust delay on actually teleporting
    mod.bytecode_hotfix(Mod.PATCH, '',
            '/Game/PlayerCharacters/_Shared/_Design/Travel/Action_TeleportEffects',
            'ExecuteUbergraph_Action_TeleportEffects',
            391,
            default_teleport,
            max(min_timers, round(new_duration*teleport_scale, 6)),
            )

    mod.newline()

# TODO: test/adapt this
if False:
    # Photo Mode activation time
    # I actually *don't* want to alter deactivation time, since Photo Mode can be used
    # to pick up gear or hit buttons that you wouldn't otherwise be able to reach,
    # while the camera's zooming back to your char.  That's even occasionally important
    # with this mod active, such as getting to the Typhon Dead Drop in Meridian
    # Outskirts without having to go all the way around the level.
    mod.header('Photo Mode Activation Time')
    mod.bytecode_hotfix(Mod.PATCH, '',
            '/Game/GameData/BP_PhotoModeController',
            'ExecuteUbergraph_BP_PhotoModeController',
            # 187 is the deactivation index (also default of 1.5)
            122,
            1.5,
            1.5/global_scale,
            )
    mod.newline()

class AS():
    """
    Little wrapper class so that I can more easily loop over a bunch of AnimSequence
    objects which largely use the defaults but occasionally need to tweak some stuff.

    When I was pretty far along in this mod, I discovered that GbxLevelSequenceActor
    objects have a SequencePlayer sub-object with a PlayRate attr which often ends
    up producing better results than tweaking the AnimSequence timings themselves.
    I suspect that a lot of our AnimSequence tweaks that we do via this class would
    probably be better done via that method instead, though I definitely don't feel
    like having to re-test huge chunks of the game.  Also there probably *are*
    various circumstances where we'd need to tweak AnimSequences anyway, so I don't
    think this was wasted work.  Still, I suspect a bunch of bulk could be cut
    back into some simpler PlayRate adjustments if I were ever willing to take the
    time to do it.
    """

    def __init__(self, path, scale=None, seqlen_scale=None, extra_char=None, method=Mod.LEVEL, target=None):
        self.path = path
        self.scale = scale
        self.seqlen_scale = seqlen_scale
        self.extra_char = extra_char
        self.method = method
        self.target = target

    def _do_scale(self, mod, data, hf_trigger, hf_target):
        """
        Method to shorten animation sequences
        """

        # Serialize the data
        as_data = data.get_exports(self.path, 'AnimSequence')[0]

        # First the RateScale; happens regardless of AnimSequence contents
        mod.reg_hotfix(hf_trigger, hf_target,
                self.path,
                'RateScale',
                self.scale)

        # Now Notifies
        if 'Notifies' in as_data:
            for idx, notify in enumerate(as_data['Notifies']):
                # TODO: Should we also do `Duration`?  Few objects have that one...
                for var in ['SegmentBeginTime', 'SegmentLength', 'LinkValue']:
                    if var in notify and notify[var] != 0:
                        mod.reg_hotfix(hf_trigger, hf_target,
                                self.path,
                                'Notifies.Notifies[{}].{}'.format(idx, var),
                                round(notify[var]/self.scale, 6))

                # If we have targets inside EndLink, process that, too.  (So far, it doesn't
                # look like any animations we touch actually have anything here.)
                endlink = notify['EndLink']
                if 'export' not in endlink['LinkedMontage'] \
                        or endlink['LinkedMontage']['export'] != 0 \
                        or 'export' not in endlink['LinkedSequence'] \
                        or endlink['LinkedSequence']['export'] != 0:
                    for var in ['SegmentBeginTime', 'SegmentLength', 'LinkValue']:
                        if var in endlink and endlink[var] != 0:
                            mod.reg_hotfix(hf_trigger, hf_target,
                                    self.path,
                                    'Notifies.Notifies[{}].EndLink.{}'.format(idx, var),
                                    round(endlink[var]/self.scale, 6))

        # Finally: SequenceLength.  This one's a bit weird, which is why we're letting categories
        # decide if they want to use alt scalings.  For player animations for entering/leaving vehicles
        # (or for changing seats), if SequenceLength is scaled at the same scale as the rest of the
        # animations, the animation "freezes" before it's fully complete, and the player just jerks
        # to their final spot once the appropriate time has elapsed.  Contrariwise, if we *don't*
        # scale SequenceLength down, you end up with a period of time where you can't interact with
        # the vehicle at all, like driving, leaving, or changing seats again.  In the end, I settled
        # on just using the global vehicle scale for all categories here, but if I want to tweak
        # something in the future, at least it's easy enough to do so.
        if 'SequenceLength' in as_data:
            mod.reg_hotfix(hf_trigger, hf_target,
                    self.path,
                    'SequenceLength',
                    round(as_data['SequenceLength']/self.seqlen_scale, 6))

    def do_scale(self, mod, data):
        if self.target is None:
            if self.method == Mod.PATCH:
                target = ''
            elif self.method == Mod.LEVEL or self.method == Mod.CHAR:
                target = 'MatchAll'
            else:
                raise RuntimeError(f'Unknown method for AnimSequence patching: {self.method}')
        else:
            target = self.target
        self._do_scale(mod, data, self.method, target)
        if self.extra_char:
            self._do_scale(mod, data, Mod.CHAR, self.extra_char)

# Direct animation speedups
mod.header('Simple Animation Speedups')
for cat_name, cat_scale, cat_seqlen_scale, animseqs in [
        ('Containers', global_scale, 1, [
            # Initial object list generated by:
            #     find $(find . -type d -name Lootables) -name "AS_*.uasset" | sort -i | cut -d. -f2 | grep -vE '(Idle|Flinch|_Closed|_Opened)'
            # ... while at the root of a data unpack
            AS('/Game/InteractiveObjects/Lootables/FishingNet/Animation/AS_Open'),
            AS('/Game/InteractiveObjects/Lootables/SingleMushroom/AS_Mush_Open'),
            AS('/Game/InteractiveObjects/Lootables/Wyvern_Pile/_Shared/Animation/AS_Open'),
            AS('/Game/Lootables/Eridian/Chest_Red/Animation/AS_Open'),
            AS('/Game/Lootables/Eridian/Chest_White/Animation/AS_Open'),
            AS('/Game/Lootables/Eridian/Crate_Ammo/Animation/AS_Open'),
            AS('/Game/Lootables/_Global/Chest_Desert_White/Animation/AS_Open'),
            AS('/Game/Lootables/_Global/Chest_Fantasy_Red/Animation/AS_Open'),
            AS('/Game/Lootables/_Global/Chest_Fantasy_White/Animation/AS_Open'),
            AS('/Game/Lootables/_Global/Chest_Gold/Animation/AS_Close'),
            AS('/Game/Lootables/_Global/Chest_Gold/Animation/AS_Open'),
            AS('/Game/Lootables/_Global/Chest_Mushroom_White/Animation/AS_Open'),
            AS('/Game/Lootables/_Global/Chest_Overworld/Animation/AS_Open'),
            AS('/Game/Lootables/_Global/Chest_Sands_Red/Animation/AS_Open'),
            AS('/Game/Lootables/_Global/Chest_Seabed_White/Animation/AS_Open'),
            AS('/Game/Lootables/_Global/Crate_ButtStallion_OfferingBox/Animation/AS_Open'),
            AS('/Game/Lootables/_Global/Crate_Fantasy_Ammo/Animation/AS_Open'),
            AS('/Game/Lootables/_Global/Crate_Sands_Ammo/Animation/AS_Open'),
            AS('/Game/Lootables/_Global/Crate_Seabed_Ammo/Animation/AS_Open'),
            AS('/Game/Lootables/Industrial/Lock_Box/Animations/AS_Open'),
            AS('/Game/Lootables/Industrial/Safe/Animation/AS_Open'),
            AS('/Game/Lootables/Industrial/Strong_Box/Animation/AS_Open'),
            ]),
        ]:

    mod.comment(cat_name)

    for animseq in animseqs:

        if animseq.scale is None:
            animseq.scale = cat_scale
        if animseq.seqlen_scale is None:
            if cat_seqlen_scale is None:
                animseq.seqlen_scale = animseq.scale
            else:
                animseq.seqlen_scale = cat_seqlen_scale

        animseq.do_scale(mod, data)

    mod.newline()

# TODO: (these notes are very BL3-centric; make sure to clear this out if it's not really
# applicable later on)
# So there's various objects in here where we're doing an IO() tweak in this section, but then
# down below we also do some tweaking to a Timeline object, specifically tweaking its Length
# attr, to match up with the freshly-scaled IO() bits.  Well, towards the tail end of this mod
# development, I noticed that those Timeline objects also have a `PlayRate` attr, which
# simplifies this whole process -- namely, you can leave this IO() bit out, leave the Timeline
# `Length` how it is, and *just* alter the `PlayRate`.  I suspect I may not have the energy
# to convert all the prior stuff to do it, so I think this new method is likely to only be
# used for some of DLC2 and then DLC3.  Still, it might be worth converting it at some point.
# (To be fair, *most* of the IOs in here make sense to keep as they are -- it's mostly just the
# mission-related objects in the "Other" section which ended up requiring map-specific tweaks.
# We wouldn't want to have to touch every single map door object to alter PlayRate, etc.  It
# should be mostly just the ones where I've noted that there's extra tweaks "below.")

class IO():
    """
    Convenience class to allow me to loop over a bunch of IO/BPIO objects which largely
    use the defaults but which occasionally need to override 'em.
    """

    def __init__(self, path, label=None,
            hf_type=Mod.LEVEL, level='MatchAll', notify=False,
            scale=None, timelinelength=True,
            timeline_skip_set=None,
            ):
        self.path = path
        self.last_bit = path.split('/')[-1]
        self.last_bit_c = f'{self.last_bit}_C'
        self.full_path = f'{self.path}.{self.last_bit_c}'
        if label is None:
            self.label = self.last_bit
        else:
            self.label = label
        self.hf_type = hf_type
        self.level = level
        self.notify = notify
        self.scale = scale

        # This is just used to suppress warnings we'd otherwise print, for objects
        # we know don't have this attr
        self.timelinelength = timelinelength

        # Any timelines to skip
        if timeline_skip_set is None:
            self.timeline_skip_set = set()
        else:
            self.timeline_skip_set = timeline_skip_set

# It's tempting to try and limit some of these doors to the "obvious" particular level,
# but I just don't feel like trying to programmatically figure that out.  So, whatever.
checked_ver = False
for category, cat_scale, io_objs in [
        ('Doors', door_scale, [
            # find $(find . -name Doors) -name "IO_*.uasset" | sort -i | cut -d. -f2 | grep -v Parent
            IO('/Game/InteractiveObjects/Doors/Default/400x400/IO_Door_400x400_SlideLeftAndRight'),
            IO('/Game/InteractiveObjects/Doors/_Design/Classes/Global/IO_Daffodil_DamageableVines'),
            IO('/Game/InteractiveObjects/Doors/_Design/Classes/Global/IO_Door_130x250_HubPlayerDoor'),
            IO('/Game/InteractiveObjects/Doors/_Design/Classes/Global/IO_Door_550x550_IntroGate'),
            IO('/Game/InteractiveObjects/Doors/_Design/Classes/Global/IO_Door_550x550_NormalGate'),
            IO('/Game/InteractiveObjects/Doors/_Design/Classes/Global/IO_Door_600x400_SlideUp_Sands'),
            IO('/Game/InteractiveObjects/Doors/_Design/Classes/Global/IO_Door_600x400_SlideUp_Seabed'),
            IO('/Game/InteractiveObjects/Doors/_Design/Classes/Global/IO_Door_CustomSize_Rotate_IronGate_ButtStallion'),
            IO('/Game/InteractiveObjects/Doors/_Design/Classes/Global/IO_Door_CustomSize_Rotate_IronGate_Graveyard'),
            IO('/Game/InteractiveObjects/Doors/_Design/Classes/Global/IO_Door_CustomSize_Rotate_IronGate'),
            IO('/Game/InteractiveObjects/Doors/_Design/Classes/Global/IO_Door_HubDrawbridge'),
            IO('/Game/InteractiveObjects/Doors/_Design/Classes/Global/IO_Door_PyramidBridge'),
            IO('/Game/InteractiveObjects/Doors/_Design/Classes/Global/IO_Door_PyramidIronBear_Lrg'),
            IO('/Game/InteractiveObjects/Doors/_Design/Classes/Global/IO_Door_PyramidIronBear_TankRoom'),
            IO('/Game/InteractiveObjects/Doors/_Design/Classes/Global/IO_Door_PyramidIronBear'),
            IO('/Game/InteractiveObjects/Doors/_Design/Classes/Global/IO_Door_ScalablePortcullis'),
            IO('/Game/InteractiveObjects/Doors/_Design/Classes/Global/IO_Door_SkeepGate'),
            IO('/Game/InteractiveObjects/Doors/Mansion/_Design/IO_Door_CustomSize_Rotate_2Piece_IronGate'),
            # No timing parameters
            #IO('/Game/InteractiveObjects/Doors/Pyramid/_Design/IO_Taint_ExplodingPyramidDoorSimplified'),
            # No main TimelineLength
            #IO('/Game/InteractiveObjects/Doors/Pyramid/_Design/IO_Taint_ExplodingPyramidDoor'),
            IO('/Game/PatchDLC/Indigo1/Common/InteractiveObjects/Doors/IO_Door_Indigo_Portcullis_02'),
            # No main TimelineLength
            #IO('/Game/PatchDLC/Indigo1/Common/InteractiveObjects/Doors/IO_Door_Indigo_Portcullis'),
            IO('/Game/PatchDLC/Indigo1/Common/InteractiveObjects/Doors/IO_Door_SlideUp_ShipDeckGrateBig'),
            IO('/Game/PatchDLC/Indigo1/Common/InteractiveObjects/Doors/IO_Door_SlideUp_ShipDeckGrate'),
            ]),
        ('Switches', global_scale, [
            # find $(find . -name Switches) -name "IO_*.uasset" | sort -i | cut -d. -f2
            IO('/Game/InteractiveObjects/Switches/_Design/Classes/Global/IO_Daffodil_LichDoorbell'),
            IO('/Game/InteractiveObjects/Switches/_Design/Classes/Global/IO_Switch_Daffodil_SkullSwitch'),
            # No timing parameters
            #IO('/Game/InteractiveObjects/Switches/_Design/Classes/Global/IO_Switch_SimpleButton'),
            IO('/Game/InteractiveObjects/Switches/Hub_Switch/IO_Switch_Hub'),
            IO('/Game/InteractiveObjects/Switches/Lever/Design/IO_Switch_Industrial_FloorLever_V1_Damageable'),
            IO('/Game/InteractiveObjects/Switches/Lever/Design/IO_Switch_Industrial_FloorLever_V1'),
            IO('/Game/InteractiveObjects/Switches/Lever/Design/IO_TimedSwitch_Industrial_FloorLever_Damageable'),
            IO('/Game/InteractiveObjects/Switches/Lever/Design/IO_TimedSwitch_Industrial_FloorLever'),
            ]),
        ('Mission-Specific Machines', global_scale, [
            ]),
        ('Other Machines', global_scale, [
            ]),
        ]:

    mod.header(f'InteractiveObject Speedups: {category}')

    for io_obj in io_objs:

        if verbose:
            print('Processing {}'.format(io_obj.path))

        if io_obj.scale is None:
            io_obj.scale = cat_scale

        mod.comment(io_obj.label)
        obj = data.get_data(io_obj.path)
        if not obj:
            print('WARNING - Could not be serialized: {}'.format(io_obj.path))
            continue

        if not checked_ver:
            if '_apoc_data_ver' not in obj[0] or obj[0]['_apoc_data_ver'] < min_apoc_jwp_version:
                raise RuntimeError('In order to generate a valid mod, you MUST use Apocalyptech\'s JWP fork which serializes to version {}'.format(min_apoc_jwp_version))
            checked_ver = True

        found_primary = False
        did_main = False
        did_curve = False
        for export in obj:
            if export['_jwp_object_name'] == io_obj.last_bit_c:
                found_primary = True
                if 'Timelines' in export:
                    for timeline_idx, timeline_ref in enumerate(export['Timelines']):
                        timeline_exp = timeline_ref['export']
                        timeline_name = timeline_ref['_jwp_export_dst_name']
                        if timeline_name in io_obj.timeline_skip_set:
                            if verbose:
                                print(f' - Skipping timeline {timeline_idx} ({timeline_name}, export {timeline_exp})')
                            continue
                        if verbose:
                            print(f' - Processing timeline {timeline_idx} ({timeline_name}, export {timeline_exp})')
                        if timeline_exp != 0:
                            timeline = obj[timeline_exp-1]

                            # This one's not actually required (and doesn't seem to do anything), but I feel weird *not* specifying it.
                            # NOTE: I *think* that when this attr doesn't show up, it's probably because
                            # there's a LengthMode=TL_TimelineLength in play, which you'll see in the
                            # map object itself, and the length ends up getting sort of computed?
                            # Anyway, in those instances I believe the TimelineLength *does* show up
                            # in this object if you query it, but the one you need to alter is the
                            # one from the map object.  So you'll want to `getall` on that TimelineComponent
                            # to ensure what it is and then do a tweak down below.  Fun!  You can see this
                            # in the BL3 data on the IO_MissionPlaceable_BloodJar in Lake_P.
                            if 'TimelineLength' in timeline and timeline['TimelineLength'] != 0:
                                did_main = True
                                mod.reg_hotfix(io_obj.hf_type, io_obj.level,
                                        io_obj.full_path,
                                        f'Timelines.Timelines[{timeline_idx}].Object..TimelineLength',
                                        round(timeline['TimelineLength']/io_obj.scale, 6),
                                        notify=io_obj.notify,
                                        )

                            # Now process all our various curves
                            for trackname, curve_var in [
                                    ('EventTracks', 'CurveKeys'),
                                    ('FloatTracks', 'CurveFloat'),
                                    # I think VectorTracks is generally not needed; more used for
                                    # rotation+position info, perhaps?
                                    ('VectorTracks', 'CurveVector'),
                                    ]:
                                if trackname in timeline:
                                    if verbose:
                                        print('   - Processing {}'.format(trackname))
                                    for track_idx, track_ref in enumerate(timeline[trackname]):
                                        track_exp = track_ref[curve_var]['export']
                                        if verbose:
                                            print('     - On curve {} (export {})'.format(track_idx, track_exp))
                                        if track_exp != 0:
                                            curve = obj[track_exp-1]
                                            for inner_curve_var in ['FloatCurve', 'FloatCurves']:
                                                if inner_curve_var in curve:
                                                    for key_idx, key in enumerate(curve[inner_curve_var]['Keys']):
                                                        if key['time'] != 0:
                                                            did_curve = True
                                                            mod.reg_hotfix(io_obj.hf_type, io_obj.level,
                                                                    io_obj.full_path,
                                                                    f'Timelines.Timelines[{timeline_idx}].Object..{trackname}.{trackname}[{track_idx}].{curve_var}.Object..{inner_curve_var}.Keys.Keys[{key_idx}].Time',
                                                                    round(key['time']/io_obj.scale, 6),
                                                                    notify=io_obj.notify,
                                                                    )


        if not found_primary:
            raise RuntimeError('Could not find main export for {}'.format(io_obj.path))

        if not did_main and not did_curve:
            print('NOTICE - No timing parameters found for {}'.format(io_obj.path))
            mod.comment('(no timing parameters found to alter)')
        elif not did_main:
            # This honestly hardly matters; it doesn't look like this attr's really used
            # for much, anyway.
            if io_obj.timelinelength:
                print('NOTICE - No main TimelineLength found for {}'.format(io_obj.path))
        elif not did_curve:
            print('NOTICE - No curve timings found for {}'.format(io_obj.path))

        mod.newline()

# `getall Elevator`
mod.header('Elevators')
for label, level, obj_name, speed, travel_time in sorted([
        #("Weepwild Dankness", 'Mushroom_P',
        #    '/Game/Maps/Zone_1/Mushroom/Mushroom_Boss.Mushroom_Boss:PersistentLevel.Elevator_Banshee_1',
        #    400, 8),
        #("Weepwild Dankness", 'Mushroom_P',
        #    '/Game/Maps/Zone_1/Mushroom/Mushroom_Boss.Mushroom_Boss:PersistentLevel.Elevator_Banshee_2',
        #    400, 8),
        #("Weepwild Dankness", 'Mushroom_P',
        #    '/Game/Maps/Zone_1/Mushroom/Mushroom_Boss.Mushroom_Boss:PersistentLevel.Elevator_Banshee_3',
        #    400, 8),
        #("Crackmast Cove", 'Pirate_P',
        #    '/Game/Maps/Zone_2/Pirate/Pirate_M_CrookedEyePhil.Pirate_M_CrookedEyePhil:PersistentLevel.Elevator_PirateMajor_Pirate_2',
        #    250, 10),
        #("Karnok's Wall", 'Climb_P',
        #    '/Game/Maps/Zone_2/Climb/Climb_M_Plot8.Climb_M_Plot8:PersistentLevel.Elevator_BoneElevator_2',
        #    200, 8),
        #("Karnok's Wall", 'Climb_P',
        #    '/Game/Maps/Zone_2/Climb/Climb_M_Plot8.Climb_M_Plot8:PersistentLevel.Elevator_Plot8_Climb_Repaired',
        #    200, 10),
        #("Sunfang Oasis", 'Oasis_P',
        #    '/Game/Maps/Zone_3/Oasis/Oasis_M_CloggageOfTheDammed.Oasis_M_CloggageOfTheDammed:PersistentLevel.Elevator_Sewers_WaterRising_6',
        #    75, 10),
        #("Sunfang Oasis", 'Oasis_P',
        #    '/Game/Maps/Zone_3/Oasis/Oasis_M_CloggageOfTheDammed.Oasis_M_CloggageOfTheDammed:PersistentLevel.Elevator_Sewers_WaterRising_0',
        #    100, 10),
        #("Ossu-Gol Necropolis", 'Sands_P',
        #    '/Game/Maps/Zone_3/Sands/Sands_Dynamic.Sands_Dynamic:PersistentLevel.Elevator_SandsBridge_3',
        #    200, 8),
        #("Ossu-Gol Necropolis", 'Sands_P',
        #    '/Game/Maps/Zone_3/Sands/Sands_Dynamic.Sands_Dynamic:PersistentLevel.Elevator_SandsBridge_4',
        #    200, 8),
        #("Ossu-Gol Necropolis", 'Sands_P',
        #    '/Game/Maps/Zone_3/Sands/Sands_M_Plot09.Sands_M_Plot09:PersistentLevel.Elevator_BoneElevator_2',
        #    200, 8),
        #("The Fearamid", 'Pyramid_P',
        #    '/Game/Maps/Zone_3/Pyramid/Pyramid_Dynamic.Pyramid_Dynamic:PersistentLevel.Elevator_BoneElevator_2',
        #    200, 8),
        ]):
    mod.comment(label)
    # Honestly not sure if we need both of these, but we *do* need EarlyLevel.  I'm pretty
    # sure that the one we *actually* need is TravelTime -- I think the Speed ends up
    # getting dynamically set.  Whatever, it doesn't *hurt*.
    #mod.reg_hotfix(Mod.EARLYLEVEL, level,
    #        obj_name,
    #        'ElevatorSpeed',
    #        speed*global_scale,
    #        )
    mod.reg_hotfix(Mod.EARLYLEVEL, level,
            obj_name,
            'ElevatorTravelTime',
            travel_time/global_scale,
            )
    mod.newline()

mod.header('NPC Walking Speeds')

class Char():
    """
    Convenience class for looping over a bunch of BPChar objects for speed improvements.
    At the moment there's not really much of a reason to do this instead of just looping
    over a list of tuples, but we're doing other classes like this anyway (IO and AS),
    so I may as well do this too.
    """

    def __init__(self, name, path, scale, sprint_scale=None, force_have_slowdown=False):
        self.name = name
        self.path = path
        self.last_bit = path.split('/')[-1]
        self.default_name = f'Default__{self.last_bit}_C'
        self.default_name_lower = self.default_name.lower()
        self.full_path = f'{self.path}.{self.default_name}'
        self.scale = scale
        self.force_have_slowdown = force_have_slowdown
        if sprint_scale is None:
            self.sprint_scale = scale
        else:
            self.sprint_scale = sprint_scale

    def __lt__(self, other):
        return self.name.casefold() < other.name.casefold()

for char in sorted([
        #Char('Claptrap',
        #    '/Game/NonPlayerCharacters/Claptrap/_Design/Character/BpChar_Claptrap',
        #    global_char_scale,
        #    ),
        ]):

    found_main = False
    char_data = data.get_data(char.path)
    speed_walk = None
    speed_sprint = None
    have_slowdown = False
    for export in char_data:
        if export['_jwp_object_name'].lower() == char.default_name_lower:
            found_main = True
            if 'OakCharacterMovement' in export:
                if export['OakCharacterMovement']['export'] != 0:
                    move_export = char_data[export['OakCharacterMovement']['export']-1]
                    if 'MaxWalkSpeed' in move_export:
                        speed_walk = move_export['MaxWalkSpeed']['BaseValue']
                    else:
                        # The default
                        speed_walk = 600
                    if 'MaxSprintSpeed' in move_export:
                        speed_sprint = move_export['MaxSprintSpeed']['BaseValue']
                    else:
                        # The default
                        speed_sprint = 900
                    if char.force_have_slowdown \
                            or 'NavSlowdownOptions' in move_export and 'SlowdownSpeed' in move_export['NavSlowdownOptions']:
                        have_slowdown = True
                else:
                    raise RuntimeError('Could not find OakCharacterMovement export in {}'.format(char.path))
            else:
                raise RuntimeError('Could not find OakCharacterMovement in {}'.format(char.path))
            break
    if not found_main:
        raise RuntimeError('Could not find {} in {}'.format(char.default_name, char.path))

    mod.comment(char.name)
    mod.reg_hotfix(Mod.CHAR, char.last_bit,
            char.full_path,
            'OakCharacterMovement.Object..MaxWalkSpeed',
            '(Value={},BaseValue={})'.format(
                round(speed_walk*char.scale, 6),
                round(speed_walk*char.scale, 6),
                ),
            )
    # NOTE: After spending quite a bit of time getting Oletta sorted out, I'm pretty sure
    # that MaxSprintSpeed isn't actually used by NPCs.  I'm pretty sure that the stances
    # used to control NPC speeds just take the walk speed and scale it where appropriate.
    # I think that MaxWalkSpeed itself might even be scaled down a bit for the usual NPC
    # "Walk" stance.
    mod.reg_hotfix(Mod.CHAR, char.last_bit,
            char.full_path,
            'OakCharacterMovement.Object..MaxSprintSpeed',
            '(Value={},BaseValue={})'.format(
                round(speed_sprint*char.sprint_scale, 6),
                round(speed_sprint*char.sprint_scale, 6),
                ),
            )
    if have_slowdown:
        mod.reg_hotfix(Mod.CHAR, char.last_bit,
                char.full_path,
                'OakCharacterMovement.Object..NavSlowdownOptions.bSlowdownNearGoal',
                'False',
                )
        mod.reg_hotfix(Mod.CHAR, char.last_bit,
                char.full_path,
                'OakCharacterMovement.Object..NavSlowdownOptions.SlowdownSpeed.Value',
                1,
                )
    mod.newline()

mod.close()
