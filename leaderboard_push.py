"""Small optional background publisher. No tokens or private user records are exported."""
import asyncio
import contextlib
import heapq
import json
import logging
import os
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


def build_payload(users, tribes, excluded=(), world=None):
    # Called on the Discord event loop without awaits, so no cross-thread access
    # to mutable bot state. Only this detached minimal payload goes to a thread.
    rankings = {}
    fields = [
        ('level', 'level'), ('money', 'money'), ('prestige', 'prestige'),
        ('caught', 'total_caught'),
        # Idle Hunter V2 — exploration-flavoured boards
        ('myths', 'stats.myths_killed'),
        ('tracking', 'stats.tracks_completed'),
        ('regions', 'regions'),
    ]
    for key, field in fields:
        candidates = ((uid, record) for uid, record in users.items() if str(uid) not in excluded)
        top = heapq.nlargest(100, candidates, key=lambda pair: score(_stat(pair[1], field)))
        entries = []
        for _, d in top:
            entry = {'name': public_name(d.get('username'), 'Unnamed hunter'),
                     'score': str(score(_stat(d, field)))}
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
                # TESTER accounts are maxed for testing — never publish them.
                excluded = self.excluded | {
                    str(uid) for uid, d in users.items() if d.get('is_tester')
                }
                world = None
                if self.world and self.send_world:
                    try:
                        world = self.world()
                    except Exception:
                        world = None
                payload = build_payload(users, self.tribes(), excluded, world)
                result, detail = await asyncio.to_thread(self._send, payload)
                if result == 200:
                    if not announced:
                        log.warning('Website leaderboard connected; public rankings update every 60 seconds.')
                    announced = True
                else:
                    log.warning('Leaderboard upload returned HTTP %s%s; retrying in 60 seconds.',
                                 result, f' — {detail}' if detail else '')
                    announced = False
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning('Leaderboard upload failed (%s); retrying in 60 seconds.', type(exc).__name__)
                announced = False
            await asyncio.sleep(60)

    async def stop(self):
        if self.task:
            self.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.task
            self.task = None
