# SPDX-License-Identifier: GPL-3.0-only
# This module is local. It is not part of upstream my-avbroot-setup.
#
# This module removes a faulty thermistor from the thermal configuration in the
# vendor partition. Each virtual sensor has a formula that reads a list of
# sensors. For each formula that reads the faulty sensor, the module does two steps:
#   1. It adds the coefficient of the faulty sensor to a healthy neighbor sensor
#      (target += source). The neighbor sensor must already be in the formula.
#   2. It removes the faulty sensor from the Combination and Coefficient arrays.
#
# Math (Pixel thermal HAL, hardware/google/pixel/thermal/thermal-helper.cpp):
#   WEIGHTED_AVG = sum(reading[i] * coefficient[i]) + offset   (then * multiplier)
# As a result, the formula uses the reading of the target in place of the
# reading of the source.
#
# The module removes the sensor. It does not only set the coefficient to 0.
# The HAL reads each linked sensor before it applies the coefficients. If one
# read fails, the full virtual sensor returns ERROR, also at coefficient 0.
# The fault gets worse with time. Thus no formula can depend on a read of the
# faulty sensor.
#
# The sensor stays defined and stays a TriggerSensor. On husky, the sensor is a
# real kernel thermal zone. VIRTUAL-SKIN and other sensors use it as a
# TriggerSensor. At start, the HAL verifies that each trigger sensor name exists.
# The threshold of the sensor gives only information: it has Type UNKNOWN, no
# cooling device and no callback.
#
# The edit changes text only in the single-line "Combination" and "Coefficient"
# arrays of the affected formulas. Then the module parses the JSON again and
# verifies these conditions:
#   - The parsed JSON is different from the original only in these arrays.
#   - The sum of the coefficients of each formula stays the same.
#   - No formula reads the source sensor.
# If a condition is not true, the module stops with an error.

import argparse
from collections.abc import Iterable
import json
import logging
import math
from pathlib import Path, PurePosixPath
import re
from typing import Any, override

from lib import modules
from lib.filesystem import CpioFs, ExtFs
from lib.modules import Module, ModuleRequirements


logger = logging.getLogger(__name__)

_TOP_LEVEL_KEY = re.compile(r'^ {4}"(\w+)"\s*:')
_NAME_LINE = re.compile(r'^\s*"Name"\s*:\s*"([^"]+)"\s*,\s*$')
_ARRAY_LINE = r'^(\s*"{key}"\s*:\s*\[)([^\]]*)(\]\s*,?\s*)$'
_OBJ_END = re.compile(r'^\s*\}\s*,?\s*$')


def _fmt(x: float) -> str:
    x = round(x, 6)
    if x == int(x):
        return str(int(x))
    return f'{x:.6f}'.rstrip('0').rstrip('.')


def _is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


class NorthThermRewireModule(Module):
    NAME: str = 'north-therm-rewire'

    @classmethod
    @override
    def add_args(cls, parser: argparse.ArgumentParser):
        parser.add_argument(
            '--north-therm-rewire',
            action='store_true',
            help='Remove the faulty sensor from each vendor thermal formula. '
                 'Add its weight to a healthy neighbor sensor.',
        )
        parser.add_argument(
            '--north-therm-source',
            default='north_therm',
            help='The faulty sensor to remove from the formulas (default: north_therm)',
        )
        parser.add_argument(
            '--north-therm-target',
            default='cam_therm',
            help='The healthy sensor that gets the weight (default: cam_therm)',
        )

    def __init__(self, args: argparse.Namespace) -> None:
        if not getattr(args, 'north_therm_rewire', False):
            raise modules.MissingArgs()

        self.source: str = args.north_therm_source
        self.target: str = args.north_therm_target

        if self.source == self.target:
            raise ValueError('The source sensor and the target sensor must be different')

    @override
    def requirements(self) -> ModuleRequirements:
        return ModuleRequirements(
            boot_images=set(),
            ext_images={'vendor'},
            selinux_patching=False,
        )

    @override
    def inject(
        self,
        boot_fs: dict[str, CpioFs],
        ext_fs: dict[str, ExtFs],
        sepolicies: Iterable[Path],
    ) -> None:
        vendor = ext_fs['vendor']
        etc = vendor.tree / 'etc'

        candidates = sorted(
            p for p in etc.glob('*thermal*.json')
            if self.source in p.read_text()
        )
        if not candidates:
            raise ValueError(f'No vendor thermal configuration reads {self.source}')

        total = 0
        for path in candidates:
            rel = PurePosixPath('etc') / path.name
            new_text, changes = rewire_text(
                path.read_text(), self.source, self.target, str(rel))

            with vendor.open(rel, 'w') as f:
                f.write(new_text)

            for name, old, new in changes:
                logger.info(f'  /vendor/{rel}: {name}: {old} -> {new}')
            logger.info(f'Changed {len(changes)} formula(s) in /vendor/{rel}')
            total += len(changes)

        logger.info(f'{self.NAME}: changed {total} formula(s) in '
                    f'{len(candidates)} file(s)')


def _plan(sensors: list[dict], source: str, target: str, label: str) -> dict:
    plan = {}
    for s in sensors:
        comb = s.get('Combination')
        if not comb or source not in comb:
            continue
        name = s['Name']

        for key in ('CoefficientType', 'CombinationType'):
            if key in s:
                raise ValueError(f'{label}: {name} has {key}. The effect of this key is not known.')
        if s.get('Formula') != 'WEIGHTED_AVG':
            raise ValueError(f'{label}: {name} uses Formula {s.get("Formula")!r}. '
                             'The module changes only WEIGHTED_AVG formulas.')
        if comb.count(source) != 1 or comb.count(target) != 1:
            raise ValueError(f'{label}: {name} must contain {source} and {target} exactly one time each')
        if len(comb) < 2:
            raise ValueError(f'{label}: the Combination of {name} becomes empty')

        coef = s.get('Coefficient')
        if (not isinstance(coef, list) or len(coef) != len(comb)
                or not all(_is_number(c) for c in coef)):
            raise ValueError(f'{label}: {name} has an unexpected Coefficient format')

        ni, ti = comb.index(source), comb.index(target)
        new_coef = list(coef)
        new_coef[ti] = round(coef[ti] + coef[ni], 6)
        del new_coef[ni]
        new_comb = [c for c in comb if c != source]
        plan[name] = {
            'old_comb': comb, 'old_coef': coef,
            'new_comb': new_comb, 'new_coef': new_coef,
            'ni': ni, 'ti': ti,
        }
    return plan


def rewire_text(
    text: str,
    source: str,
    target: str,
    label: str,
) -> tuple[str, list[tuple[str, list, list]]]:
    """Return (new_text, [(sensor_name, old_coefficients, new_coefficients)])."""

    orig = json.loads(text)
    sensors = orig.get('Sensors')
    if not isinstance(sensors, list):
        raise ValueError(f'{label}: the "Sensors" array is missing')

    names = [s.get('Name') for s in sensors]
    for required in (source, target):
        if names.count(required) != 1:
            raise ValueError(f'{label}: there must be exactly one sensor with the name {required!r}')

    plan = _plan(sensors, source, target, label)

    lines = text.split('\n')
    top = [(i, m.group(1)) for i, l in enumerate(lines) if (m := _TOP_LEVEL_KEY.match(l))]
    try:
        start = next(i for i, k in top if k == 'Sensors')
    except StopIteration:
        raise ValueError(f'{label}: the top-level "Sensors" line is missing')
    end = next((i for i, _ in top if i > start), len(lines))

    comb_re = re.compile(_ARRAY_LINE.format(key='Combination'))
    coef_re = re.compile(_ARRAY_LINE.format(key='Coefficient'))

    def find_array(name: str, first: int, regex: re.Pattern) -> int:
        j = first
        while j < end and not regex.match(lines[j]):
            if _OBJ_END.match(lines[j]):
                raise ValueError(f'{label}: {name}: there is no single-line array before the end of the object')
            j += 1
        if j >= end:
            raise ValueError(f'{label}: {name}: the array is missing')
        return j

    changes = []
    for name, p in plan.items():
        hits = [i for i in range(start, end)
                if (m := _NAME_LINE.match(lines[i])) and m.group(1) == name]
        if len(hits) != 1:
            raise ValueError(f'{label}: Sensors must have 1 Name line for {name}, but it has {len(hits)}')

        # Combination line
        jc = find_array(name, hits[0] + 1, comb_re)
        m = comb_re.match(lines[jc])
        ctoks = [t.strip() for t in m.group(2).split(',')]
        if [t.strip('"') for t in ctoks] != p['old_comb']:
            raise ValueError(f'{label}: {name}: the Combination text is different from the parsed value')
        del ctoks[p['ni']]
        lines[jc] = m.group(1) + ', '.join(ctoks) + m.group(3)

        # Coefficient line
        jf = find_array(name, hits[0] + 1, coef_re)
        m = coef_re.match(lines[jf])
        ftoks = [t.strip() for t in m.group(2).split(',')]
        if len(ftoks) != len(p['old_coef']) or any(
                not math.isclose(float(t), float(c)) for t, c in zip(ftoks, p['old_coef'])):
            raise ValueError(f'{label}: {name}: the Coefficient text is different from the parsed value')
        ftoks[p['ti']] = _fmt(p['new_coef'][p['ti'] if p['ti'] < p['ni'] else p['ti'] - 1])
        del ftoks[p['ni']]
        lines[jf] = m.group(1) + ', '.join(ftoks) + m.group(3)

        changes.append((name, list(zip(p['old_comb'], p['old_coef'])),
                        list(zip(p['new_comb'], p['new_coef']))))

    new_text = '\n'.join(lines)
    verify(orig, json.loads(new_text), plan, source, label)
    return new_text, changes


def verify(orig: dict, patched: dict, plan: dict, source: str, label: str) -> None:
    if list(orig) != list(patched):
        raise ValueError(f'{label}: the top-level keys changed')
    for key in orig:
        if key != 'Sensors' and orig[key] != patched[key]:
            raise ValueError(f'{label}: the section {key!r} has an unplanned change')

    so, sp = orig['Sensors'], patched['Sensors']
    if [s.get('Name') for s in so] != [s.get('Name') for s in sp]:
        raise ValueError(f'{label}: the list or the order of the sensors changed')

    for a, b in zip(so, sp):
        name = a.get('Name')
        if list(a) != list(b):
            raise ValueError(f'{label}: {name}: the keys changed')
        for k in a:
            if name in plan and k in ('Combination', 'Coefficient'):
                continue
            if a[k] != b[k]:
                raise ValueError(f'{label}: {name}: the field {k!r} has an unplanned change')
        if name in plan:
            p = plan[name]
            if b['Combination'] != p['new_comb']:
                raise ValueError(f'{label}: {name}: the patched Combination is different from the plan')
            if len(b['Coefficient']) != len(b['Combination']) or any(
                    not math.isclose(x, y, abs_tol=1e-9)
                    for x, y in zip(b['Coefficient'], p['new_coef'])):
                raise ValueError(f'{label}: {name}: the patched Coefficient is different from the plan')
            if not math.isclose(sum(a['Coefficient']), sum(b['Coefficient']), abs_tol=1e-9):
                raise ValueError(f'{label}: {name}: the sum of the coefficients changed')

    for s in sp:
        if source in (s.get('Combination') or []):
            raise ValueError(f'{label}: {s["Name"]} still reads {source}')
    # The definition of the source sensor must not change.
    src_o = next(s for s in so if s.get('Name') == source)
    src_p = next(s for s in sp if s.get('Name') == source)
    if src_o != src_p:
        raise ValueError(f'{label}: the definition of {source} changed')
