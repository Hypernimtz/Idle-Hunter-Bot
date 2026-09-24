# 🏹 Idle Hunter

*Hunt always; Grind always; Idle never — wait, that's impossible!*

Idle Hunter puts you in the wild: click to hunt and grind your way to legendary prey. Step away and let your hired hunters do the work — come back to loot, level up, and dive back in.

Start your hunting journey with any command and a detailed tutorial!

---

## 🌿 Features

- **Hunting** — Hunt animals across 13 unique biomes, from the humble Village to the divine Celestial Peaks
- **Tools & Ammo** — 20 tools across 20 tiers, each with compatible ammo types that boost your Luck, Sell price, and XP
- **Idle Income** — Hire workers that earn ◈ passively while you're away; stack them for massive returns
- **Biomes** — Unlock new biomes as you level up, each with rarer animals and higher payouts
- **Tribes** — Join or create a tribe to share Luck, Sell, and XP boosts with your crew
- **Prestige** — Reset at Level 1,000 for a permanent +20% boost to everything. Repeat.
- **Daily Rewards** — Claim free ◈ or 💎 every day and build your streak for a bonus multiplier
- **Leaderboards** — Global and server-scoped rankings for Level, Money, Animals Caught, and Prestige
- **Achievements & Badges** — Track milestones, earn titles, and flex your Gold and Platinum badges
- **Gambling** — Coinflip, Slots, Blackjack, Roulette, and Rock Paper Scissors
- **Lottery** — Buy tickets daily for a chance at the prize pool
- **Gifts** — Send ◈ or 💎 to other hunters with a personal message
- **Vehicles** — Reduce your hunt cooldown with upgradeable vehicles
- **Colors** — Customize your panel accent color; unlock custom hex at Level 1,200

---

## 🚀 Getting Started

Invite the bot to your server or install it as a user app, then run any command to begin. A tutorial will walk you through the basics automatically.

| Command | Description |
|---|---|
| `/menu` | Open the main hub — everything in one place |
| `/hunt` | Go hunting in your current biome |
| `/shop` | Buy boosts, tools, ammo, and vehicles |
| `/biome` | Switch your hunting biome |
| `/equip` | Equip your tools, ammo, and vehicle |
| `/idle` | Manage your idle workers |
| `/daily` | Claim your daily reward |
| `/tribe` | View or manage your tribe |
| `/prestige` | Reset for a permanent boost multiplier |
| `/profile` | View your profile and statistics |
| `/leaderboard` | View global rankings |
| `/gamble` | Try your luck at mini-games |
| `/lottery` | Buy tickets for the daily draw |
| `/gift` | Send money or gems to another player |
| `/record` | View your catch record book |
| `/log` | View your recent hunt history |
| `/progression` | View your achievements, badges, and titles |
| `/update` | View the latest developer updates |
| `/rules` | View the server rules |
| `/tutorial` | Turn tutorial tips on or off |
| `/verify` | Complete a verification check |
| `/suggest` | Send a suggestion to the developers |
| `/report` | Report a user or a bug |
| `/invite` | Invite Idle Hunter to your server |
| `/help` | View all available commands |

*More commands are coming soon!

---

## ⚙️ Self-Hosting

### Requirements

- Python 3.12+
- A Discord bot token with `bot` and `applications.commands` scopes
- The following packages:
    discord.py
    aiosqlite
    requests
    python-dotenv
  
  Install with:
  ```bash
  pip install discord.py aiosqlite python-dotenv requests
  ```

### Setup

1. Clone the repository
2. Create a `token.env` file:
     TOKEN=your_bot_token_here_in_string
3. If migrating from JSON, place your `users_info.json` and `tribe_info.json` in the root directory — they will be imported automatically on first boot
4. Run the bot:
```bash
python app.py
```

The database (`idle_hunter.db`) is created automatically on first run. Data is saved every 20 seconds via autosave.

---

## 🗄️ Data & Storage

| File | Purpose |
|---|---|
| `idle_hunter.db` | Main SQLite database — all user and tribe data |
| `config.json` | Maintenance settings, dev mail, and update log |
| `lottery.json` | Current lottery pool, tickets, and last winner |
| `token.env` | Bot token — never commit this |

---

## 📜 Rules

Use `/rules` in Discord to view the full list of rules. Key points:

- No autoclickers, bots, or automation
- No exploiting bugs or glitches
- No real money trading
- No harassment or impersonation
- Follow Discord's Terms of Service at all times

---

## 🤝 Support

Join the support server for help, updates, and to see lottery winners:
[discord.gg/X9JzdxeS8p](https://discord.gg/X9JzdxeS8p)

---

*© Idle Hunter — All rights reserved.*
