"""
Text-to-Speech Service - Generate spoken audio for the practice coach.

Uses edge-tts for high-quality, free text-to-speech.
"""

import logging
import io
import asyncio
from typing import Optional

logger = logging.getLogger("starcoach.tts")

# Try to import edge_tts, fall back gracefully
try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False
    logger.warning("edge-tts not installed - TTS will be disabled. Install with: pip install edge-tts")


class TTSService:
    """
    Text-to-Speech service using Microsoft Edge TTS.
    """
    
    VOICES = {
        "female_us": "en-US-JennyNeural",
        "male_us": "en-US-GuyNeural",
        "female_uk": "en-GB-SoniaNeural",
        "male_uk": "en-GB-RyanNeural",
    }
    
    def __init__(self, voice: str = "female_us"):
        self.voice = self.VOICES.get(voice, self.VOICES["female_us"])
        self.available = EDGE_TTS_AVAILABLE
        
        if self.available:
            logger.info(f"TTS initialized with voice: {self.voice}")
        else:
            logger.warning("TTS service unavailable - edge-tts not installed")
    
    async def synthesize(self, text: str) -> Optional[bytes]:
        """Convert text to speech audio (MP3 bytes)."""
        if not self.available:
            logger.warning("TTS not available, skipping synthesis")
            return None
        
        try:
            communicate = edge_tts.Communicate(text, self.voice)
            
            audio_data = io.BytesIO()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data.write(chunk["data"])
            
            audio_bytes = audio_data.getvalue()
            logger.debug(f"Synthesized {len(audio_bytes)} bytes of audio")
            return audio_bytes
            
        except Exception as e:
            logger.error(f"TTS synthesis failed: {e}")
            return None
    
    async def synthesize_to_file(self, text: str, filepath: str) -> bool:
        """Convert text to speech and save to file."""
        if not self.available:
            return False
        
        try:
            communicate = edge_tts.Communicate(text, self.voice)
            await communicate.save(filepath)
            logger.debug(f"Saved TTS audio to {filepath}")
            return True
        except Exception as e:
            logger.error(f"Failed to save TTS audio: {e}")
            return False


# Singleton instance
_tts_service: Optional[TTSService] = None

def get_tts_service(voice: str = "female_us") -> TTSService:
    """Get or create the TTS service singleton."""
    global _tts_service
    if _tts_service is None:
        _tts_service = TTSService(voice)
    return _tts_service
