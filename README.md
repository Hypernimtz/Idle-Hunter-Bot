# Idle-Hunter
🌲 Idle Hunter

Hunt smarter. Earn always. Click when you can, earn while you can't.

Idle Hunter is a Discord bot that brings an idle clicker hunting game to your server. Track prey, collect loot, level up your hunter, and unlock new abilities — all from within Discord.

🎮 Features

🏹 Click to Hunt — Actively hunt prey for instant rewards
💰 Idle Earnings — Earn loot even while you're offline
🎚️ Leveling System — Unlock new buttons, abilities, and hunts as you level up
🎨 Dynamic Embeds — Color-coded embeds that reflect your hunter status
🔒 Level-Gated Actions — Some actions are locked until you reach the required level
🖱️ Interactive Buttons — All actions are handled through Discord UI buttons


🚀 Getting Started
Prerequisites

Python 3.10+
A Discord Bot Token (Discord Developer Portal)
discord.py library

Installation
bash# Clone the repository
git clone https://github.com/yourusername/idle-hunter.git
cd idle-hunter

# Install dependencies
pip install -r requirements.txt

# Add your bot token
cp .env.example .env
# Edit .env and add your DISCORD_TOKEN
Running the Bot
bashpython bot.py

🛠️ Tech Stack

Language: Python 3.10+
Library: discord.py
UI: Discord Message Components (Buttons, Embeds)


🎮 Commands
CommandDescription! /hunt Opens the Hunt menu with interactive buttons!

📁 Project Structure
idle-hunter/
├── bot.py           # Main bot entry point
├── views/
│   └── hunt_view.py # HuntView class with all buttons
├── utils/
│   └── colors.py    # COLORS dictionary
├── requirements.txt
└── .env.example

🧩 Example: HuntView
pythonclass HuntView(discord.ui.View):
    def __init__(self, user_level):
        super().__init__()
        self.user_level = user_level

        if user_level < 5:
            self.collect_loot.disabled = True

    @discord.ui.button(label="🏹 Hunt", style=discord.ButtonStyle.primary)
    async def hunt(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🦌 You went hunting!")

    @discord.ui.button(label="💰 Collect Loot", style=discord.ButtonStyle.success)
    async def collect_loot(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("💰 Loot collected!")

🗺️ Roadmap

 Persistent player data (database integration)
 Rare and legendary prey
 Crafting system
 Multiplayer hunting parties
 Seasonal events


🤝 Contributing
Pull requests are welcome! For major changes, please open an issue first to discuss what you'd like to change.

Fork the repo
Create your feature branch (git checkout -b feature/my-feature)
Commit your changes (git commit -m 'Add my feature')
Push to the branch (git push origin feature/my-feature)
Open a Pull Request


📄 License
This project is licensed under the MIT License — see the LICENSE file for details.

Built with 🐍 Python and ❤️ for the Discord community.
