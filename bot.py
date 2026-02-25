"""
STARCoach - AI-Powered STAR Interview Practice Bot

Main entry point for the Discord bot. Helps users practice
answering behavioral interview questions using the STAR method
(Situation, Task, Action, Result).
"""

import os
import asyncio
import logging
from pathlib import Path

import discord
from discord.ext import commands
from dotenv import load_dotenv

from src.services.database import Database

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("starcoach")


class STARCoach(commands.Bot):
    """
    Main bot class for STARCoach.
    
    Conducts STAR method interview practice sessions via Discord
    voice channels, then provides coaching feedback on how to
    improve STAR-formatted answers.
    """

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        intents.members = True

        super().__init__(
            command_prefix=os.getenv("COMMAND_PREFIX", "!"),
            intents=intents,
            description="AI-powered STAR interview practice coach",
        )

        # Database instance
        self.db = Database()

        # Channel ID for posting coaching reports
        self.report_channel_id = int(os.getenv("REPORT_CHANNEL_ID", 0))

        # Role name that triggers a practice session
        self.applicant_role_name = os.getenv("PRACTICE_ROLE_NAME", "Practice")

        # Score threshold (not used for hire/no-hire, but for "ready" indicator)
        self.fit_threshold = int(os.getenv("READINESS_THRESHOLD", 70))

        # Active practice sessions: {voice_channel_id: session_data}
        self.active_sessions = {}

    async def on_ready(self):
        """Called when the bot is fully connected and ready."""
        if not self.cogs:
            logger.info("Loading cogs...")
            for cog in ["src.cogs.voice", "src.cogs.admin"]:
                try:
                    self.load_extension(cog)
                    logger.info(f"Loaded cog: {cog}")
                except Exception as e:
                    logger.error(f"Failed to load cog {cog}: {e}")
            logger.info(f"Loaded cogs: {list(self.cogs.keys())}")
        
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Connected to {len(self.guilds)} guild(s)")
        logger.info(f"Report channel ID: {self.report_channel_id}")
        logger.info(f"Practice role: {self.applicant_role_name}")
        logger.info("------")

        # Set presence
        activity = discord.Activity(
            type=discord.ActivityType.listening,
            name="STAR practice sessions",
        )
        await self.change_presence(activity=activity)

    async def on_voice_state_update(self, member, before, after):
        """Handle voice state changes - delegate to voice cog."""
        logger.info(f"[BOT] Voice event: {member.display_name} | {before.channel} -> {after.channel}")
        
        # Get voice cog and call its handler
        voice_cog = self.get_cog("VoiceCog")
        if voice_cog:
            await voice_cog.handle_voice_update(member, before, after)
        else:
            logger.warning("VoiceCog not found!")

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        """Global error handler for commands."""
        if isinstance(error, commands.CommandNotFound):
            return

        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You don't have permission to use this command.")
            return

        if isinstance(error, commands.NoPrivateMessage):
            await ctx.send("❌ This command can only be used in a server, not in DMs.")
            return

        if isinstance(error, commands.CheckFailure):
            await ctx.send("❌ You don't have permission to use this command.")
            return

        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ Missing argument: `{error.param.name}`\nUsage: `!{ctx.command.name} {ctx.command.signature}`")
            return

        if isinstance(error, commands.BadArgument):
            await ctx.send(f"❌ Invalid argument.\nUsage: `!{ctx.command.name} {ctx.command.signature}`")
            return

        # Unwrap CommandInvokeError to get the real exception
        original = getattr(error, "original", error)
        logger.error(f"Command error in {ctx.command}: {original}", exc_info=original)
        await ctx.send(f"❌ An error occurred: `{type(original).__name__}: {original}`")

    def get_report_channel(self) -> discord.TextChannel | None:
        """Get the channel for posting coaching reports."""
        return self.get_channel(self.report_channel_id)


async def main():
    """Main entry point."""
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        logger.error("DISCORD_TOKEN not found in environment variables!")
        logger.error("Please create a .env file with your bot token.")
        return

    bot = STARCoach()
    
    # Initialize database first
    await bot.db.initialize()
    logger.info("Database initialized")

    await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
