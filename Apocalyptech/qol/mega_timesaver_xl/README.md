Mega TimeSaver XL
=================

This mod aims to speed up nearly all the noticeably-slow interactive
objects that you use throughout WL.  It will eventually hope to encompass
basically the entire game, but **it is currently a work in progress!**

As such, this mod has not seen an awful lot of testing, so please let me
know if there's anything game-breaking or Obviously Wrong with this (like
if a too-fast animation ends up breaking mission progression somewhere).
Ordinarily I wouldn't release this until I'd had a chance to thoroughly
test it, but there's some fairly deep mining I need to do in the data to
finish it properly

Currently, the mod attempts to affect the following:

* Lootable Containers, Doors, Elevators, Loot Dice, Wheel of Fate, Lost
  Loot Machine, etc...


Not Handled By This Mod
=======================

Some things intentionally *not* handled by the mod, either because they were
already pretty good speedwise, because speedups would've caused dialogue
skips, or because it just felt right to leave 'em alone:

* The initial spawning of Overworld random encounter enemies
* Cheese curl removal sequence in the Overworld

Known Bugs / TODO
=================

* Haven't yet really run through the game often enough to have a feel
  for what might feel slow still.
* Lost Loot machine opening/closing -- can't seem to get those to speed up.
* The loot from some containers in the overworld (Crates, Pottery) get picked
  up immediately on spawn (so long as the player's in range) but the loot from
  others (chests, barrels) does NOT.  The most useful comparison would be
  between the destructible ones, so check out `/Game/Lootables/_Design/Classes/Destructibles/Overworld`.
  I can hardly see any difference, alas.  I think the answer might be that
  the immediate-pickup ones seem to use `BP_LootableDestructible` whereas
  the non-immediate-pickup ones use `BP_LootableDestructible_Daffodil`.
  I can't see anything useful between those two -- the `_Daffodil` version
  just includes some Mimic-related code.
* The yellow glow after rolling Lucky Dice hangs around for the usual duration.
  No idea what controls that, but it doesn't get in the way of the sped-up
  loot shower.
* Maybe re-test up to Brighthoof restoration (and remainder of Queen's Gate)?
  Basically everything before Weepwild Dankness (and also before Mount Craw).
  I bumped the speed increase back up to 5x; WL containers seem a bit slower
  than BL3's.

Changelog
=========

**v1.0.0** - *(unreleased)*
 * Merged in a lot of internal infrastructure from the now-"finished" BL3 version
 * New Additions:
   * Photo Mode activation time
   * Fast-travel/teleport/resurrect skips
   * Random Encounter + Dungeon speedups
   * Lost Loot Machine
   * Wheel of Fate
   * Lucky Dice
 * Mission/Level Specific Objects:
   * Starting platform-rise in Snoring Valley
   * Intro gate in Snoring Valley
   * Tome of Fate secret stairs in Shattergrave Barrow
   * Sword of Souls town-restoration sequences in Brighthoof
 * Character Speedups:
   * Flora and Glornesh (from A Farmer's Ardor)

**v0.9.0** - Jul 28, 2022
 * Initial beta release.  Incomplete, but should be handy regardless!
   Based on v0.9.1 of [BL3's Mega TimeSaver XL](https://github.com/BLCM/bl3mods/wiki/Mega%20TimeSaver%20XL)
 
Licenses
========

This mod is licensed under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).

The generation script for the mod is licensed under the
[GPLv3 or later](https://www.gnu.org/licenses/quick-guide-gplv3.html).
See [COPYING.txt](../../COPYING.txt) for the full text of the license.

