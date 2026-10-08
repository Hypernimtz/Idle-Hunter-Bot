# Website changelog endpoint + bot environment variables

## 1. The website needs `POST /api/changelog`

The bot already pushes the versioned update log to `<site>/api/changelog` (same host and bearer token as
`/api/leaderboard`). If the site answers **HTTP 404 / 405 / 501** the bot logs
`The website has no /api/changelog endpoint yet … retrying hourly` and keeps going — nothing is broken, the page just
doesn't exist yet. (405 = the route exists but doesn't accept POST; a static file or a GET-only route at that path
causes it.)

**Request** — `POST /api/changelog`, `Authorization: Bearer <LEADERBOARD_PUSH_TOKEN>`, JSON body, sent when the log
changes and again every 30 minutes (so a site that restarts and loses its data recovers by itself):

```json
{"changelog": [
  {"version": "26.10.07.2", "title": "…", "message": "markdown text", "date": 1790000000, "date_iso": "2026-10-07T18:00:00Z"}
]}
```

Newest first, every entry has a version (`YY.MM.DD.N`). No user IDs are ever included. Reply **200** with any body.

### Express (Node)
```js
let changelog = [];                                   // or persist it to a DB/file — Render's disk resets on deploy
app.post('/api/changelog', express.json({ limit: '2mb' }), (req, res) => {
  const auth = req.get('authorization') || '';
  if (auth !== `Bearer ${process.env.LEADERBOARD_PUSH_TOKEN}`) return res.sendStatus(401);
  if (!Array.isArray(req.body?.changelog)) return res.status(400).send('Expected changelog array');
  changelog = req.body.changelog;
  res.sendStatus(200);
});
app.get('/api/changelog', (req, res) => res.json({ changelog }));   // the page reads this
```

### Flask (Python)
```python
CHANGELOG = []
@app.post("/api/changelog")
def push_changelog():
    if request.headers.get("Authorization") != f"Bearer {os.environ['LEADERBOARD_PUSH_TOKEN']}":
        return "", 401
    body = request.get_json(silent=True) or {}
    if not isinstance(body.get("changelog"), list):
        return "Expected changelog array", 400
    CHANGELOG[:] = body["changelog"]
    return "", 200

@app.get("/api/changelog")
def read_changelog():
    return {"changelog": CHANGELOG}
```

The changelog page then renders `GET /api/changelog` (version badge, date, title, markdown message).

## 2. Bot environment variables (`token.env`)

| Variable | What it does |
|---|---|
| `STAFF_GUILD_ID` | Registers `/bot`, `/inspect` and `/updates` to this one server only. Unset = they stay global. If the bot can't reach that server at startup they fall back to global automatically. |
| `STATUS_CHANNEL_ID` | Channel for connection notices (reconnected, connection lost, website down, long-outage boot; plus online/shutting down if `STATUS_NOTIFY_BOOT=1`). Unset = the bot DMs its owner. |
| `STATUS_NOTIFY` | `0` turns the connection notices off. |
| `STATUS_NOTIFY_BOOT` | `1` also sends the routine "online" / "shutting down" notices on every restart or deploy. Off by default; a boot after a 10+ minute outage and real problems (connection lost, website down) are always sent. |
| `LEADERBOARD_URL`, `LEADERBOARD_PUSH_TOKEN` | Website leaderboard push (and, derived from the same URL, the changelog push). |
| `CHANGELOG_URL` | Only if the changelog lives somewhere other than `<LEADERBOARD_URL host>/api/changelog`. |

`/inspect status` (staff) shows the live version of the connection report: Discord, database, website push, staff commands.
