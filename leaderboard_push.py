"""Small optional background publisher. No tokens or private user records are exported."""
import asyncio
import contextlib
import heapq
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from urllib import request, error, parse

from game_data import BADGES, SPECIAL_BADGES

log = logging.getLogger('idlehunter.leaderboard')

class NoRedirect(request.HTTPRedirectHandler):
    # Never forward the secret to a redirect destination.
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def score(value):
    try:
        return max(0, min(int(value), 10**100 - 1))
    except (ValueError, TypeError, OverflowError):
        return 0


def public_id(uid) -> str:
    """A short, stable, non-reversible tag so two players with the same display name can be told apart on the
    website without ever exposing their Discord id."""
    import hashlib
    return hashlib.sha256(('idle-hunter-lb:' + str(uid)).encode()).hexdigest()[:8]


def public_name(value, fallback):
    text = ''.join(c for c in str(value or fallback) if ord(c) >= 32).strip()
    return text[:100] or fallback


def _stat(record, field):
    """Read a nested stat: 'stats.myths_killed', or a top-level field."""
    if field.startswith('stats.'):
        return (record.get('stats') or {}).get(field.split('.', 1)[1], 0)
    if field == 'regions':
        return len(record.get('guide_seen') or [])
    return record.get(field, 0)


def featured_badge(record):
    """{'icon', 'tier'} for the player's featured badge (mirrors app.py's
    featured_badge_key/_badge_tier without importing the bot module), or None.
    Special (admin-granted) badges have no website artwork yet, so a featured
    special badge is skipped here rather than sent as a broken image."""
    earned_stat = [k for k in BADGES
                   if record.get('badges', {}).get(k, {}).get('tier', 0) >= 1]
    earned_special = [k for k in SPECIAL_BADGES if k in (record.get('special_badges') or [])]
    earned = earned_stat + earned_special
    if not earned:
        return None
    pick = record.get('featured_badge')
    key = pick if pick in earned else earned[0]
    if key not in BADGES:
        return None   # a special badge is featured — no website art for it yet
    tier = record.get('badges', {}).get(key, {}).get('tier', 0)
    return {'icon': BADGES[key].get('icon', key), 'tier': 'platinum' if tier >= 2 else 'gold'}


_FIELDS = [
    ('level', 'level'), ('money', 'money'), ('prestige', 'prestige'),
    ('caught', 'total_caught'),
    ('lifetime_caught', 'stats.lifetime_caught'),
    # Idle Hunter V2 — exploration-flavoured boards
    ('myths', 'stats.myths_killed'),
    ('tracking', 'stats.tracks_completed'),
    ('regions', 'regions'),
]
_YIELD_EVERY = 200   # players scored between event-loop yields


async def build_payload(users, tribes, excluded=(), world=None):
    """Top-100 boards in ONE pass over the players (it used to scan everyone once
    per board — 7 full scans plus a separate tester scan — in a single blocking
    burst). Runs on the Discord event loop, so it yields every _YIELD_EVERY
    players instead of freezing every click for the duration; each player is read
    in a single loop step, so no cross-thread access to mutable bot state either.
    Only the finished, detached payload goes to a worker thread."""
    heaps = {key: [] for key, _ in _FIELDS}
    uid_of = {}      # id(record) -> Discord id, only to derive the public id below (never exported)
    for n, (uid, record) in enumerate(list(users.items())):
        if str(uid) not in excluded and not record.get('is_tester'):
            for key, field in _FIELDS:
                # (score, -position) so ties keep original order, like nlargest(key=score)
                item = (score(_stat(record, field)), -n, record)
                uid_of[id(record)] = str(uid)
                heap = heaps[key]
                if len(heap) < 100:
                    heapq.heappush(heap, item)
                elif item[:2] > heap[0][:2]:
                    heapq.heapreplace(heap, item)
        if n % _YIELD_EVERY == _YIELD_EVERY - 1:
            await asyncio.sleep(0)
    rankings = {}
    for key, _ in _FIELDS:
        entries = []
        for sc, _n, d in sorted(heaps[key], key=lambda t: t[:2], reverse=True):
            entry = {'name': public_name(d.get('username'), 'Unnamed hunter'), 'score': str(sc),
                     'id': public_id(uid_of[id(d)])}
            badge = featured_badge(d)
            if badge:
                entry['badge'] = badge
            entries.append(entry)
        rankings[key] = entries
    top_tribes = heapq.nlargest(100, tribes.items(), key=lambda pair: score(pair[1].get('level', 0)))
    rankings['tribes'] = [{'name': public_name(name, 'Unnamed tribe'), 'score': str(score(d.get('level', 0)))} for name, d in top_tribes]
    out = {'rankings': rankings}
    if world:
        out['world'] = world
    return out


class LeaderboardPublisher:
    def __init__(self, users, tribes, world=None):
        self.users, self.tribes = users, tribes
        self.world = world      # callable -> small public dict, or None
        self.task = None
        self.url = ''
        self.token = ''
        self.excluded = set()
        self.send_world = False
        self.connected = False          # last upload got HTTP 200 (shown by the bot's status notifier)
        self.fail_since = 0.0           # when uploads started failing (0 = not failing)

    def start(self):
        if self.task and not self.task.done():
            return
        self.url = os.getenv('LEADERBOARD_URL', '').strip()
        self.token = os.getenv('LEADERBOARD_PUSH_TOKEN', '')
        # The website's /api/leaderboard currently rejects anything but a bare
        # {"rankings": ...} body (HTTP 400 "Expected rankings only") — so the
        # optional `world` field stays off unless the site's been updated to
        # accept it too. Flip LEADERBOARD_SEND_WORLD=1 once it has.
        self.send_world = os.getenv('LEADERBOARD_SEND_WORLD', '').strip().lower() in ('1', 'true', 'yes')
        if not self.url or not self.token:
            log.warning('Leaderboard sync disabled: add LEADERBOARD_URL and LEADERBOARD_PUSH_TOKEN to token.env.')
            return
        parsed = parse.urlsplit(self.url)
        if parsed.scheme != 'https' or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path.rstrip('/') != '/api/leaderboard':
            log.warning('Leaderboard sync disabled: use https://YOUR-SERVICE.onrender.com/api/leaderboard.')
            return
        if len(self.token) < 32 or not self.token.isascii():
            log.warning('Leaderboard sync disabled: the private push token must be at least 32 ASCII characters.')
            return
        self.excluded = {s.strip() for s in os.getenv('LEADERBOARD_EXCLUDE_IDS', '').split(',') if s.strip()}
        self.task = asyncio.create_task(self._run(), name='website-leaderboard-push')

    def _send(self, payload):
        req = request.Request(self.url, data=json.dumps(payload).encode('utf-8'), method='POST', headers={'Content-Type':'application/json', 'Authorization':'Bearer '+self.token})
        try:
            with request.build_opener(NoRedirect()).open(req, timeout=25) as response:
                return response.status, ''
        except error.HTTPError as exc:
            # The response body here is the receiving server's own error text
            # (e.g. "missing field X"), not user data — safe to surface for
            # diagnosis, but still redact the token in case it gets echoed
            # back and cap the length so a noisy server can't flood the log.
            detail = ''
            try:
                detail = exc.read(500).decode('utf-8', 'replace')
                detail = ' '.join(detail.replace(self.token, '[redacted]').split())[:200]
            except Exception:
                pass
            return exc.code, detail

    async def _run(self):
        announced = False
        while True:
            try:
                users = self.users()
                # TESTER accounts are maxed for testing — build_payload skips them
                # (is_tester) alongside the operator's LEADERBOARD_EXCLUDE_IDS.
                excluded = self.excluded
                world = None
                if self.world and self.send_world:
                    try:
                        world = self.world()
                    except Exception:
                        world = None
                payload = await build_payload(users, self.tribes(), excluded, world)
                result, detail = await asyncio.to_thread(self._send, payload)
                if result == 200:
                    if not announced:
                        log.warning('Website leaderboard connected; public rankings update every 60 seconds.')
                    announced = True
                    self.connected, self.fail_since = True, 0.0
                else:
                    log.warning('Leaderboard upload returned HTTP %s%s; retrying in 60 seconds.',
                                 result, f' — {detail}' if detail else '')
                    announced = False
                    self.connected = False
                    self.fail_since = self.fail_since or time.time()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning('Leaderboard upload failed (%s); retrying in 60 seconds.', type(exc).__name__)
                announced = False
                self.connected = False
                self.fail_since = self.fail_since or time.time()
            await asyncio.sleep(60)

    async def stop(self):
        if self.task:
            self.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.task
            self.task = None


# ─────────────────────────────────────────────
# Website changelog
# ─────────────────────────────────────────────
# The in-game update log (/update) is the single source of truth; every entry has a
# version "YY.MM.DD.N" (UTC date + that day's Nth update). This publishes the whole
# log, newest first, to the same site that receives the leaderboards.

_CUSTOM_EMOJI = re.compile(r'<a?:(\w+):\d+>')
_USER_MENTION = re.compile(r'<@[!&]?\d+>')
_CHANNEL_MENTION = re.compile(r'<#\d+>')
_TIMESTAMP = re.compile(r'<t:(-?\d+)(?::[a-zA-Z])?>')


def web_text(value, limit):
    """Discord markup -> plain-ish markdown a website can show. No user ids leak."""
    text = str(value or '')
    text = _CUSTOM_EMOJI.sub(lambda m: f':{m.group(1)}:', text)
    text = _USER_MENTION.sub('@someone', text)
    text = _CHANNEL_MENTION.sub('#channel', text)
    def _ts(m):
        try:
            return datetime.fromtimestamp(int(m.group(1)), timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
        except (ValueError, OverflowError, OSError):
            return ''
    text = _TIMESTAMP.sub(_ts, text)
    return ''.join(c for c in text if c == '\n' or ord(c) >= 32).strip()[:limit]


def build_changelog_payload(entries):
    """{'changelog': [...]} newest first. Public fields only — never the
    moderator id. Entries without a version are skipped (the bot stamps them)."""
    out = []
    for u in entries:
        version = str(u.get('version') or '').strip()
        title = web_text(u.get('title'), 200)
        message = web_text(u.get('message'), 4000)
        if not version or not (title or message):
            continue
        try:
            ts = int(u.get('date') or 0)
        except (TypeError, ValueError):
            ts = 0
        out.append({
            'version': version,
            'title': title,
            'message': message,
            'date': ts,
            'date_iso': datetime.fromtimestamp(ts, timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ') if ts else '',
        })
    # Version strings sort as dates + counter; sort on the numeric parts, newest first.
    def _key(e):
        return tuple(int(p) if p.isdigit() else 0 for p in e['version'].split('.'))
    out.sort(key=_key, reverse=True)
    return {'changelog': out}


class ChangelogPublisher:
    """Pushes the versioned update log to <site>/api/changelog (override with
    CHANGELOG_URL) using the same private token as the leaderboard. Posts when the
    log changes and re-posts every 30 min so a site that lost its data recovers."""
    REFRESH_S = 1800

    def __init__(self, entries):
        self.entries = entries      # callable -> list of update-log dicts
        self.task = None
        self.url = ''
        self.token = ''
        self.connected = False          # last upload got HTTP 200 (shown by the bot's status notifier)
        self.unsupported = 0            # HTTP 404/405/501 from the site = it has no such endpoint yet

    def start(self):
        if self.task and not self.task.done():
            return
        token = os.getenv('LEADERBOARD_PUSH_TOKEN', '')
        url = os.getenv('CHANGELOG_URL', '').strip()
        if not url:
            base = os.getenv('LEADERBOARD_URL', '').strip()
            if base.rstrip('/').endswith('/api/leaderboard'):
                url = base.rstrip('/')[:-len('/api/leaderboard')] + '/api/changelog'
        if not url or not token:
            log.warning('Website changelog disabled: add LEADERBOARD_URL (or CHANGELOG_URL) and LEADERBOARD_PUSH_TOKEN to token.env.')
            return
        parsed = parse.urlsplit(url)
        if parsed.scheme != 'https' or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path.rstrip('/') != '/api/changelog':
            log.warning('Website changelog disabled: use https://YOUR-SERVICE.onrender.com/api/changelog.')
            return
        if len(token) < 32 or not token.isascii():
            log.warning('Website changelog disabled: the private push token must be at least 32 ASCII characters.')
            return
        self.url, self.token = url, token
        self.task = asyncio.create_task(self._run(), name='website-changelog-push')

    def _send(self, payload):
        req = request.Request(self.url, data=json.dumps(payload).encode('utf-8'), method='POST',
                              headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + self.token})
        try:
            with request.build_opener(NoRedirect()).open(req, timeout=25) as response:
                return response.status, ''
        except error.HTTPError as exc:
            detail = ''
            try:
                detail = ' '.join(exc.read(500).decode('utf-8', 'replace').replace(self.token, '[redacted]').split())[:200]
            except Exception:
                pass
            return exc.code, detail

    async def _run(self):
        last_hash, last_ok, warned = '', 0.0, False
        loop = asyncio.get_running_loop()
        while True:
            wait = 60
            try:
                payload = build_changelog_payload(list(self.entries()))
                digest = json.dumps(payload, sort_keys=True)
                if digest != last_hash or loop.time() - last_ok >= self.REFRESH_S:
                    status, detail = await asyncio.to_thread(self._send, payload)
                    if status == 200:
                        if not last_hash:
                            log.warning('Website changelog connected (%d entries).', len(payload['changelog']))
                        last_hash, last_ok, warned = digest, loop.time(), False
                        self.connected = True
                        self.unsupported = 0
                    elif status in (404, 405, 501):
                        self.connected = False
                        self.unsupported = status      # the site just hasn't built the endpoint yet
                        if not warned:
                            log.warning('The website has no /api/changelog endpoint yet (HTTP %s); retrying hourly.', status)
                        warned, wait = True, 3600
                    else:
                        self.connected = False
                        log.warning('Changelog upload returned HTTP %s%s; retrying.', status, f' — {detail}' if detail else '')
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.connected = False
                log.warning('Changelog upload failed (%s); retrying.', type(exc).__name__)
            await asyncio.sleep(wait)

    async def stop(self):
        if self.task:
            self.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.task
            self.task = None
