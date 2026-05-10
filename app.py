import discord
from discord.ext import commands

MAINTENANCE_WARNING = {
    "status": False,
    "minutes": 10,
    "reason": "Routine Updates"
}
warned_users = {}

def maintenance_warning(interaction: discord.Interaction):
    if not MAINTENANCE_WARNING["status"]:
        return

    channel_id = interaction.channel_id
    user_id = interaction.user.id
    user_channel_key = (user_id, channel_id)

    if user_channel_key in warned_users:
        return

    embed = discord.Embed(
        title="Maintenance Warning",
        description=f"⚠️ Maintenance incoming in {MAINTENANCE_WARNING['minutes']} minutes. Reason: {MAINTENANCE_WARNING['reason']}",
        color=discord.Color.yellow()
    )

    warned_users[user_channel_key] = True
    return interaction.response.send_message(embed=embed, ephemeral=True)

# Example integration in command logic
class MyBot(commands.Bot):
    async def on_interaction(self, interaction: discord.Interaction):
        maintenance_warning(interaction)
        await super().on_interaction(interaction)