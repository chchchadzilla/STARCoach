"""
Voice Cog - STAR Interview Practice Coach.

This cog handles:
- Joining voice channels when practice users enter
- Dynamic LLM-driven STAR interview practice
- Coaching users through Situation, Task, Action, Result format
- Silence detection before sending to LLM
- TTS responses + text display for accessibility
"""

import asyncio
import logging
import io
import os
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import discord
from discord.ext import commands
import aiohttp

from src.services.transcription import TranscriptionService
from src.services.analysis import AnalysisService
from src.services.tts import get_tts_service
from src.utils.embeds import create_report_embeds

logger = logging.getLogger("starcoach.voice")

# STAR Coach system prompt template
INTERVIEWER_SYSTEM_PROMPT_TEMPLATE = """CRITICAL RULES - READ FIRST:
1. **KEEP IT SHORT** - Maximum 2-3 sentences per response. One brief reaction + coaching nudge or next question.
2. **NO URLS OR LINKS** - Never include ANY URLs, websites, or web references.
3. **NO ROLEPLAY ACTIONS** - Never use *asterisk actions* like *nods*. Just speak.
4. **NO GREETINGS** - The user has already been greeted. Jump straight into your question.
5. **NO SYSTEM NOTES** - Never include [SYSTEM:], [NOTE:], [THINKING:], or any bracketed commentary.

You are an AI STAR interview coach helping someone practice answering behavioral interview questions using the STAR method.

{community_context}

THE STAR METHOD:
- **S**ituation: Set the scene. What was the context?
- **T**ask: What was your responsibility or challenge?
- **A**ction: What specific steps did YOU take?
- **R**esult: What was the outcome? What did you learn?

YOUR GOALS:
1. Ask behavioral interview questions that require STAR-formatted answers
2. Listen to their answer and identify which STAR components are present or missing
3. Gently coach them to fill in missing components
4. Help them practice giving complete, structured STAR answers
5. Be encouraging but honest about what needs improvement

COACHING APPROACH:
- After each answer, briefly note what was good
- If they're missing a STAR component, ask a follow-up to draw it out
  - Missing Situation: "Can you paint the picture a bit more? Where were you working, and what was going on?"
  - Missing Task: "What was specifically YOUR role or responsibility in that?"
  - Missing Action: "Walk me through the specific steps YOU took."
  - Missing Result: "How did it turn out? What was the outcome?"
- If they give a complete STAR answer, acknowledge it and move to the next question
- Use phrases like "Great start!", "Let's dig deeper into...", "That's a solid answer!"

RESPONSE FORMAT (STRICT):
- Sentence 1: Brief positive acknowledgment of what they said
- Sentence 2: Either a coaching nudge for a missing component OR the next question
- THAT'S IT. No paragraphs. No lists. No lectures about STAR theory.
- DO NOT say "Hello", "Hi", "Welcome" - the user was already greeted.

EXAMPLE GOOD COACHING RESPONSES:
- "Nice, you set the scene really well! Now walk me through the specific steps you took to solve that."
- "Good detail on your actions! How did everything turn out in the end?"
- "Solid STAR answer! Okay, next one: Tell me about a time you had to deal with a difficult team member."
- "I can see you jumped straight to what you did. Let's back up, what was the situation and what was your specific role?"

QUESTION TYPES TO USE:
- "Tell me about a time when you had to..."
- "Describe a situation where you..."
- "Give me an example of when you..."
- "Walk me through a time you..."

TOPICS FOR BEHAVIORAL QUESTIONS:
- Handling conflict or disagreement
- Meeting a tight deadline
- Taking initiative on something
- Dealing with failure or a mistake
- Leading or influencing others
- Solving a complex problem
- Adapting to change
- Working under pressure
- Collaborating with a difficult person
- Going above and beyond
- Handling a difficult customer or client
- Managing a project or team
- Identifying a problem and solving it independently

GUIDELINES:
- Ask ONE question at a time
- Give them time to answer fully before coaching
- Track which STAR components they consistently miss
- After 5-6 complete questions (with coaching), wrap up
- Be warm, encouraging, and supportive - this is practice, not a test!

When ready to end (ONLY after 5+ fully explored questions), include "[INTERVIEW_COMPLETE]" at the end.

Remember: This is VOICE. Keep it conversational and SHORT. NO GREETINGS. DO NOT END EARLY."""


def load_interview_config() -> str:
    """
    Load custom practice configuration from interview-config.md.
    
    Returns context string to inject into system prompt.
    """
    config_path = Path("interview-config.md")
    
    if not config_path.exists():
        logger.warning("interview-config.md not found, using default config")
        return """CONTEXT:
- This is a STAR interview practice session
- You're having a voice conversation (keep responses concise and natural for speech)
- The user is practicing for real interviews, be encouraging and helpful
- Focus on helping them structure answers in Situation, Task, Action, Result format"""
    
    try:
        content = config_path.read_text(encoding="utf-8")
        
        context_parts = []
        
        # Extract practitioner name if present
        if "**Practitioner Name:**" in content:
            for line in content.split("\n"):
                if "**Practitioner Name:**" in line:
                    name = line.replace("**Practitioner Name:**", "").strip()
                    if name:
                        context_parts.append(f"- The person practicing is {name}")
                    break
        
        # Extract target role/industry
        if "**Target Role:**" in content:
            for line in content.split("\n"):
                if "**Target Role:**" in line:
                    role = line.replace("**Target Role:**", "").strip()
                    if role:
                        context_parts.append(f"- They're preparing for: {role}")
                    break
        
        # Extract focus areas
        if "**Focus Areas:**" in content:
            start = content.find("**Focus Areas:**")
            end = content.find("---", start + 1)
            if end == -1:
                end = start + 500
            section = content[start:end]
            areas = []
            for line in section.split("\n"):
                line = line.strip()
                if line.startswith("- ") and len(line) > 3:
                    areas.append(line[2:])
            if areas:
                context_parts.append(f"\nFOCUS AREAS FOR PRACTICE:\n" + "\n".join(f"- {a}" for a in areas[:6]))
        
        # Extract common weaknesses to watch for
        if "**Known Weaknesses:**" in content:
            start = content.find("**Known Weaknesses:**")
            end = content.find("---", start + 1)
            if end == -1:
                end = start + 500
            section = content[start:end]
            weaknesses = []
            for line in section.split("\n"):
                line = line.strip()
                if line.startswith("- ") and len(line) > 3:
                    weaknesses.append(line[2:])
            if weaknesses:
                context_parts.append(f"\nKNOWN AREAS TO IMPROVE:\n" + "\n".join(f"- {w}" for w in weaknesses[:5]))
        
        # Extract special instructions
        if "**Special Instructions:**" in content:
            start = content.find("**Special Instructions:**")
            end = content.find("---", start + 1)
            if end == -1:
                end = start + 400
            section = content[start:end]
            instructions = []
            for line in section.split("\n"):
                line = line.strip()
                if line.startswith("- ") and len(line) > 3:
                    instructions.append(line[2:])
            if instructions:
                context_parts.append(f"\nSPECIAL INSTRUCTIONS:\n" + "\n".join(f"- {i}" for i in instructions[:4]))
        
        if context_parts:
            result = "CONTEXT:\n" + "\n".join(context_parts)
            result += "\n- This is a STAR interview practice session"
            result += "\n- You're having a voice conversation (keep responses concise and natural for speech)"
            result += "\n- Be encouraging and supportive - this is practice, not a real interview"
            logger.info("Loaded custom practice config from interview-config.md")
            return result
        else:
            logger.warning("Could not parse interview-config.md, using defaults")
            return """CONTEXT:
- This is a STAR interview practice session
- You're having a voice conversation (keep responses concise and natural for speech)
- The user is practicing for real interviews, be encouraging and helpful
- Focus on helping them structure answers in Situation, Task, Action, Result format"""
            
    except Exception as e:
        logger.error(f"Error loading interview-config.md: {e}")
        return """CONTEXT:
- This is a STAR interview practice session
- You're having a voice conversation (keep responses concise and natural for speech)
- The user is practicing for real interviews, be encouraging and helpful"""


def get_system_prompt() -> str:
    """Build the full system prompt with custom config."""
    community_context = load_interview_config()
    return INTERVIEWER_SYSTEM_PROMPT_TEMPLATE.format(community_context=community_context)


class InterviewSession:
    """Represents an active STAR practice session."""

    def __init__(self, channel: discord.VoiceChannel, applicant: discord.Member, text_channel: discord.TextChannel):
        self.channel = channel
        self.applicant = applicant
        self.guild = channel.guild
        self.text_channel = text_channel
        self.started_at = datetime.utcnow()
        
        # Voice connection
        self.connection: Optional[discord.VoiceClient] = None
        
        # Recording state
        self.sink: Optional[discord.sinks.WaveSink] = None
        self.is_recording = False
        self.last_audio_size = 0
        self.silence_start: Optional[float] = None
        
        # Conversation state
        self.conversation_history: list[dict] = []
        self.is_active = True
        self.is_speaking = False
        self.interview_complete = False
        
        # Transcript for final coaching analysis
        self.transcript_lines: list[str] = []
        
        # Pre-allocated interview ID (set at session start)
        self.interview_id: Optional[int] = None
        
        # Report tracking
        self.report_sent = False


class VoiceCog(commands.Cog):
    """STAR Interview Practice Coach cog."""

    def __init__(self, bot):
        self.bot = bot
        self.transcription = TranscriptionService()
        self.analysis = AnalysisService()
        self.tts = get_tts_service()
        
        # Silence detection settings — tuned for conversational feel
        self.silence_threshold = 0.8      # seconds of silence before processing (was 1.5)
        self.check_interval = 0.05        # poll interval for audio size changes (was 0.2)
        self.min_speech_duration = 0.3    # ignore ultra-short noise bursts
        
        # OpenRouter settings
        self.openrouter_key = os.getenv("OPENROUTER_API_KEY")
        self.openrouter_model = os.getenv("OPENROUTER_MODEL", "anthropic/claude-haiku-4.5:nitro")
        
        # Shared HTTP session for lower latency (reuse TCP connections)
        self._http_session: Optional[aiohttp.ClientSession] = None

    async def _get_http_session(self) -> aiohttp.ClientSession:
        """Get or create a shared aiohttp session for connection reuse."""
        if self._http_session is None or self._http_session.closed:
            self._http_session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15),
                connector=aiohttp.TCPConnector(limit=10, keepalive_timeout=60),
            )
        return self._http_session

    async def cog_unload(self):
        """Cleanup shared HTTP session when cog unloads."""
        if self._http_session and not self._http_session.closed:
            await self._http_session.close()

    async def handle_voice_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        """Handle voice state changes - called from bot.py."""
        logger.info(f"Voice update: {member.display_name} | {before.channel} -> {after.channel}")
        
        if member.bot:
            return

        # Check for practice role
        practice_role = discord.utils.get(
            member.guild.roles,
            name=self.bot.applicant_role_name,
        )
        
        if not practice_role or practice_role not in member.roles:
            return

        logger.info(f"Practice user detected: {member.display_name}")

        # User joined a voice channel
        if after.channel and (not before.channel or before.channel != after.channel):
            if after.channel.id in self.bot.active_sessions:
                logger.info(f"Session already in progress in {after.channel.name}")
                return
            await self._start_interview(member, after.channel)

        # User left
        elif before.channel and (not after.channel or before.channel != after.channel):
            await self._handle_applicant_leave(member, before.channel)

    async def _start_interview(self, applicant: discord.Member, channel: discord.VoiceChannel):
        """Start a STAR practice session."""
        if channel.id in self.bot.active_sessions:
            logger.info(f"Already in session in {channel.name}")
            return

        logger.info(f"Starting STAR practice with {applicant.display_name}")

        text_channel = self.bot.get_report_channel()
        if not text_channel:
            text_channel = channel.guild.text_channels[0] if channel.guild.text_channels else None

        session = InterviewSession(channel, applicant, text_channel)

        try:
            session.connection = await channel.connect()
            logger.info(f"Connected to {channel.name}")
            
            self.bot.active_sessions[channel.id] = session
            asyncio.create_task(self._run_conversation(session))

        except Exception as e:
            logger.error(f"Failed to start session: {e}", exc_info=True)
            if session.connection:
                await session.connection.disconnect()
            self.bot.active_sessions.pop(channel.id, None)

    async def _run_conversation(self, session: InterviewSession):
        """Run the STAR practice conversation loop."""
        try:
            await asyncio.sleep(2)
            
            # Initialize conversation with STAR coach system prompt
            system_prompt = get_system_prompt()
            session.conversation_history = [
                {"role": "system", "content": system_prompt}
            ]
            
            # Pre-allocate interview ID so we can display it throughout the session
            try:
                session.interview_id = await self.bot.db.create_interview(
                    applicant_id=session.applicant.id,
                    applicant_name=session.applicant.display_name,
                    guild_id=session.guild.id,
                    channel_name=session.channel.name,
                    started_at=session.started_at,
                )
                logger.info(f"Pre-allocated session #{session.interview_id}")
            except Exception as e:
                logger.error(f"Failed to pre-allocate interview ID: {e}")
            
            # === INTRODUCTION ===
            intro_message = (
                f"Hey {session.applicant.display_name}! Welcome to your STAR interview practice session. "
                f"I'm going to ask you some behavioral interview questions, and I'll help you "
                f"structure your answers using the STAR method: Situation, Task, Action, and Result. "
                f"Take your time with each answer, and I'll coach you along the way. Ready? Let's go!"
            )
            await self._speak_and_display(session, intro_message)
            await asyncio.sleep(1.0)
            
            # First question — stream directly to voice
            await self._speak_and_display(session, "Alright, here's your first question:", add_to_transcript=False)
            await asyncio.sleep(0.3)
            
            first_question = await self._stream_and_speak(session, is_initial=True)
            
            # Main conversation loop
            question_number = 1
            
            while session.is_active and not session.interview_complete:
                user_response = await self._record_until_silence(session)
                
                if not session.is_active:
                    break
                
                if user_response:
                    logger.info(f"User said: {user_response[:100]}...")
                    
                    session.conversation_history.append({
                        "role": "user",
                        "content": user_response
                    })
                    session.transcript_lines.append(f"[{session.applicant.display_name}]: {user_response}")
                    
                    # Get coaching response — streamed sentence-by-sentence to voice
                    _start = time.time()
                    llm_response = await self._stream_and_speak(session)
                    logger.info(f"LLM response took {time.time() - _start:.1f}s (streamed)")
                    
                    if llm_response:
                        if "[INTERVIEW_COMPLETE]" in llm_response:
                            if question_number >= 5:
                                session.interview_complete = True
                                logger.info(f"Practice ending after {question_number} questions")
                            else:
                                logger.warning(f"LLM tried to end at question {question_number}, forcing continue")
                        
                        question_number += 1
                
                else:
                    if len(session.conversation_history) < 4:
                        await self._speak_and_display(session, "Take your time! Think of a specific example from your experience.", add_to_transcript=False)
            
            # Practice complete
            if session.is_active:
                logger.info(f"Practice complete, generating coaching report... (transcript lines: {len(session.transcript_lines)})")
                
                closing_message = (
                    f"Great practice session, {session.applicant.display_name}! "
                    f"You did a really nice job working through those questions. "
                    f"I'm going to put together some coaching feedback for you now "
                    f"with tips on how to make your STAR answers even stronger. "
                    f"Give me just a moment!"
                )
                await self._speak_and_display(session, closing_message)
                await asyncio.sleep(1)
                
                await self._complete_interview(session)
                
        except asyncio.CancelledError:
            logger.info("Practice session cancelled")
        except Exception as e:
            logger.error(f"Conversation error: {e}", exc_info=True)
        finally:
            await self._cleanup_session(session)

    async def _record_until_silence(self, session: InterviewSession, short_timeout: bool = False) -> Optional[str]:
        """Record audio until silence is detected, then transcribe."""
        if not session.connection or session.is_speaking:
            return None
        
        silence_threshold = self.silence_threshold if not short_timeout else 0.6
        no_response_timeout = 8.0 if short_timeout else 30.0
        
        try:
            session.sink = discord.sinks.WaveSink()
            session.connection.start_recording(
                session.sink,
                self._on_recording_done,
                session.channel.id,
            )
            session.is_recording = True
            session.last_audio_size = 0
            session.silence_start = None
            
            logger.debug("Started recording, waiting for speech...")
            
            has_received_audio = False
            speech_start_time = None
            
            while session.is_active and session.is_recording:
                await asyncio.sleep(self.check_interval)
                
                current_size = self._get_audio_size(session)
                
                if current_size > session.last_audio_size:
                    if not has_received_audio:
                        speech_start_time = time.time()
                    has_received_audio = True
                    session.silence_start = None
                    session.last_audio_size = current_size
                else:
                    if has_received_audio:
                        if session.silence_start is None:
                            session.silence_start = time.time()
                        elif time.time() - session.silence_start >= silence_threshold:
                            # Check minimum speech duration to filter noise bursts
                            speech_duration = (time.time() - speech_start_time) if speech_start_time else 0
                            if speech_duration < self.min_speech_duration:
                                # Too short - likely noise, reset and keep listening
                                logger.debug(f"Ignoring {speech_duration:.1f}s noise burst")
                                has_received_audio = False
                                speech_start_time = None
                                session.silence_start = None
                                continue
                            if not short_timeout:
                                logger.info(f"{silence_threshold}s silence detected, processing...")
                            break
                    else:
                        if session.silence_start is None:
                            session.silence_start = time.time()
                        elif time.time() - session.silence_start >= no_response_timeout:
                            if not short_timeout:
                                logger.info(f"No response for {no_response_timeout} seconds")
                            break
            
            if session.is_recording and session.connection:
                session.connection.stop_recording()
                session.is_recording = False
            
            await asyncio.sleep(0.1)
            
            if has_received_audio and session.sink:
                audio_bytes = self._extract_user_audio(session)
                if audio_bytes:
                    http = await self._get_http_session()
                    result = await self.transcription.transcribe_audio(audio_bytes, http_session=http)
                    if result and result.get("transcript"):
                        return result["transcript"].strip()
            
            return None
            
        except Exception as e:
            logger.error(f"Recording error: {e}")
            if session.is_recording and session.connection:
                try:
                    session.connection.stop_recording()
                except:
                    pass
                session.is_recording = False
            return None

    def _get_audio_size(self, session: InterviewSession) -> int:
        """Get total audio data size from sink."""
        if not session.sink or not session.sink.audio_data:
            return 0
        
        total = 0
        for user_id, audio in session.sink.audio_data.items():
            member = session.guild.get_member(user_id)
            if member and member.bot:
                continue
            if audio.file:
                audio.file.seek(0, 2)
                total += audio.file.tell()
        return total

    def _extract_user_audio(self, session: InterviewSession) -> Optional[bytes]:
        """Extract audio data from non-bot users."""
        if not session.sink or not session.sink.audio_data:
            return None
        
        combined = io.BytesIO()
        for user_id, audio in session.sink.audio_data.items():
            member = session.guild.get_member(user_id)
            if member and member.bot:
                continue
            if audio.file:
                audio.file.seek(0)
                combined.write(audio.file.read())
        
        return combined.getvalue() if combined.tell() > 0 else None

    async def _on_recording_done(self, sink, channel_id: int, *args):
        """Callback when recording stops. Must be async for py-cord."""
        pass

    async def _get_llm_response(self, session: InterviewSession, is_initial: bool = False) -> Optional[str]:
        """Get a response from the LLM via OpenRouter (non-streaming, for backward compat)."""
        full_text = ""
        async for sentence in self._stream_llm_sentences(session, is_initial=is_initial):
            full_text += sentence
        return full_text.strip() if full_text.strip() else None

    async def _stream_llm_sentences(self, session: InterviewSession, is_initial: bool = False):
        """
        Stream LLM response sentence-by-sentence via OpenRouter SSE.
        
        Yields complete sentences as soon as they're ready, so the caller
        can start TTS on the first sentence while later ones are still generating.
        """
        if not self.openrouter_key:
            logger.error("OpenRouter API key not configured")
            return
        
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                messages = session.conversation_history.copy()
                
                if is_initial:
                    messages.append({
                        "role": "user",
                        "content": f"[SYSTEM: A practice user named {session.applicant.display_name} is ready for their STAR practice session. Ask your first behavioral question. Remember to keep it short since this will be spoken aloud. Do NOT greet them - they've already been greeted.]"
                    })
                
                http = await self._get_http_session()
                async with http.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.openrouter_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.openrouter_model,
                        "messages": messages,
                        "max_tokens": 200,
                        "temperature": 0.7,
                        "stream": True,
                        "provider": {
                            "sort": "latency",
                            "preferred_max_latency": {"p90": 3.0},
                        },
                    },
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as response:
                    if response.status == 520 or response.status >= 500:
                        error = await response.text()
                        logger.warning(f"OpenRouter error {response.status} (attempt {attempt + 1}/{max_retries}): {error}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(1)
                            continue
                        return
                    
                    if response.status != 200:
                        error = await response.text()
                        logger.error(f"OpenRouter error {response.status}: {error}")
                        return
                    
                    # Stream SSE tokens and yield complete sentences
                    buffer = ""
                    full_response = ""
                    sentence_end_re = re.compile(r'[.!?]\s')
                    line_buffer = ""
                    
                    async for raw_chunk in response.content.iter_any():
                        line_buffer += raw_chunk.decode("utf-8", errors="ignore")
                        
                        # Process complete lines from the SSE stream
                        while "\n" in line_buffer:
                            line, line_buffer = line_buffer.split("\n", 1)
                            line = line.strip()
                            if not line.startswith("data: "):
                                continue
                            data_str = line[6:]
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data_str)
                                delta = chunk.get("choices", [{}])[0].get("delta", {})
                                token = delta.get("content", "")
                                if token:
                                    buffer += token
                                    full_response += token
                                    
                                    # Yield complete sentences as they form
                                    while sentence_end_re.search(buffer):
                                        match = sentence_end_re.search(buffer)
                                        sentence = buffer[:match.end()]
                                        buffer = buffer[match.end():]
                                        yield sentence
                            except (json.JSONDecodeError, IndexError, KeyError):
                                continue
                    
                    # Yield any remaining text
                    if buffer.strip():
                        yield buffer
                    
                    # Update conversation history with full response
                    if full_response.strip():
                        session.conversation_history.append({
                            "role": "assistant",
                            "content": full_response.strip()
                        })
                    
                    return  # Success, don't retry
                        
            except asyncio.TimeoutError:
                logger.warning(f"OpenRouter timeout (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    continue
                return
            except Exception as e:
                logger.error(f"LLM request failed: {e}")
                return

    def _clean_for_speech(self, text: str) -> str:
        """Remove roleplay actions, URLs, and other non-speech text for TTS."""
        cleaned = re.sub(r'https?://\S+', '', text)
        cleaned = re.sub(r'www\.\S+', '', cleaned)
        cleaned = re.sub(r'\S+\.(com|org|net|io|gg|co|dev|ai)\S*', '', cleaned)
        cleaned = re.sub(r'check out \S+', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'visit \S+', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\*[^*]+\*', '', cleaned)
        cleaned = re.sub(r'_[^_]+_', '', cleaned)
        cleaned = cleaned.replace('[INTERVIEW_COMPLETE]', '')
        cleaned = cleaned.replace('[PAUSE]', '')
        cleaned = re.sub(r'\[pause\]', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\[SYSTEM:[^\]]*\]', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\[NOTE:[^\]]*\]', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\[INTERNAL:[^\]]*\]', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\[THINKING:[^\]]*\]', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\[[A-Z][A-Z\s]*:[^\]]*\]', '', cleaned)
        cleaned = ' '.join(cleaned.split())
        return cleaned.strip()

    def _clean_for_display(self, text: str) -> str:
        """Remove URLs and control markers for display."""
        cleaned = re.sub(r'https?://\S+', '[link removed]', text)
        cleaned = re.sub(r'www\.\S+', '[link removed]', cleaned)
        cleaned = re.sub(r'\S+\.(com|org|net|io|gg|co|dev|ai)\S*', '[link removed]', cleaned)
        cleaned = cleaned.replace('[INTERVIEW_COMPLETE]', '')
        return cleaned.strip()

    async def _speak_and_display(self, session: InterviewSession, text: str, add_to_transcript: bool = True):
        """Speak the text via TTS and display in text channel."""
        if not text:
            return
        
        display_text = self._clean_for_display(text)
        
        if add_to_transcript:
            session.transcript_lines.append(f"[STARCoach]: {display_text}")
        
        if session.text_channel:
            try:
                embed = discord.Embed(
                    description=f"🎯 **STARCoach:** {display_text}",
                    color=0x5865F2
                )
                session_tag = f"Session #{session.interview_id} • " if session.interview_id else ""
                embed.set_footer(text=f"{session_tag}STAR Practice with {session.applicant.display_name}")
                await session.text_channel.send(embed=embed)
            except Exception as e:
                logger.error(f"Failed to send text: {e}")
        
        speech_text = self._clean_for_speech(text)
        
        session.is_speaking = True
        try:
            await self._speak(session, speech_text)
        finally:
            session.is_speaking = False

    async def _stream_and_speak(self, session: InterviewSession, is_initial: bool = False) -> Optional[str]:
        """
        Stream LLM response and speak sentences as they arrive.
        
        This pipelines LLM streaming → TTS → voice playback so the bot
        starts speaking the first sentence while later sentences are still
        being generated. Feels much more conversational.
        
        Returns the full response text, or None.
        """
        sentences = []
        full_text = ""
        first_sentence_spoken = False
        
        session.is_speaking = True
        try:
            async for sentence in self._stream_llm_sentences(session, is_initial=is_initial):
                full_text += sentence
                sentences.append(sentence)
                
                # Speak the first sentence immediately for low latency
                if not first_sentence_spoken:
                    first_sentence_spoken = True
                    # Send the embed to text channel with a placeholder
                    # (we'll have the full text for transcript after)
                    speech = self._clean_for_speech(sentence)
                    if speech.strip():
                        await self._speak(session, speech)
                else:
                    # Speak subsequent sentences as they arrive
                    speech = self._clean_for_speech(sentence)
                    if speech.strip():
                        await self._speak(session, speech)
        finally:
            session.is_speaking = False
        
        if not full_text.strip():
            return None
        
        # Display the complete message in text channel
        display_text = self._clean_for_display(full_text)
        session.transcript_lines.append(f"[STARCoach]: {display_text}")
        
        if session.text_channel:
            try:
                embed = discord.Embed(
                    description=f"🎯 **STARCoach:** {display_text}",
                    color=0x5865F2
                )
                session_tag = f"Session #{session.interview_id} • " if session.interview_id else ""
                embed.set_footer(text=f"{session_tag}STAR Practice with {session.applicant.display_name}")
                await session.text_channel.send(embed=embed)
            except Exception as e:
                logger.error(f"Failed to send text: {e}")
        
        return full_text.strip()

    async def _speak(self, session: InterviewSession, text: str):
        """Speak text in the voice channel using TTS — streams directly via pipe."""
        if not session.connection or not session.connection.is_connected():
            return
        
        try:
            audio_data = await self.tts.synthesize(text)
            if not audio_data:
                return
            
            # Stream MP3 bytes through FFmpeg via stdin pipe (no temp file)
            source = discord.FFmpegPCMAudio(
                io.BytesIO(audio_data),
                pipe=True,
            )
            
            if session.connection.is_playing():
                session.connection.stop()
            
            session.connection.play(source)
            
            while session.connection.is_playing():
                await asyncio.sleep(0.05)
                    
        except Exception as e:
            logger.error(f"Speech error: {e}")

    async def _complete_interview(self, session: InterviewSession):
        """Process completed practice session - analyze and post coaching report."""
        logger.info(f"_complete_interview called - report_sent: {session.report_sent}, transcript_lines: {len(session.transcript_lines)}")
        
        if session.report_sent:
            logger.info("Report already sent for this session, skipping")
            return
        session.report_sent = True
        
        transcript = "\n".join(session.transcript_lines)
        
        if not transcript.strip():
            logger.warning("Empty transcript, skipping analysis")
            return
        
        if len(session.transcript_lines) < 3:
            logger.warning(f"Transcript too short ({len(session.transcript_lines)} lines), skipping analysis")
            return
        
        logger.info(f"Processing transcript ({len(transcript)} chars)")
        
        # Save to database
        try:
            if session.interview_id:
                # Update the placeholder row created at session start
                await self.bot.db.update_interview_transcript(
                    interview_id=session.interview_id,
                    transcript=transcript,
                )
                interview_id = session.interview_id
            else:
                # Fallback: create a new row if pre-allocation failed
                interview_id = await self.bot.db.save_transcript(
                    applicant_id=session.applicant.id,
                    applicant_name=session.applicant.display_name,
                    guild_id=session.guild.id,
                    channel_name=session.channel.name,
                    transcript=transcript,
                    started_at=session.started_at,
                )
            logger.info(f"Saved transcript with ID: {interview_id}")
        except Exception as e:
            logger.error(f"Failed to save transcript: {e}")
            interview_id = session.interview_id
        
        # Analyze with STAR coaching analysis
        logger.info("Running STAR coaching analysis...")
        analysis = await self.analysis.analyze_transcript(transcript)
        
        if not analysis:
            logger.error("Analysis failed - no result returned")
            report_channel = self.bot.get_report_channel()
            if report_channel:
                await report_channel.send(f"⚠️ Practice session with **{session.applicant.display_name}** completed but coaching analysis failed. Check logs.")
            return
        
        logger.info(f"Analysis complete: readiness_score={analysis.get('readiness_score')}")
        
        # Save analysis
        if interview_id:
            try:
                await self.bot.db.save_analysis(interview_id, analysis)
                logger.info("Analysis saved to database")
            except Exception as e:
                logger.error(f"Failed to save analysis: {e}")
        
        # Post coaching report
        report_channel = self.bot.get_report_channel()
        logger.info(f"Report channel: {report_channel} (ID: {self.bot.report_channel_id})")
        
        if report_channel:
            try:
                embeds = create_report_embeds(
                    applicant=session.applicant,
                    analysis=analysis,
                    transcript_preview=transcript[:500],
                    fit_threshold=self.bot.fit_threshold,
                    interview_id=interview_id,
                )
                for embed in embeds:
                    await report_channel.send(embed=embed)
                logger.info(f"✅ Coaching report posted to #{report_channel.name} ({len(embeds)} embed(s))")
            except Exception as e:
                logger.error(f"Failed to post report: {e}", exc_info=True)
        else:
            logger.error(f"Report channel not found! ID: {self.bot.report_channel_id}")

    async def _handle_applicant_leave(self, applicant: discord.Member, channel: discord.VoiceChannel):
        """Handle user leaving mid-practice."""
        session = self.bot.active_sessions.get(channel.id)
        if not session or session.applicant.id != applicant.id:
            return
        
        logger.info(f"{applicant.display_name} left during practice")
        session.is_active = False
        
        if session.transcript_lines and len(session.transcript_lines) > 2:
            await self._complete_interview(session)
        
        await self._cleanup_session(session)

    async def _cleanup_session(self, session: InterviewSession):
        """Clean up a practice session."""
        try:
            if session.is_recording and session.connection:
                try:
                    session.connection.stop_recording()
                except:
                    pass
            
            if session.connection and session.connection.is_connected():
                await session.connection.disconnect()
            
            self.bot.active_sessions.pop(session.channel.id, None)
            logger.info(f"Cleaned up session for {session.channel.name}")
            
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

    @commands.command(name="endpractice")
    @commands.has_permissions(manage_channels=True)
    async def end_interview(self, ctx: commands.Context):
        """Manually end a practice session."""
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("❌ You must be in a voice channel.")
            return

        channel = ctx.author.voice.channel
        session = self.bot.active_sessions.get(channel.id)

        if not session:
            await ctx.send("❌ No active practice session in this channel.")
            return

        await ctx.send("⏹️ Ending practice session...")
        session.is_active = False
        session.interview_complete = True
        await ctx.send("✅ Practice session ended.")

    @commands.command(name="sessions")
    @commands.has_permissions(manage_channels=True)
    async def list_sessions(self, ctx: commands.Context):
        """List all active practice sessions."""
        if not self.bot.active_sessions:
            await ctx.send("📋 No active practice sessions.")
            return

        lines = ["**Active Practice Sessions:**"]
        for channel_id, session in self.bot.active_sessions.items():
            duration = (datetime.utcnow() - session.started_at).seconds // 60
            exchanges = len([m for m in session.conversation_history if m["role"] == "user"])
            lines.append(
                f"• **{session.channel.name}** - "
                f"{session.applicant.display_name} - "
                f"{exchanges} exchanges - {duration}m"
            )

        await ctx.send("\n".join(lines))

    @commands.command(name="testvoice")
    async def test_voice(self, ctx: commands.Context):
        """Test if voice cog is loaded."""
        tts_status = "✅" if self.tts.available else "❌"
        llm_status = "✅" if self.openrouter_key else "❌"
        await ctx.send(f"✅ STARCoach voice cog active!\n• Role: `{self.bot.applicant_role_name}`\n• TTS: {tts_status}\n• LLM: {llm_status}")


def setup(bot):
    """Load the Voice cog."""
    bot.add_cog(VoiceCog(bot))
    logger.info("Voice cog loaded - STAR Interview Coach ready")
