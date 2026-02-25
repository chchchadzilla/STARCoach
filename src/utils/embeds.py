"""
Embed Utilities - Discord embed generation for STAR coaching reports.

Creates formatted Discord embeds for practice session
coaching feedback and other bot messages.
"""

from datetime import datetime
from typing import Optional, Any

import discord


def _embed_char_count(embed: discord.Embed) -> int:
    """Calculate total character count of an embed (Discord counts all text)."""
    total = len(embed.title or "") + len(embed.description or "")
    if embed.footer and embed.footer.text:
        total += len(embed.footer.text)
    if embed.author and embed.author.name:
        total += len(embed.author.name)
    for field in embed.fields:
        total += len(field.name or "") + len(field.value or "")
    return total


def _field_char_count(name: str, value: str) -> int:
    """Character count of a single field."""
    return len(name) + len(value)


def create_report_embeds(
    applicant: Any,
    analysis: dict,
    transcript_preview: str,
    fit_threshold: int = 70,
    interview_id: Optional[int] = None,
) -> list[discord.Embed]:
    """
    Create STAR coaching report as one or more embeds (Part I / Part II).
    
    Builds all fields, then distributes them across embeds so
    none exceed Discord's 6000-char limit. No data is truncated.
    
    Args:
        applicant: Discord member object
        analysis: STAR coaching analysis result dict
        transcript_preview: First portion of transcript
        fit_threshold: Score threshold for "interview ready"
        interview_id: Optional session ID to display in the report
        
    Returns:
        List of Discord Embed objects (1-3 embeds)
    """
    readiness_score = analysis.get("readiness_score", analysis.get("fit_score", 0))
    readiness_level = analysis.get("readiness_level", "NEEDS_PRACTICE")

    readiness_display = {
        "INTERVIEW_READY": ("🟢 INTERVIEW READY", discord.Color.green()),
        "ALMOST_READY": ("🟡 ALMOST READY", discord.Color.gold()),
        "NEEDS_PRACTICE": ("🟠 NEEDS MORE PRACTICE", discord.Color.orange()),
        "EARLY_STAGE": ("🔴 EARLY STAGE", discord.Color.red()),
    }
    
    status_text, color = readiness_display.get(
        readiness_level, 
        ("📋 PRACTICE COMPLETE", discord.Color.blurple())
    )

    # ------------------------------------------------------------------
    # Build all fields as (name, value, inline) tuples
    # ------------------------------------------------------------------
    fields: list[tuple[str, str, bool]] = []

    # Readiness Score
    score_bar = _create_score_bar(readiness_score)
    fields.append((
        "📊 Interview Readiness",
        f"**{readiness_score}**/100\n{score_bar}",
        False,
    ))

    # STAR Component Scores
    scores = analysis.get("scores", {})
    if scores:
        score_emoji = {
            "situation_clarity": "📍",
            "task_definition": "📋",
            "action_detail": "⚡",
            "result_impact": "🏆",
            "overall_structure": "🏗️",
            "storytelling": "📖",
        }
        score_lines = []
        for trait, score in scores.items():
            emoji = score_emoji.get(trait, "📊")
            trait_name = trait.replace("_", " ").title()
            score_lines.append(f"{emoji} **{trait_name}:** {score}/10")
        fields.append(("⭐ STAR Component Scores", "\n".join(score_lines), True))

    # Strengths
    strengths = analysis.get("strengths", [])
    if strengths:
        fields.append((
            "💪 What You Did Well",
            "\n".join(f"• {s}" for s in strengths[:5]),
            True,
        ))

    # Improvement Areas
    improvement_areas = analysis.get("improvement_areas", analysis.get("concerns", []))
    if improvement_areas:
        fields.append((
            "🔧 Areas to Improve",
            "\n".join(f"• {a}" for a in improvement_areas[:5]),
            True,
        ))

    # STAR Breakdown per question
    star_breakdown = analysis.get("star_breakdown", [])
    if star_breakdown:
        breakdown_lines = []
        for i, item in enumerate(star_breakdown[:5], 1):
            topic = item.get("question_topic", f"Question {i}")
            present = item.get("components_present", [])
            missing = item.get("components_missing", [])
            feedback = item.get("feedback", "")
            
            star_visual = ""
            for component in ["S", "T", "A", "R"]:
                if component in present:
                    star_visual += f"✅{component} "
                elif component in missing:
                    star_visual += f"❌{component} "
                else:
                    star_visual += f"⬜{component} "
            
            line = f"**{i}. {topic}**\n{star_visual}"
            if feedback:
                line += f"\n> {feedback}"
            breakdown_lines.append(line)
        
        breakdown_text = "\n\n".join(breakdown_lines)
        if len(breakdown_text) <= 1024:
            fields.append(("📝 Answer-by-Answer Breakdown", breakdown_text, False))
        else:
            mid = len(breakdown_lines) // 2
            fields.append((
                "📝 Answer Breakdown (1/2)",
                "\n\n".join(breakdown_lines[:mid])[:1024],
                False,
            ))
            fields.append((
                "📝 Answer Breakdown (2/2)",
                "\n\n".join(breakdown_lines[mid:])[:1024],
                False,
            ))

    # Coaching Tips
    coaching_tips = analysis.get("coaching_tips", [])
    if coaching_tips:
        fields.append((
            "💡 Coaching Tips",
            "\n".join(f"**{i}.** {tip}" for i, tip in enumerate(coaching_tips[:4], 1)),
            False,
        ))

    # Example Improvement
    example = analysis.get("example_improvements", {})
    if example and example.get("weakest_answer_topic"):
        example_text = f"**Topic:** {example['weakest_answer_topic']}\n"
        if example.get("original_approach"):
            example_text += f"**What you said:** {example['original_approach']}\n"
        if example.get("suggested_approach"):
            example_text += f"**Try this instead:** {example['suggested_approach']}"
        if len(example_text) <= 1024:
            fields.append(("🔄 Example: How to Improve Your Weakest Answer", example_text, False))

    # Overall Feedback
    overall_feedback = analysis.get("overall_feedback", "")
    next_steps = analysis.get("next_steps", "")
    if overall_feedback or next_steps:
        feedback_text = overall_feedback
        if next_steps:
            feedback_text += f"\n\n**Next Steps:** {next_steps}"
        fields.append(("🎯 Overall Coaching Feedback", feedback_text[:1024], False))

    # Transcript Preview
    if transcript_preview:
        preview = transcript_preview[:400]
        if len(transcript_preview) > 400:
            preview += "..."
        fields.append(("📜 Session Preview", f"```{preview}```", False))

    # ------------------------------------------------------------------
    # Distribute fields across embeds (max 5800 chars each for safety)
    # ------------------------------------------------------------------
    MAX_EMBED_SIZE = 5800
    embeds: list[discord.Embed] = []
    part = 1

    def _make_embed(part_num: int, total_parts: int) -> discord.Embed:
        id_tag = f" (#{interview_id})" if interview_id else ""
        if total_parts == 1:
            title = f"🎯 STAR Coaching Report: {applicant.display_name}{id_tag}"
        else:
            title = f"🎯 STAR Coaching Report: {applicant.display_name}{id_tag} — Part {part_num}"
        e = discord.Embed(
            title=title,
            description=f"**{status_text}**" if part_num == 1 else "",
            color=color,
            timestamp=datetime.utcnow(),
        )
        if part_num == 1:
            e.set_author(
                name=f"Practice Session • {applicant.display_name}",
                icon_url=applicant.avatar.url if hasattr(applicant, 'avatar') and applicant.avatar else None,
            )
        return e

    # First pass: try fitting everything in one embed
    test_embed = _make_embed(1, 1)
    for name, value, inline in fields:
        test_embed.add_field(name=name, value=value, inline=inline)
    test_embed.set_footer(text=f"STARCoach • {f'Session #{interview_id} • ' if interview_id else ''}Readiness Threshold: {fit_threshold}")

    if _embed_char_count(test_embed) <= MAX_EMBED_SIZE:
        return [test_embed]

    # Second pass: split across multiple embeds
    # Estimate how many parts we need
    total_field_chars = sum(_field_char_count(n, v) for n, v, _ in fields)
    estimated_parts = max(2, (total_field_chars // (MAX_EMBED_SIZE - 200)) + 1)

    current_embed = _make_embed(1, estimated_parts)
    # Account for base embed overhead (title, description, author, footer)
    base_overhead = 200

    for name, value, inline in fields:
        field_size = _field_char_count(name, value)
        
        # If adding this field would exceed the limit, start a new embed
        if _embed_char_count(current_embed) + field_size > MAX_EMBED_SIZE and current_embed.fields:
            current_embed.set_footer(
                text=f"STARCoach • {f'Session #{interview_id} • ' if interview_id else ''}Part {part} — continued below ⬇️",
            )
            embeds.append(current_embed)
            part += 1
            current_embed = _make_embed(part, estimated_parts)
        
        current_embed.add_field(name=name, value=value, inline=inline)
    
    # Finalize last embed
    current_embed.set_footer(
        text=f"STARCoach • {f'Session #{interview_id} • ' if interview_id else ''}Readiness Threshold: {fit_threshold}",
    )
    embeds.append(current_embed)

    # Fix part numbers in titles now that we know the real total
    total = len(embeds)
    if total > 1:
        id_tag = f" (#{interview_id})" if interview_id else ""
        for i, e in enumerate(embeds, 1):
            e.title = f"🎯 STAR Coaching Report: {applicant.display_name}{id_tag} — Part {i}/{total}"

    return embeds


# Keep backward-compatible alias that returns a single embed (first one)
def create_report_embed(
    applicant: Any,
    analysis: dict,
    transcript_preview: str,
    fit_threshold: int = 70,
    interview_id: Optional[int] = None,
) -> discord.Embed:
    """Backward-compatible wrapper — returns the first embed."""
    embeds = create_report_embeds(applicant, analysis, transcript_preview, fit_threshold, interview_id=interview_id)
    return embeds[0]


def _create_score_bar(score: int, total: int = 100, length: int = 20) -> str:
    """Create a visual progress bar for scores."""
    filled = int((score / total) * length)
    empty = length - filled
    
    if score >= 80:
        fill_char = "🟩"
    elif score >= 60:
        fill_char = "🟨"
    elif score >= 40:
        fill_char = "🟧"
    else:
        fill_char = "🟥"
    
    return fill_char * filled + "⬜" * empty


def create_session_start_embed(
    applicant: discord.Member,
    channel: discord.VoiceChannel,
) -> discord.Embed:
    """Create an embed for when a practice session starts."""
    embed = discord.Embed(
        title="🎯 STAR Practice Session Started",
        description=f"Practice session with **{applicant.display_name}**",
        color=discord.Color.blue(),
        timestamp=datetime.utcnow(),
    )
    
    embed.add_field(name="Channel", value=channel.name, inline=True)
    embed.add_field(name="User ID", value=str(applicant.id), inline=True)
    
    embed.set_thumbnail(url=applicant.avatar.url if applicant.avatar else None)
    embed.set_footer(text="STARCoach • Session in progress")
    
    return embed


def create_error_embed(
    title: str,
    description: str,
    details: Optional[str] = None,
) -> discord.Embed:
    """Create an error embed."""
    embed = discord.Embed(
        title=f"❌ {title}",
        description=description,
        color=discord.Color.red(),
        timestamp=datetime.utcnow(),
    )
    
    if details:
        embed.add_field(
            name="Details",
            value=f"```{details[:1000]}```",
            inline=False,
        )
    
    return embed


def create_success_embed(
    title: str,
    description: str,
) -> discord.Embed:
    """Create a success embed."""
    return discord.Embed(
        title=f"✅ {title}",
        description=description,
        color=discord.Color.green(),
        timestamp=datetime.utcnow(),
    )
