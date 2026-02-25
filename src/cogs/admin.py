"""
Admin Cog - Administrative commands for managing STARCoach.

Provides commands for viewing past practice sessions, re-analyzing,
and other administrative functions.
"""

import logging
from datetime import datetime

import discord
from discord.ext import commands

from src.utils.embeds import create_report_embeds

logger = logging.getLogger("starcoach.admin")


class AdminCog(commands.Cog):
    """Administrative commands for STARCoach."""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="history")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def view_history(self, ctx: commands.Context, limit: int = 10):
        """
        View recent practice session history.
        
        Usage: !history [limit]
        """
        interviews = await self.bot.db.get_recent_interviews(
            guild_id=ctx.guild.id,
            limit=limit,
        )

        if not interviews:
            await ctx.send("📋 No practice session history found.")
            return

        embed = discord.Embed(
            title="📋 Recent Practice Sessions",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow(),
        )

        for interview in interviews:
            session_id = interview.get("id", "?")
            score = interview.get("fit_score") or "N/A"
            ready = "✅" if interview.get("recommended") else "🔄"
            date = interview.get("created_at", "Unknown")
            transcript_exists = "📄" if interview.get("transcript") else "⏳"

            embed.add_field(
                name=f"#{session_id} — {interview['applicant_name']}",
                value=(
                    f"{transcript_exists} Readiness: **{score}**/100 {ready}\n"
                    f"Date: {date}\n"
                    f"Channel: #{interview.get('channel_name', 'Unknown')}\n"
                    f"`!transcript {session_id}` · `!reanalyze {session_id}`"
                ),
                inline=True,
            )

        embed.set_footer(text="Use !transcript <#> or !reanalyze <#> to view/redo a session")
        await ctx.send(embed=embed)

    @commands.command(name="session")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def view_interview(self, ctx: commands.Context, session_id: int):
        """
        View details of a specific practice session.
        
        Usage: !session <id>
        """
        interview = await self.bot.db.get_interview(session_id)

        if not interview:
            await ctx.send(f"❌ Session #{session_id} not found.")
            return

        embed = discord.Embed(
            title=f"Practice Session #{session_id}",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow(),
        )

        embed.add_field(
            name="Practitioner",
            value=interview["applicant_name"],
            inline=True,
        )
        embed.add_field(
            name="Readiness Score",
            value=f"{interview.get('fit_score', 'N/A')}/100",
            inline=True,
        )
        embed.add_field(
            name="Interview Ready",
            value="✅ Yes" if interview.get("recommended") else "🔄 Keep Practicing",
            inline=True,
        )

        if interview.get("analysis"):
            analysis = interview["analysis"]
            
            if analysis.get("strengths"):
                embed.add_field(
                    name="Strengths",
                    value="\n".join(f"• {s}" for s in analysis["strengths"][:3]),
                    inline=False,
                )
            
            if analysis.get("concerns"):
                embed.add_field(
                    name="Areas to Improve",
                    value="\n".join(f"• {c}" for c in analysis["concerns"][:3]),
                    inline=False,
                )

        if interview.get("transcript"):
            preview = interview["transcript"][:500]
            if len(interview["transcript"]) > 500:
                preview += "..."
            embed.add_field(
                name="Session Preview",
                value=f"```{preview}```",
                inline=False,
            )

        await ctx.send(embed=embed)

    @commands.command(name="transcript")
    @commands.has_permissions(manage_guild=True)
    async def get_transcript(self, ctx: commands.Context, session_id: str):
        """
        Get full transcript of a practice session.
        
        Usage: !transcript <id>
        """
        session_id_clean = session_id.lstrip("#")
        try:
            session_id_int = int(session_id_clean)
        except ValueError:
            await ctx.send(f"❌ Invalid session ID: {session_id}. Please use a number like `!transcript 1`")
            return
        
        interview = await self.bot.db.get_interview(session_id_int)

        if not interview:
            await ctx.send(f"❌ Session #{session_id_int} not found.")
            return

        transcript = interview.get("transcript", "No transcript available.")

        if len(transcript) > 1900:
            import io
            file_buffer = io.BytesIO(transcript.encode('utf-8'))
            file = discord.File(
                fp=file_buffer,
                filename=f"transcript_{session_id_int}.txt",
            )
            await ctx.send(f"📄 Transcript for Session #{session_id_int}:", file=file)
        else:
            await ctx.send(
                f"📄 **Transcript for Session #{session_id_int}:**\n```{transcript}```"
            )

    @commands.command(name="reanalyze")
    @commands.has_permissions(administrator=True)
    async def reanalyze(self, ctx: commands.Context, session_id: str):
        """
        Re-run coaching analysis on a past practice session.
        
        Usage: !reanalyze <id>
        """
        session_id_clean = session_id.lstrip("#")
        try:
            session_id_int = int(session_id_clean)
        except ValueError:
            await ctx.send(f"❌ Invalid session ID: {session_id}. Please use a number like `!reanalyze 1`")
            return
        
        interview = await self.bot.db.get_interview(session_id_int)

        if not interview:
            await ctx.send(f"❌ Session #{session_id_int} not found.")
            return

        transcript = interview.get("transcript")
        if not transcript:
            await ctx.send("❌ No transcript available for this session.")
            return

        await ctx.send("🔄 Re-analyzing practice session...")

        voice_cog = self.bot.get_cog("VoiceCog")
        if not voice_cog:
            await ctx.send("❌ Voice cog not loaded.")
            return

        analysis = await voice_cog.analysis.analyze_transcript(transcript)

        if not analysis:
            await ctx.send("❌ Analysis failed.")
            return

        await self.bot.db.save_analysis(session_id_int, analysis)

        class MockApplicant:
            def __init__(self, name, id):
                self.display_name = name
                self.id = id
                self.avatar = None

        applicant = MockApplicant(
            interview["applicant_name"],
            interview["applicant_id"],
        )

        embeds = create_report_embeds(
            applicant=applicant,
            analysis=analysis,
            transcript_preview=transcript[:500],
            fit_threshold=self.bot.fit_threshold,
            interview_id=session_id_int,
        )

        await ctx.send("✅ Coaching analysis complete!")
        for embed in embeds:
            await ctx.send(embed=embed)

    @commands.command(name="setrole")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def set_practice_role(self, ctx: commands.Context, *, role_name: str):
        """
        Set the role name that triggers practice sessions.
        
        Usage: !setrole <role name>
        """
        role = discord.utils.get(ctx.guild.roles, name=role_name)
        if not role:
            await ctx.send(f"⚠️ Role '{role_name}' not found, but setting anyway.")

        self.bot.applicant_role_name = role_name
        await ctx.send(f"✅ Practice role set to: **{role_name}**")

    @commands.command(name="setthreshold")
    @commands.has_permissions(administrator=True)
    async def set_threshold(self, ctx: commands.Context, threshold: int):
        """
        Set the readiness score threshold.
        
        Usage: !setthreshold <1-100>
        """
        if not 1 <= threshold <= 100:
            await ctx.send("❌ Threshold must be between 1 and 100.")
            return

        self.bot.fit_threshold = threshold
        await ctx.send(f"✅ Readiness threshold set to: **{threshold}**")

    @commands.command(name="status")
    @commands.guild_only()
    async def show_status(self, ctx: commands.Context):
        """Show current bot configuration and status."""
        embed = discord.Embed(
            title="🎯 STARCoach Status",
            color=discord.Color.green(),
            timestamp=datetime.utcnow(),
        )

        embed.add_field(
            name="Practice Role",
            value=self.bot.applicant_role_name,
            inline=True,
        )
        embed.add_field(
            name="Readiness Threshold",
            value=f"{self.bot.fit_threshold}/100",
            inline=True,
        )
        embed.add_field(
            name="Active Sessions",
            value=str(len(self.bot.active_sessions)),
            inline=True,
        )

        report_channel = self.bot.get_report_channel()
        embed.add_field(
            name="Report Channel",
            value=f"#{report_channel.name}" if report_channel else "Not configured",
            inline=True,
        )

        stats = await self.bot.db.get_stats(ctx.guild.id)
        embed.add_field(
            name="Total Sessions",
            value=str(stats.get("total_sessions", 0)),
            inline=True,
        )
        embed.add_field(
            name="Avg Readiness",
            value=f"{stats.get('avg_readiness_score', 0):.1f}",
            inline=True,
        )

        await ctx.send(embed=embed)


def setup(bot):
    """Load the Admin cog."""
    bot.add_cog(AdminCog(bot))
