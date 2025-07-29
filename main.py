import discord
from discord import Interaction, User
from discord.ext import commands
from discord import app_commands
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from discord.ui import View, Button
import time
from datetime import datetime, timedelta, timezone
from flask import Flask
from threading import Thread
import os
import json
import re
import typing
from typing import Optional
import random
import math

# Google Sheets Setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_json = json.loads(os.environ["GOOGLE_CREDS"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
client = gspread.authorize(creds)
sheet = client.open("SCP Points Log").sheet1
activity_sheet = client.open("SCP Points Log").worksheet("Deployments")
log_sheet = client.open("SCP Points Log").worksheet("Logs")

# Constants
POINTS_LOG_CHANNEL_ID = 1387710159446474895
AUDIT_LOG_CHANNEL_ID = 1387713963550314577
ALLOWED_ROLES = [1395018313847013487]
DEPLOYMENT_ROLE = [1395875682810331318]
GUILD_ID = 995723132478427267
EVENTS_CHANNEL_ID = 1309756614387044352
DEPLOYMENTS_LOG_CHANNEL = 1387310947110228070
faction = 'Delta-0 "Livid Night"'

# Bot Setup
OWNER_ID = 719909192000864398
intents = discord.Intents.all()
bot = commands.Bot(command_prefix=commands.when_mentioned_or("d!"), intents=intents)

deployment_tracker = {}
active_deployments = {}

RULES = {
    1:
    "Do not false react to event-checks, i.e Reacting to a deployment message but not showing up at the deployment.",
    2: "Do not speak about unnecessary things.",
    3: "Do not mock or speak badly about allied and/or unallied factions.",
    4: "Spamming is not allowed.",
    5: "Do not ping Rogue unless an emergency.",
    6: "Do not be racist.",
    7:
    "You can be disrespectful in a jokingly manner, as long as you know the consequences.",
    8: "Respect every SCP:RP site staff member.",
    9:
    "DM advertising or advertising is not allowed without consent of the person you are advertising to / or without the consent of Rogue.",
    10:
    "Do not start an irrelevant or inappropriate topic to talk about in any channel.",
    11: "Do not add unnecessary reactions on announcements individually.",
    12: "Refrain from mocking each other.",
    13:
    "Don't date in here, if you intend to do that, dating is only between 2 people. Do it in DM's, the faction has nothing to do with it.",
    14: "Follow Discord TOS: https://discord.com/terms",
    15:
    "Follow Roblox TOS: https://en.help.roblox.com/hc/en-us/articles/115004647846-Roblox-Terms-of-Use",
    69: "Did ur dumbass really think this was a rule?",
    420: "What are you expecting to find here?",
    1917: "Theres 15 fucking rules, why tf are you checking for rule 1917",
    67: "I don't know what the meme is so uh yea",
}

PROTOCOLS = {
    1:
    "Act mature and professional at all times especially in formal situations. Joking should only be permitted when sites are in casual mode, and there should be no inappropriate content or behaviours being shared.",
    2:
    "If you are told to stop a behaviour by a HICOM, CO, or Site-Staff in game, please correct yourself and apologize to whoever was disturbed by the behaviour. Whether that be site-staff, other factions, Delta-0 members, or members of the public.",
    3:
    "Report Misbehaviour in-game to Mika directly as Mika overlooks professionalism and discipline. Do not be shy to reach out even if you are unsure if someone has broken a rule. All reports, serious or not, will be shared to other members of the HICOM team for overviewing.",
    4:
    "Under no circumstance should you mock, bully, behave inappropriately, be racist, sexist, homophobic, hateful, insensitive, offensive, or verbally abusive someone on site. This will NOT be taken lightly. This includes making comments on someone who is provoking you, or towards a person/site.",
    5:
    "If you react to a deployment, you show up. If for any reason you cannot attend, inform the host.",
    6:
    "Do not break in-site rules and use common sense otherwise there will be consequences.",
}

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    content = message.content.lower()

    # Check Rules with regex to match only rule followed by number 1-15
    rule_match = re.search(r"\brule\s*(\d+)\b", content)
    if rule_match:
        rule_num = int(rule_match.group(1))
        if rule_num in RULES:
            await message.channel.send(RULES[rule_num])
            return

    # Check Protocols
    protocol_match = re.search(r"\bprotocol\s*(\d{1,2})\b", content)
    if protocol_match:
        protocol_num = int(protocol_match.group(1))
        if protocol_num in PROTOCOLS:
            await message.channel.send(PROTOCOLS[protocol_num])
            return

    # Other keywords
    if "crazy" in content and random.random() < 0.05: 
        await message.channel.send(
            "Crazy? I was crazy once. They locked me in a room. A rubber room. A rubber room filled with rats. And rats make me crazy.")
        
    if "lupus" in content and random.random() < 0.05:
        lupus_responses = [
            "It's never lupus you absolute dumbfuck.",
            "Still not lupus gang. It's never lupus.",
            "<@510784737800093716> would be disappointed.",
            "Lupus? I had lupus once. They locked me in a room. A room filled with lupus. And lupus makes me lupus.",
            "Gang plz stop im done saying its never lupus.",
        ]
        await message.channel.send(random.choice(lupus_responses))


# Utility Functions

def is_allowed(interaction):
    return any(role.id in ALLOWED_ROLES for role in interaction.user.roles)

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
    **Points**
    `/pointsadd` - Add points
    `/pointsremove` - Remove points
    `/points` - Check user points
    `/leaderboard` - Show leaderboard

    **Deployments**
    `/startdeploy` - Start deployment timer
    `/stopdeploy` - Stop deployment timer
    `/deploylog` - View deployment logs
    `/cleardeploy` - Clear a user's deployment logs

    **Automation**
    `/start` - Start a deployment
    `/end` - End a deployment and log attendees
    Note: Upload proof image in the events channel after /start and before /end
    `/morph` - Automatically does the morph for you

    **Moderation**
    `/kick` - Kick a user
    `/ban` - Ban a user
    `/syfm` - Shuts a users fucking mouth
    `/purge` - Purge messages
    `/sybau` - Lock a channel
    `/unlock` - Unlock a channel

    **Misc**
    `/virtus` - Shows Virtus morph channels
    `/416` - Shows 416 morph channels
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

        # Filter out invalid or blank rows
        valid_data = []
        for row in all_data:
            points = row.get('Points')
            discord_id = row.get('Discord ID')

            if not discord_id or not str(points).strip():
                continue  # skip blank rows

            try:
                points = int(points)
                valid_data.append({'Discord ID': discord_id, 'Points': points})
            except ValueError:
                continue  # skip non-numeric points

        # Sort by points
        sorted_data = sorted(valid_data, key=lambda x: x['Points'], reverse=True)

        if not sorted_data:
            await interaction.response.send_message("⚠️ No valid leaderboard data found.", ephemeral=True)
            return

        per_page = 10
        total_pages = math.ceil(len(sorted_data) / per_page)
        current_page = 0

        def get_embed(page):
            start = page * per_page
            end = start + per_page
            page_data = sorted_data[start:end]

            embed = discord.Embed(
                title=f"📊 Leaderboard (Page {page + 1}/{total_pages})",
                color=discord.Color.gold()
            )

            for i, row in enumerate(page_data, start=start + 1):
                embed.add_field(
                    name=f"{i}.",
                    value=f"<@{row['Discord ID']}> — **{row['Points']}** points",
                    inline=False
                )

            return embed

        # View + buttons
        view = View(timeout=60)

        async def update_message(inter, page_change):
            nonlocal current_page
            current_page += page_change
            current_page = max(0, min(current_page, total_pages - 1))

            # Disable buttons appropriately
            prev_button.disabled = current_page == 0
            next_button.disabled = current_page == total_pages - 1

            await inter.response.edit_message(embed=get_embed(current_page), view=view)

        prev_button = Button(label="⬅️ Previous", style=discord.ButtonStyle.primary)
        next_button = Button(label="Next ➡️", style=discord.ButtonStyle.primary)

        prev_button.callback = lambda inter: update_message(inter, -1)
        next_button.callback = lambda inter: update_message(inter, +1)

        # Initial button state
        prev_button.disabled = current_page == 0
        next_button.disabled = total_pages <= 1

        view.add_item(prev_button)
        view.add_item(next_button)

        await interaction.response.send_message(embed=get_embed(current_page), view=view)

    except Exception as e:
        await interaction.response.send_message(f"❌ Error loading leaderboard: `{e}`", ephemeral=True)


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
@bot.tree.command(name="syfm", description="Timeout a member")
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
    await interaction.response.send_message(f"🧹 Deleted {amount} messages.")
    log_channel = bot.get_channel(AUDIT_LOG_CHANNEL_ID)
    await log_channel.send(f"🧹 {interaction.user.mention} purged {amount} messages in {interaction.channel.mention}")

# Deployment Log

@bot.tree.command(name="log", description="Log deployment attendees.")
@app_commands.describe(
    user1="Attendee 1",
    user2="Attendee 2 (optional)",
    user3="Attendee 3 (optional)",
    user4="Attendee 4 (optional)",
    user5="Attendee 5 (optional)"
)
async def log(
    interaction: discord.Interaction,
    user1: discord.Member,
    user2: Optional[discord.Member] = None,
    user3: Optional[discord.Member] = None,
    user4: Optional[discord.Member] = None,
    user5: Optional[discord.Member] = None,
):
    # Role check
    if not any(role.id in DEPLOYMENT_ROLE for role in interaction.user.roles):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return

    attendees = [user1]
    for user in (user2, user3, user4, user5):
        if user is not None:
            attendees.append(user)

    records = log_sheet.get_all_records()
    id_to_row = {str(row["Discord ID"]): (i + 2, row) for i, row in enumerate(records)}  # Google Sheet rows start at 2
    updated_mentions = []

    for member in attendees:
        member_id = str(member.id)
        if member_id in id_to_row:
            row_num, row = id_to_row[member_id]
            current_count = int(row.get("Deployment Count", 0))
            log_sheet.update_cell(row_num, 3, current_count + 1)
        else:
            log_sheet.append_row([member_id, str(member), 1])
        updated_mentions.append(member.mention)

    if updated_mentions:
        await interaction.response.send_message(f"Logged deployment for: {', '.join(updated_mentions)}")
    else:
        await interaction.response.send_message("No valid members found to log.", ephemeral=True)


@bot.tree.command(name="deployments", description="Check deployment count for yourself or another user.")
@app_commands.describe(user="User to check deployment count for (optional)")
async def deployments(interaction: discord.Interaction, user: Optional[discord.Member] = None):
    target = user or interaction.user
    user_id = str(target.id)
    records = log_sheet.get_all_records()

    for row in records:
        if str(row["Discord ID"]) == user_id:
            await interaction.response.send_message(f"{target.mention} has attended **{row['Deployment Count']}** deployments.")
            return

    await interaction.response.send_message(f"{target.mention} has no deployments logged yet.")

@bot.tree.command(name="clearlog", description="Clear a users deployment log.")
@app_commands.describe(user="The user whose deployment log you want to clear.")
async def clearlog(interaction: discord.Interaction, user: discord.Member):
    if not any(role.id in ALLOWED_ROLES for role in interaction.user.roles):
        await interaction.response.send_message("No perms gang", ephemeral=True)
        return

    records = log_sheet.get_all_records()
    for i, row in enumerate(records, start=2):
        if str(row["Discord ID"]) == str(user.id):
            log_sheet.update_cell(i, 3, 0)
            await interaction.response.send_message(f"Cleared deployment log for {user.mention}.")
            return

    await interaction.response.send_message("User not found", ephemeral=True)

# Ban and unban

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

# MISC

@app_commands.guilds(discord.Object(id=GUILD_ID))
@app_commands.guilds(discord.Object(id=GUILD_ID))
@bot.tree.command(name="virtus", description="Access Virtus channels")
async def virtus(interaction: discord.Interaction):
    await interaction.response.send_message(
        "**Virtus Channels:**\n<#1387293873063202958>\n<#1394945387709730868>",)


@app_commands.guilds(discord.Object(id=GUILD_ID))
@bot.tree.command(name="416", description="Access 416 channels")
async def fouronesix(interaction: discord.Interaction):
    await interaction.response.send_message(
        "**416 Channels:**\n<#1394220165926752286>\n<#1394945444936810599>", )

# LOCKDOWN
@app_commands.guilds(discord.Object(id=GUILD_ID))
@bot.tree.command(name="sybau", description="Sybau's a channel")
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
@bot.tree.command(name="e", description="Event")
@app_commands.describe(message="The message to send")
async def g(interaction: discord.Interaction, message: str):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("❌ You do not have permission to use this command.", ephemeral=True)
        return
    channel = bot.get_channel(1309756614387044352)
    await channel.send(message)
    await interaction.response.send_message("✅ Sent to #events.", ephemeral=True)

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

# Deployment Automation

@bot.tree.command(name="start", description="Start a deployment.")
@app_commands.describe(site="Site number", cohost="Mention the co-host")
async def start(interaction: discord.Interaction, site: str, cohost: discord.Member):
    if interaction.channel.id != EVENTS_CHANNEL_ID:
        await interaction.response.send_message("This command can only be used in the events channel.", ephemeral=True)
        return

    active_deployments[interaction.user.id] = {
        "timestamp": datetime.now(timezone.utc),
        "site": site,
        "cohost": cohost
    }

    await interaction.response.send_message(f"Deployment started for Site {site} with Co-host {cohost.mention}.")


@bot.tree.command(name="end", description="End a deployment and log attendee count.")
@app_commands.describe(
    attendee_count="Number of attendees present in the deployment"
)
@app_commands.guild_only()
async def end(
    interaction: Interaction,
    attendee_count: int,
):
    # Check command channel
    if not interaction.channel or interaction.channel.id != EVENTS_CHANNEL_ID:
        await interaction.response.send_message(
            "This command can only be used in the events channel.", ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)

    user_id = interaction.user.id

    if user_id not in active_deployments:
        await interaction.followup.send(
            "You have no active deployment started. Use /start first.", ephemeral=True
        )
        return

    deployment = active_deployments[user_id]
    start_time = deployment["timestamp"]
    site = deployment["site"]
    co_host = deployment["cohost"]

    end_time = datetime.now(timezone.utc)
    duration = end_time - start_time
    total_seconds = int(duration.total_seconds())
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    formatted_duration = f"{minutes} minutes {seconds} seconds"

    channel = interaction.guild.get_channel(interaction.channel.id)
    proof_url = []
    async for message in channel.history(limit=100, after=start_time, oldest_first=True):
        for attachment in message.attachments:
            if attachment.content_type and attachment.content_type.startswith("image/"):
                proof_url.append(attachment.url)

    if len(proof_url) < 2:
        await interaction.followup.send(
            "At least two proof images are required in the deployment channel after /start and before /end.", ephemeral=True
        )
        return

    proof_text = "\n".join(proof_url)

    guild = interaction.guild

    if isinstance(co_host, str):
        co_host_obj = guild.get_member_named(co_host)
        if co_host_obj is None:
            co_host_obj = co_host
    else:
        co_host_obj = co_host

    cohost_text = co_host_obj.mention if hasattr(co_host_obj, "mention") else str(co_host_obj)

    msg = (
        f"**Site:** {site}\n"
        f"**Faction Name:** Delta-0 \"Livid Night\"\n"
        f"**Faction Leader:** <@534854012328214559>\n"
        f"**Host:** {interaction.user.mention}\n"
        f"**Co-host:** {cohost_text}\n"
        f"**Attendees:** {attendee_count}\n"
        f"**Time:** {formatted_duration}\n"
        f"**Proof:**\n{proof_text}"
    )

    log_channel = interaction.guild.get_channel(DEPLOYMENTS_LOG_CHANNEL)
    await log_channel.send(msg)

    del active_deployments[user_id]

    await interaction.followup.send(
        f"Deployment ended and logged with {attendee_count} attendees.",
    )




# Auto morph

morphs = {
    "virtus": {
        "LR": 'run permrtag me <font face="Michroma">Delta-0 "Livid Night" | Rank</font> & permntag me <font face="Fantasy">["Callsign"]</font> & permcrtag me 0 0 0 & permcntag me 149 3 1 & permmorph me remove & permshirt me 14572682166 14572536468 & permhat me 0,JSNVG,Holster,89985831397392,17172715247,17330407522,Kneepads,13770147630,16755421666,4507911797,118325759243,18325759243,17430938152,15893925206,17558966643,12383357842 & startergear me mpx,glock & permmaxhealth me 110 & heal me',
        "MR": 'run permrtag me <font face="Michroma">Delta-0 "Livid Night" | Rank</font> & permntag me <font face="Fantasy">["Callsign"]</font> & permcrtag me 0 0 0 & permcntag me 149 3 1 & permmorph me remove & permshirt me 14572682166 14572536468 & permhat me 0,JSNVG,Holster,89985831397392,17172715247,17330407522,Kneepads,13770147630,16755421666,4507911797,118325759243,18325759243,17430938152,15893925206,17558966643,12383357842 & startergear me mpx,glock & permmaxhealth me 110 & heal me',
        "HR": 'run permrtag me <font face="Michroma">Delta-0 "Livid Night" | Rank</font> & permntag me <font face="Fantasy">["Callsign"]</font> & permcrtag me 0 0 0 & permcntag me 139 0 0 & permmorph me remove & permshirt me 14572682166 14572536468 & permhat me 0,JNVG,Holster,89985831397392,17172715247,17330407522,Kneepads,13770147630,16270371844,4507911797,118325759243,8087415055,17430938152,15893925206,12497812780,12497817183,17558966643 & permhat me 12383357842 & startergear me hk,glock & permmaxhealth me 120 & heal me',
    },
    "416": {
        "LR": 'run permrtag me <font face="Michroma">Delta-0 "Livid Night" | Rank</font> & permcrtag me 4 2 115 & permmorph me remove & permshirt me 14572682166 14572536468 & permhat me 0,JSNVG,Holster,89985831397392,17172715247,17330407522,Kneepads,13770147630,16755421666,4507911797,118325759243,18325759243,17430938152,15893925206,17558966643,12383357842 & startergear me FN,MP7,Glock & permmaxhealth me 125 & heal me',
        "MR": 'run permrtag me <font face="Michroma">Delta-0 "Livid Night" | Rank</font> & permcrtag me 4 2 115 & permmorph me remove & permshirt me 14572682166 14572536468 & permhat me 0,JNVG,Holster,89985831397392,17172715247,17330407522,Kneepads,13770147630,16270371844,4507911797,118325759243,8087415055,17430938152,15893925206,12497812780,12497817183,17558966643 & permhat me 12383357842 & startergear me FN,MP7,Glock & permmaxhealth me 150 & heal me',
        "HR": 'run permrtag me <font face="Michroma">Delta-0 "Livid Night" | Rank</font> & permcrtag me 4 2 115 & permmorph me remove & permshirt me 14572682166 14572536468 & permhat me 0,JQNVG,Holster,89985831397392,17172715247,17330407522,Kneepads,13770147630,16270371844,4507911797,118325759243,8087415055,17430938152,15893925206,12497812780,18273662783,18273659133 & permhat me 12383357842 & startergear me FN,MP7,Glock & permmaxhealth me 175 & heal me',
    }
}

@bot.tree.command(name="morph", description="Morph a user automatically.")
@app_commands.describe(
    site="Choose the site (416 or Virtus)",
    roblox_username="Roblox username",
    rank="Choose the rank (LR, MR, HR)"
)
@app_commands.choices(site=[
    app_commands.Choice(name="416", value="416"),
    app_commands.Choice(name="Virtus", value="Virtus"),
])
@app_commands.choices(rank=[
    app_commands.Choice(name="LR", value="LR"),
    app_commands.Choice(name="MR", value="MR"),
    app_commands.Choice(name="HR", value="HR"),
])
async def morph(interaction: Interaction, site: app_commands.Choice[str], roblox_username: str, rank: app_commands.Choice[str]):
    await interaction.response.defer(ephemeral=True)

    site_key = site.value.lower()
    rank_key = rank.value

    morph_template = morphs.get(site_key, {}).get(rank_key)
    if not morph_template:
        await interaction.followup.send(f"Morph data not found for site `{site.value}` and rank `{rank.value}`.", ephemeral=True)
        return

    # Replace all ' me ' occurrences with the roblox username (surrounded by spaces)
    morph_text = morph_template.replace(" me ", f" {roblox_username} ")

    await interaction.followup.send(f"Morph command for **{site.value}**:\n```\n{morph_text}\n```", ephemeral=True)


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
bot.run(os.environ["DISCORD_BOT_TOKEN"])
