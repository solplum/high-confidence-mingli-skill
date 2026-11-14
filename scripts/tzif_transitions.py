"""Exact checkpoint hints for a query ZoneInfo built from the same TZif bytes."""
from bisect import bisect_left
from calendar import monthrange
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from importlib import resources
from io import BytesIO
from itertools import chain
from pathlib import Path
import re
import struct
import zoneinfo


EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
DAY_SECONDS = 86400
# A pair of valid datetime offsets differs by less than two days.
MIN_TRANSITION_GAP = 2 * DAY_SECONDS
HEADER = struct.Struct('>4sc15x6I')
POSIX_SECONDS = r'[+-]?[0-9]{1,3}(?::[0-5][0-9](?::[0-5][0-9])?)?'
POSIX_NAME = r'(?:[A-Za-z]{3,}|<[A-Za-z0-9+-]{3,}>)'
POSIX_HEAD = re.compile(rf'{POSIX_NAME}({POSIX_SECONDS})(?:({POSIX_NAME})({POSIX_SECONDS})?)?')
POSIX_MONTH = re.compile(rf'M(1[0-2]|[1-9])\.([1-5])\.([0-6])(?:/({POSIX_SECONDS}))?')


def read_tzif(zone):
    """Read the public zoneinfo search path or first-party tzdata package."""
    parts = zone.split('/')
    if any(part in ('', '.', '..') for part in parts) or '\\' in zone or ':' in zone:
        return None
    for root in zoneinfo.TZPATH:
        path = Path(root).joinpath(*parts)
        if path.is_file():
            try:
                return path.read_bytes(), 'host_iana_tzif'
            except OSError:
                return None
    try:
        path = resources.files('tzdata.zoneinfo')
        for part in parts:
            path = path.joinpath(part)
        return path.read_bytes(), 'tzdata_package'
    except (ImportError, OSError):
        return None


def source_provenance(zone, source):
    if source is None:
        return {'kind': 'unverified_iana_source', 'zone': zone, 'tzif_sha256': None}
    data, kind = source
    return {'kind': kind, 'zone': zone, 'tzif_sha256': sha256(data).hexdigest()}


def _block(data, start, width):
    magic, version, ut, std, leaps, count, types, chars = HEADER.unpack_from(data, start)
    if magic != b'TZif' or version not in (b'\0', b'2', b'3', b'4') or not 1 <= types <= 256:
        raise ValueError('Unsupported TZif header')
    begin = start + HEADER.size
    info = begin + count * (width + 1)
    end = info + types * 6 + chars + leaps * (width + 4) + std + ut
    if end > len(data):
        raise ValueError('Incomplete TZif data block')
    return version, begin, count, info, types, end


def _seconds(text):
    hour, *rest = map(int, text.lstrip('+-').split(':'))
    minute, second = (rest + [0, 0])[:2]
    total = hour * 3600 + minute * 60 + second
    return -total if text.startswith('-') else total


def _month_rule(text):
    match = POSIX_MONTH.fullmatch(text)
    if match is None:
        return None
    month, week, weekday = map(int, match.groups()[:3])
    clock = _seconds(match[4]) if match[4] is not None else 7200
    # These bounds keep both UTC and local event lookups in the same year.
    if not 2 <= month <= 11 or abs(clock) >= 7 * DAY_SECONDS:
        return None
    return month, week, weekday, clock


def _footer(data):
    """Decode a fixed tail or the common, unambiguous recurring month rules."""
    if data == b'\n\n':
        return ()
    if not (data.startswith(b'\n') and data.endswith(b'\n')):
        return None
    head, *rules = data[1:-1].decode('ascii').split(',')
    match = POSIX_HEAD.fullmatch(head)
    if match is None:
        return None
    standard = -_seconds(match[1])
    if abs(standard) >= DAY_SECONDS:
        return None
    if match[2] is None:
        return standard if not rules else None
    daylight = -_seconds(match[3]) if match[3] is not None else standard + 3600
    if len(rules) != 2 or abs(daylight) >= DAY_SECONDS:
        return None
    start, end = map(_month_rule, rules)
    if start is None or end is None:
        return None
    return ((start, standard, daylight), (end, daylight, standard))


def _index(data):
    version, begin, count, info, types, end = _block(data, 0, 4)
    format_code = 'i'
    tail = ()
    if version != b'\0':
        version, begin, count, info, types, end = _block(data, end, 8)
        if version == b'\0':
            return None
        format_code = 'q'
        tail = _footer(data[end:])
    transitions = struct.unpack_from(f'>{count}{format_code}', data, begin)
    offsets = [struct.unpack_from('>i', data, info + index * 6)[0] for index in range(types)]
    # Wall-clock fold lookups can overlap for dense transitions. A DST first
    # type can also select a different pre-transition type for UTC lookups.
    if (any(abs(offset) >= DAY_SECONDS for offset in offsets) or
            (transitions and data[info + 4] != 0) or
            any(b - a <= MIN_TRANSITION_GAP for a, b in zip(transitions, transitions[1:]))):
        return None
    if transitions:
        last_type = data[info - 1]
        if last_type >= types:
            return None
        if not _tail_matches(tail, transitions[-1], offsets[last_type]):
            tail = None
    return transitions, () if type(tail) is int else tail


def _epoch_second(value):
    delta = value - EPOCH
    return delta.days * DAY_SECONDS + delta.seconds


def _transition(year, rule, offset):
    month, week, weekday, clock = rule
    first_weekday, days = monthrange(year, month)
    day = 1 + (weekday - first_weekday - 1) % 7 + 7 * (week - 1)
    if day > days:
        day -= 7
    local_day = datetime(year, month, day, tzinfo=timezone.utc)
    return _epoch_second(local_day) + clock - offset


def _tail_matches(tail, last, offset):
    if type(tail) is int:
        return offset == tail
    if not tail:
        return True
    year = (EPOCH + timedelta(seconds=last)).year
    (start_rule, standard, daylight), (end_rule, _, _) = tail
    start = _transition(year, start_rule, standard)
    end = _transition(year, end_rule, daylight)
    is_daylight = start <= last < end if start < end else not end <= last < start
    return offset == (daylight if is_daylight else standard)


class _QueryZone(zoneinfo.ZoneInfo):
    def _offset_at(self, timestamp):
        instant = EPOCH + timedelta(seconds=timestamp)
        return instant.astimezone(self).utcoffset()

    def _tail_checkpoints(self, start, end, low, high, last, tail):
        if tail is None:
            return None
        if last is not None and low - MIN_TRANSITION_GAP <= last < high + MIN_TRANSITION_GAP:
            if self._offset_at(last) != self._offset_at(last + 1):
                return None
        events = sorted((_transition(year, rule, before), before, after)
                        for year in range(start.year, end.year + 1)
                        for rule, before, after in tail)
        events = [(point, before, after) for point, before, after in events
                  if last is None or point > last]
        if ((events and last is not None and events[0][0] - last <= MIN_TRANSITION_GAP) or
                any(b[0] - a[0] <= MIN_TRANSITION_GAP for a, b in zip(events, events[1:]))):
            return None
        inside = [(point, before, after) for point, before, after in events if low <= point < high]
        # Reconfirm the offsets with the actual ZoneInfo, not the parser.
        if any(self._offset_at(point - 1) != timedelta(seconds=before) or
               self._offset_at(point) != timedelta(seconds=after) for point, before, after in inside):
            return None
        return [point for point, _, _ in inside]

    def _checkpoint_seconds(self, start, end):
        low = _epoch_second(start) + 1
        high = _epoch_second(end) + bool(end.microsecond)
        if self._transition_index is None:
            return range(low, high)
        transitions, tail = self._transition_index
        last = transitions[-1] if transitions else None
        if last is not None and high <= last - MIN_TRANSITION_GAP:
            return transitions[bisect_left(transitions, low):bisect_left(transitions, high)]
        join_start = join_end = low
        if last is not None and tail:
            # Wall-clock lookups can overlap at the switch from the explicit
            # table to recurrence, even when their final offsets agree.
            join_start = max(low, last - MIN_TRANSITION_GAP)
            join_end = min(high, last + MIN_TRANSITION_GAP + 1)
        recurring = self._tail_checkpoints(start, end, max(low, join_end), high, last, tail)
        if recurring is None:
            # An unfamiliar tail can affect wall-clock lookups near the seam.
            scan_from = low if last is None else max(low, last - MIN_TRANSITION_GAP)
            explicit = transitions[bisect_left(transitions, low):bisect_left(transitions, scan_from)]
            return chain(explicit, range(scan_from, high))
        if join_start < join_end:
            explicit = transitions[bisect_left(transitions, low):bisect_left(transitions, join_start)]
            return chain(explicit, range(join_start, join_end), recurring)
        explicit = transitions[bisect_left(transitions, low):bisect_left(transitions, high)]
        return (*explicit, *recurring)

    def offset_checkpoints(self, start, end):
        return (EPOCH + timedelta(seconds=point) for point in self._checkpoint_seconds(start, end))


def bind_query_zone(reference):
    """Bind offset hints and provenance to the ZoneInfo instance reading those bytes."""
    source = read_tzif(reference.key)
    if source is None:
        return reference
    data, _ = source
    try:
        tz = _QueryZone.from_file(BytesIO(data), key=reference.key)
    except (ValueError, OSError, OverflowError):
        return reference
    tz.tzif_source = source_provenance(reference.key, source)
    try:
        tz._transition_index = _index(data)
    except (ValueError, OverflowError, struct.error):
        tz._transition_index = None
    return tz
