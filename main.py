import discord
from discord.ext import commands
from discord import app_commands
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from discord.ui import View, Button
import time
from datetime import datetime, timedelta
from flask import Flask
from threading import Thread
import os

# Google Sheets Setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_json = json.loads(os.environ["GOOGLE_CREDS"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
client = gspread.authorize(creds)
sheet = client.open("SCP Points Log").sheet1
activity_sheet = client.open("SCP Points Log").worksheet("Deployments")
morph_sheet = client.open("SCP Points Log").worksheet("Morphs")

# Constants
POINTS_LOG_CHANNEL_ID = 1387710159446474895
AUDIT_LOG_CHANNEL_ID = 1387713963550314577
ALLOWED_USERS = [1293609488833581099, 865864826236305418, 567108786033262595, 534854012328214559, 720535646871093268, 529933806170275856, 957994640093626408, 709213547527405690, 728405079572480031, 961232571256164383, 1114079619000303667, 719909192000864398, 619726723914661888, 851069327268380683, 936577360432619540, 1114079619000303667]
GUILD_ID = 995723132478427267

# Bot Setup
OWNER_ID = 719909192000864398
intents = discord.Intents.all()
bot = commands.Bot(command_prefix=commands.when_mentioned_or("d!"), intents=intents)

deployment_tracker = {}

# Utility Functions

def is_allowed(interaction):
    return interaction.user.id in ALLOWED_USERS

def get_points(discord_id):
    records = sheet.get_all_records()
    for i, row in enumerate(records, start=2):
        if str(row['Discord ID']) == str(discord_id):
            return int(row['Points'])
    return 0

def update_points(discord_id, discord_tag, points_to_add):
    records = sheet.get_all_records()
    for i, row in enumerate(records, start=2):
        if str(row['Discord ID']) == str(discord_id):
            new_points = int(row['Points']) + points_to_add
            sheet.update_cell(i, 3, new_points)
            return new_points
    sheet.append_row([str(discord_id), discord_tag, points_to_add])
    return points_to_add

def remove_points(discord_id, points_to_remove):
    records = sheet.get_all_records()
    for i, row in enumerate(records, start=2):
        if str(row['Discord ID']) == str(discord_id):
            new_points = max(0, int(row['Points']) - points_to_remove)
            sheet.update_cell(i, 3, new_points)
            return new_points

def save_morph_to_sheet(user_id, username, morph):
    records = morph_sheet.get_all_records()
    for i, row in enumerate(records, start=2):
        if str(row['Discord ID']) == str(user_id):
            morph_sheet.update_cell(i, 3, morph)
            return
    morph_sheet.append_row([str(user_id), username, morph])

def get_morph_from_sheet(user_id):
    records = morph_sheet.get_all_records()
    for row in records:
        if str(row['Discord ID']) == str(user_id):
            return row['Morph']
    return None

@bot.event
async def on_ready():
    print("✅ Bot is starting...")
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    try:
        bot.tree.copy_global_to(guild=discord.Object(id=GUILD_ID))
        synced = await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        print(f"✅ Synced {len(synced)} slash commands to guild {GUILD_ID}")
    except Exception as e:
        print(f"❌ Sync failed: {e}")


@app_commands.guilds(discord.Object(id=GUILD_ID))
@bot.tree.command(name="cmds", description="List all commands")
async def cmds(interaction: discord.Interaction):
    commands_list = """
    **📜 Command List:**
    `/pointsadd` - Add points
    `/pointsremove` - Remove points
    `/points` - Check user points
    `/leaderboard` - Show leaderboard
    `/startdeploy` - Start deployment timer
    `/stopdeploy` - Stop deployment timer
    `/deploylog` - View deployment logs
    `/cleardeploy` - Clear a user's deployment logs
    `/kick` - Kick a user
    `/ban` - Ban a user
    `/timeout` - Timeout a user
    `/purge` - Purge messages
    `/savemorph` - Save morph
    `/morph` - Get your saved morph
    `/lockdown` - Lock a channel
    `/unlock` - Unlock a channel
    """
    await interaction.response.send_message(commands_list)

@app_commands.guilds(discord.Object(id=GUILD_ID))
@bot.tree.command(name="pointsadd", description="Add points to a user")
async def pointsadd(interaction: discord.Interaction, user: discord.User, amount: int):
    if not is_allowed(interaction):
        await interaction.response.send_message("❌ You do not have permission to use this command.", ephemeral=True)
        return
    total = update_points(user.id, user.name, amount)
    await interaction.response.send_message(f"✅ {amount} points added to {user.name}. Total: {total}", ephemeral=True)
    log_channel = bot.get_channel(POINTS_LOG_CHANNEL_ID)
    if log_channel:
        await log_channel.send(f"{amount} awarded to {user.mention}. Total points: {total}.")

@app_commands.guilds(discord.Object(id=GUILD_ID))
@bot.tree.command(name="pointsremove", description="Remove points from a user")
async def pointsremove(interaction: discord.Interaction, user: discord.User, amount: int):
    if not is_allowed(interaction):
        await interaction.response.send_message("❌ You do not have permission to use this command.", ephemeral=True)
        return
    total = remove_points(user.id, amount)
    await interaction.response.send_message(f"✅ {amount} points removed from {user.name}. Total: {total}", ephemeral=True)
    log_channel = bot.get_channel(POINTS_LOG_CHANNEL_ID)
    if log_channel:
        await log_channel.send(f"{amount} points removed from {user.mention}. Total points: {total}.")

@app_commands.guilds(discord.Object(id=GUILD_ID))
@bot.tree.command(name="points", description="Check your points")
async def points(interaction: discord.Interaction, user: discord.Member):
    total = get_points(user.id)
    await interaction.response.send_message(f"{user.mention} has {total} points.", ephemeral=False)

@app_commands.guilds(discord.Object(id=GUILD_ID))
@bot.tree.command(name="leaderboard", description="Show top point holders")
async def leaderboard(interaction: discord.Interaction):
    try:
        all_data = sheet.get_all_records()
        sorted_data = sorted(all_data, key=lambda x: x['Points'], reverse=True)
        embed = discord.Embed(title="📊 Leaderboard", color=discord.Color.gold())
        for i, row in enumerate(sorted_data[:10], start=1):
            embed.add_field(name=f"{i}.", value=f"<@{row['Discord ID']}> - {row['Points']} points", inline=False)
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error loading leaderboard: {e}")

@app_commands.guilds(discord.Object(id=GUILD_ID))
@bot.tree.command(name="startdeploy", description="Start deployment timer")
async def startdeploy(interaction: discord.Interaction):
    deployment_tracker[interaction.user.id] = time.time()
    await interaction.response.send_message(f"⏱️ Deployment started for {interaction.user.mention}.")

@app_commands.guilds(discord.Object(id=GUILD_ID))
@bot.tree.command(name="stopdeploy", description="Stop deployment timer")
async def stopdeploy(interaction: discord.Interaction):
    if interaction.user.id not in deployment_tracker:
        await interaction.response.send_message("❌ No deployment started.")
        return
    start_time = deployment_tracker.pop(interaction.user.id)
    duration = round((time.time() - start_time) / 60, 2)
    activity_sheet.append_row([str(interaction.user.id), interaction.user.name, f"{duration} minutes"])
    await interaction.response.send_message(f"✅ Deployment ended. Duration: {duration} minutes.")

@app_commands.guilds(discord.Object(id=GUILD_ID))
@bot.tree.command(name="deploylog", description="Show deployment log")
async def deploylog(interaction: discord.Interaction, user: discord.User = None):
    target = user or interaction.user
    logs = activity_sheet.get_all_records()
    message = f"Deployment Logs for {target.name}:\n"
    for row in logs:
        if str(row['Discord ID']) == str(target.id):
            message += f"- {row['Deployment Time']}\n"
    await interaction.response.send_message(message)

@app_commands.guilds(discord.Object(id=GUILD_ID))
@bot.tree.command(name="cleardeploy", description="Clear a user's deployment logs")
async def cleardeploy(interaction: discord.Interaction, user: discord.User):
    if not is_allowed(interaction):
        await interaction.response.send_message("Ask a HR or HICOM to do ts for u", ephemeral=True)
        return
    records = activity_sheet.get_all_records()
    updated = [row for row in records if str(row['Discord ID']) != str(user.id)]
    activity_sheet.clear()
    activity_sheet.append_row(["Discord ID", "Name", "Deployment Time"])
    for row in updated:
        activity_sheet.append_row([row['Discord ID'], row['Name'], row['Deployment Time']])
    await interaction.response.send_message(f"{user.name}'s deployment logs has been wiped'.")

#MODERATION
@app_commands.guilds(discord.Object(id=GUILD_ID))
@bot.tree.command(name="kick", description="Kick a user")
async def kick(interaction: discord.Interaction, user: discord.Member, reason: str):
    if not is_allowed(interaction):
        await interaction.response.send_message("why ru trying to kick someone bro ur not HR+.", ephemeral=True)
        return
    await user.kick(reason=reason)
    await interaction.response.send_message(f"{user.name} has been kicked. Reason: {reason}")

@app_commands.guilds(discord.Object(id=GUILD_ID))
@bot.tree.command(name="ban", description="Ban a user")
async def ban(interaction: discord.Interaction, user: discord.Member, reason: str):
    if not is_allowed(interaction):
        await interaction.response.send_message("Ur not special bro u dont got permission for ts", ephemeral=True)
        return
    await user.ban(reason=reason)
    await interaction.response.send_message(f"🔨 {user.name} has been banned. Reason: {reason}")

@app_commands.guilds(discord.Object(id=GUILD_ID))
@bot.tree.command(name="timeout", description="Timeout a member")
@app_commands.describe(member="Member to timeout", minutes="Duration in minutes")
async def timeout(interaction: discord.Interaction, member: discord.Member, minutes: int):
    duration = timedelta(minutes=minutes)
    await member.timeout(duration)
    await interaction.response.send_message(f"⏳ {member.mention} has been timed out for {minutes} minutes.")

@app_commands.guilds(discord.Object(id=GUILD_ID))
@bot.tree.command(name="purge", description="Delete a number of messages")
@app_commands.describe(amount="Number of messages to delete")
async def purge(interaction: discord.Interaction, amount: int):
    await interaction.channel.purge(limit=amount)
    await interaction.response.send_message(f"🧹 Deleted {amount} messages.", ephemeral=True)
    log_channel = bot.get_channel(AUDIT_LOG_CHANNEL_ID)
    await log_channel.send(f"🧹 {interaction.user.mention} purged {amount} messages in {interaction.channel.mention}")

# MORPHS
@app_commands.guilds(discord.Object(id=GUILD_ID))
@bot.tree.command(name="savemorph", description="Save your morph settings")
async def savemorph(interaction: discord.Interaction, morph: str):
    user_id = str(interaction.user.id)
    username = str(interaction.user.name)
    formatted_morph = morph.replace("\\n", "\n")
    data = morph_sheet.get_all_records()
    for i, row in enumerate(data, start=2):
        if str(row['UserID']) == user_id:
            morph_sheet.update_cell(i, 3, formatted_morph)
            await interaction.response.send_message("Ok nice saved")
            return
    morph_sheet.append_row([username, user_id, formatted_morph])
    await interaction.response.send_message("✅ Morph saved.")


@app_commands.guilds(discord.Object(id=GUILD_ID))
@bot.tree.command(name="unban", description="Unban a user")
@app_commands.describe(user_id="ID of the user to unban")
async def unban(interaction: discord.Interaction, user_id: int):
    user = await bot.fetch_user(user_id)
    await interaction.guild.unban(user)
    await interaction.response.send_message(f"✅ Unbanned {user.mention}.")

@app_commands.guilds(discord.Object(id=GUILD_ID))
@bot.tree.command(name="untimeout", description="Remove timeout from a member")
async def untimeout(interaction: discord.Interaction, member: discord.Member):
    await member.timeout(None)
    await interaction.response.send_message(f"✅ Timeout removed from {member.mention}.")

@app_commands.guilds(discord.Object(id=GUILD_ID))
@bot.tree.command(name="morph", description="Retrieve your saved morph")
async def morph(interaction: discord.Interaction, user: discord.Member = None):
    target = user or interaction.user
    data = morph_sheet.get_all_records()
    for row in data:
        if str(row['UserID']) == str(target.id):
            try:
                raw_morph = row['Morph']
                formatted = raw_morph.replace(" :", "\n:")
                await target.send(f"Your morph:\n{formatted}")

                await interaction.response.send_message("Check ur dms bro.", ephemeral=True)
            except:
                await interaction.response.send_message("Ur dms are off dumbass.", ephemeral=True)
            return
    await interaction.response.send_message("❌ No morph saved.", ephemeral=True)

# LOCKDOWN
@app_commands.guilds(discord.Object(id=GUILD_ID))
@bot.tree.command(name="lockdown", description="Lock a channel")
async def lockdown(interaction: discord.Interaction):
    if not is_allowed(interaction):
        await interaction.response.send_message("Sybau bro u dont have permission.", ephemeral=True)
        return
    overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
    overwrite.send_messages = False
    await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
    await interaction.response.send_message("🔒 Channel has been locked.")

@app_commands.guilds(discord.Object(id=GUILD_ID))
@bot.tree.command(name="unlock", description="Unlock a channel")
async def unlock(interaction: discord.Interaction):
    if not is_allowed(interaction):
        await interaction.response.send_message("u dont have perms.", ephemeral=True)
        return
    overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
    overwrite.send_messages = True
    await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
    await interaction.response.send_message("🔓 Channel has been unlocked.")

@app_commands.guilds(discord.Object(id=GUILD_ID))
@bot.tree.command(name="g", description="Send a message to #general-chat")
@app_commands.describe(message="The message to send")
async def g(interaction: discord.Interaction, message: str):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("❌ You do not have permission to use this command.", ephemeral=True)
        return
    channel = bot.get_channel(1248647511913136179)
    await channel.send(message)
    await interaction.response.send_message("✅ Sent to #general-chat.", ephemeral=True)

@app_commands.guilds(discord.Object(id=GUILD_ID))
@bot.tree.command(name="n", description="Send a message to #major-news")
@app_commands.describe(message="The message to send")
async def n(interaction: discord.Interaction, message: str):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("❌ You do not have permission to use this command.", ephemeral=True)
        return
    channel = bot.get_channel(1309756493314261072)
    await channel.send(message)
    await interaction.response.send_message("✅ Sent to #major-news.", ephemeral=True)

# Flask app for keeping the bot alive
app = Flask('')

@app.route('/')
def home():
    return "I'm alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# keep alive and run the bot

keep_alive()
bot.run(os.run[DISCORD_BOT_TOKEN])
