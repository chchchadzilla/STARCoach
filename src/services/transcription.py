"""
Transcription Service - Deepgram integration for audio transcription.

Uses Deepgram's REST API directly for audio transcription.
"""

import logging
import os
import aiohttp
from typing import Optional

logger = logging.getLogger("starcoach.transcription")


class TranscriptionService:
    """
    Service for transcribing audio using Deepgram's REST API.
    """

    def __init__(self):
        self.api_key = os.getenv("DEEPGRAM_API_KEY")
        if not self.api_key:
            logger.warning("DEEPGRAM_API_KEY not set - transcription will fail!")
        
        self.base_url = "https://api.deepgram.com/v1/listen"
        logger.info("TranscriptionService initialized")

    async def transcribe_audio(self, audio_data: bytes, mimetype: str = "audio/wav", http_session: "aiohttp.ClientSession | None" = None) -> Optional[dict]:
        """
        Transcribe audio data using Deepgram's REST API.
        
        Args:
            audio_data: Raw audio bytes
            mimetype: Audio MIME type (default: audio/wav)
            http_session: Optional shared aiohttp session for connection reuse
            
        Returns:
            Dictionary with transcript and segments, or None on error
        """
        if not self.api_key:
            logger.error("Deepgram API key not configured")
            return None
        
        if not audio_data:
            logger.warning("No audio data provided for transcription")
            return None
        
        try:
            headers = {
                "Authorization": f"Token {self.api_key}",
                "Content-Type": mimetype,
            }
            
            params = {
                "model": "nova-2",
                "language": "en",
                "smart_format": "true",
                "diarize": "true",
                "punctuate": "true",
                "utterances": "true",
            }
            
            # Use provided session or create a new one
            if http_session and not http_session.closed:
                async with http_session.post(
                    self.base_url,
                    headers=headers,
                    params=params,
                    data=audio_data,
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Deepgram API error {response.status}: {error_text}")
                        return None
                    result = await response.json()
            else:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        self.base_url,
                        headers=headers,
                        params=params,
                        data=audio_data,
                    ) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            logger.error(f"Deepgram API error {response.status}: {error_text}")
                            return None
                        result = await response.json()
            
            return self._parse_response(result)
            
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return None

    def _parse_response(self, result: dict) -> Optional[dict]:
        """Parse Deepgram API response into our standard format."""
        try:
            parsed = {
                "transcript": "",
                "segments": [],
                "speakers": set(),
            }
            
            if "results" not in result:
                return None
            
            results = result["results"]
            
            if "utterances" in results and results["utterances"]:
                for utterance in results["utterances"]:
                    speaker = f"Speaker {utterance.get('speaker', 0)}"
                    parsed["speakers"].add(speaker)
                    parsed["segments"].append({
                        "speaker": speaker,
                        "text": utterance.get("transcript", ""),
                        "start": utterance.get("start", 0),
                        "end": utterance.get("end", 0),
                        "confidence": utterance.get("confidence", 0),
                    })
                    parsed["transcript"] += f"[{speaker}]: {utterance.get('transcript', '')}\n"
            
            elif "channels" in results and results["channels"]:
                channel = results["channels"][0]
                if "alternatives" in channel and channel["alternatives"]:
                    parsed["transcript"] = channel["alternatives"][0].get("transcript", "")
            
            parsed["speakers"] = list(parsed["speakers"])
            
            logger.info(f"Transcription successful: {len(parsed['transcript'])} chars")
            return parsed
            
        except Exception as e:
            logger.error(f"Error parsing Deepgram response: {e}")
            return None
