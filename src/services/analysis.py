"""
Analysis Service - AI-powered STAR coaching analysis via OpenRouter.

Analyzes practice interview transcripts and provides coaching feedback
on STAR method usage, identifying strengths and areas for improvement.
"""

import os
import json
import logging
import asyncio
from typing import Optional

import aiohttp

logger = logging.getLogger("starcoach.analysis")

# STAR Coaching Analysis Prompt
ANALYSIS_PROMPT = """You are an expert interview coach specializing in the STAR method (Situation, Task, Action, Result). You're reviewing a practice interview session to provide coaching feedback.

**CRITICAL - READ FIRST:**
The transcript contains TWO speakers:
- Lines starting with [STARCoach]: are the AI COACH asking questions - IGNORE THESE for scoring
- Lines starting with any other name are the PRACTICE USER's responses - ONLY ANALYZE THESE

You are coaching the PRACTICE USER. Evaluate how well they used the STAR method in their answers.

**THE STAR METHOD:**
- **Situation (S)**: Did they clearly set the scene? Context, background, when/where?
- **Task (T)**: Did they explain their specific role/responsibility in the situation?
- **Action (A)**: Did they describe the concrete steps THEY personally took?
- **Result (R)**: Did they share the outcome, impact, or what they learned?

**YOUR COACHING TASK:**
Analyze each of the user's answers and rate how well they applied each STAR component.

Score these dimensions (1-10 each):
1. **Situation Clarity** (1-10): How well do they set the scene and provide context?
2. **Task Definition** (1-10): How clearly do they explain their specific responsibility?
3. **Action Detail** (1-10): How specific are they about the steps THEY took? Do they use "I" vs "we"?
4. **Result Impact** (1-10): Do they quantify outcomes? Share lessons learned?
5. **Overall Structure** (1-10): How naturally do they organize their answers in STAR format?
6. **Storytelling** (1-10): Are their answers engaging, concise, and memorable?

**TRANSCRIPT:**
{transcript}

**COACHING STANDARD:**
A strong STAR answer hits all four components naturally, uses specific examples with details (numbers, names, timeframes), focuses on personal contributions (not just team outcomes), and ends with a measurable result or clear lesson learned.

**OUTPUT FORMAT:**
Return ONLY valid JSON with this exact structure:
{{
    "scores": {{
        "situation_clarity": <1-10>,
        "task_definition": <1-10>,
        "action_detail": <1-10>,
        "result_impact": <1-10>,
        "overall_structure": <1-10>,
        "storytelling": <1-10>
    }},
    "readiness_score": <1-100 overall interview readiness>,
    "star_breakdown": [
        {{
            "question_topic": "Brief description of the question",
            "components_present": ["S", "T", "A", "R"],
            "components_missing": ["T"],
            "feedback": "Brief coaching note for this specific answer"
        }}
    ],
    "strengths": ["strength1", "strength2", "strength3"],
    "improvement_areas": ["area1", "area2", "area3"],
    "coaching_tips": [
        "Specific, actionable tip for improving their STAR answers",
        "Another concrete tip they can practice",
        "A third tip with an example of what to say"
    ],
    "example_improvements": {{
        "weakest_answer_topic": "The topic of their weakest answer",
        "original_approach": "Brief summary of what they said",
        "suggested_approach": "How they could restructure it using STAR"
    }},
    "overall_feedback": "2-3 sentences of encouraging, constructive coaching feedback",
    "readiness_level": "<INTERVIEW_READY|ALMOST_READY|NEEDS_PRACTICE|EARLY_STAGE>",
    "next_steps": "1-2 sentences on what to focus on in their next practice session"
}}"""


class AnalysisService:
    """
    Service for analyzing STAR practice sessions using AI.
    
    Provides coaching feedback on STAR method usage.
    """

    def __init__(self):
        self.openrouter_key = os.getenv("OPENROUTER_API_KEY")
        # Use Claude Sonnet 4.5 for deeper coaching analysis
        self.openrouter_model = os.getenv(
            "ANALYSIS_MODEL",
            "google/gemini-3-flash-preview",
        )
        
        if not self.openrouter_key:
            logger.warning("OPENROUTER_API_KEY not set - coaching analysis unavailable")

    async def analyze_transcript(self, transcript: str) -> Optional[dict]:
        """
        Analyze a practice transcript and return coaching feedback.
        
        Args:
            transcript: Full practice transcript with speaker labels
            
        Returns:
            Coaching analysis result dict or None
        """
        if not transcript or not transcript.strip():
            logger.warning("Empty transcript provided")
            return None

        logger.info("Analyzing transcript via OpenRouter...")
        result = await self._analyze_openrouter(transcript)
        
        if result:
            logger.info("STAR coaching analysis successful")
            return result

        logger.error("Analysis failed")
        return None

    async def _analyze_openrouter(self, transcript: str) -> Optional[dict]:
        """Analyze transcript using OpenRouter API with retry logic."""
        if not self.openrouter_key:
            logger.error("OpenRouter API key not configured")
            return None

        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                prompt = ANALYSIS_PROMPT.format(transcript=transcript)

                async with aiohttp.ClientSession() as session:
                    payload = {
                        "model": self.openrouter_model,
                        "messages": [
                            {
                                "role": "user",
                                "content": prompt,
                            }
                        ],
                        "temperature": 0.3,
                        "max_tokens": 4096,
                    }

                    headers = {
                        "Authorization": f"Bearer {self.openrouter_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": os.getenv("APP_URL", "https://starcoach.local"),
                        "X-Title": "STARCoach Practice Analysis",
                    }

                    async with session.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        json=payload,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=60),
                    ) as response:
                        if response.status == 520 or response.status >= 500:
                            error_text = await response.text()
                            logger.warning(f"OpenRouter error {response.status} (attempt {attempt + 1}/{max_retries}): {error_text[:200]}")
                            if attempt < max_retries - 1:
                                await asyncio.sleep(2 ** attempt)
                                continue
                            return None
                        
                        if response.status != 200:
                            error_text = await response.text()
                            logger.error(f"OpenRouter API error {response.status}: {error_text}")
                            return None

                        data = await response.json()
                        response_text = data["choices"][0]["message"]["content"]
                        
                        try:
                            if "```json" in response_text:
                                json_str = response_text.split("```json")[1].split("```")[0]
                            elif "```" in response_text:
                                json_str = response_text.split("```")[1].split("```")[0]
                            else:
                                json_str = response_text

                            json_str = json_str.strip()
                            
                            start_idx = json_str.find('{')
                            if start_idx != -1:
                                depth = 0
                                end_idx = start_idx
                                for i, char in enumerate(json_str[start_idx:], start_idx):
                                    if char == '{':
                                        depth += 1
                                    elif char == '}':
                                        depth -= 1
                                        if depth == 0:
                                            end_idx = i
                                            break
                                json_str = json_str[start_idx:end_idx + 1]

                            result = json.loads(json_str)
                            return self._normalize_result(result)

                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to parse response as JSON: {e}")
                            logger.error(f"Response: {response_text[:500]}...")
                            if attempt < max_retries - 1:
                                await asyncio.sleep(2 ** attempt)
                                continue
                            return None

            except aiohttp.ClientError as e:
                logger.warning(f"OpenRouter connection error (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                return None
            except Exception as e:
                logger.error(f"Analysis error: {e}")
                return None
        
        return None

    def _normalize_result(self, data: dict) -> dict:
        """Normalize coaching analysis result to ensure consistent structure."""
        
        # Map readiness level for backward compatibility
        readiness_map = {
            "INTERVIEW_READY": True,
            "ALMOST_READY": True,
            "NEEDS_PRACTICE": False,
            "EARLY_STAGE": False,
        }
        
        raw_readiness = data.get("readiness_level", "NEEDS_PRACTICE")
        recommended = readiness_map.get(raw_readiness, False)

        normalized = {
            "scores": data.get("scores", {}),
            "readiness_score": data.get("readiness_score", 0),
            # Map to fit_score for database compatibility
            "fit_score": data.get("readiness_score", 0),
            "star_breakdown": data.get("star_breakdown", []),
            "strengths": data.get("strengths", []),
            "improvement_areas": data.get("improvement_areas", []),
            # Map improvement_areas to concerns for database compatibility
            "concerns": data.get("improvement_areas", []),
            "coaching_tips": data.get("coaching_tips", []),
            "example_improvements": data.get("example_improvements", {}),
            "overall_feedback": data.get("overall_feedback", ""),
            # Map to summary for database compatibility
            "summary": data.get("overall_feedback", "No feedback available."),
            "readiness_level": raw_readiness,
            # Map to recommendation for database compatibility
            "recommendation": raw_readiness,
            "next_steps": data.get("next_steps", ""),
            # Compatibility fields
            "red_flags": [],
            "evidence_quotes": {"positive": [], "negative": []},
            "psychological_profile": "",
            "culture_alignment": "",
            "recommendation_reasoning": data.get("next_steps", ""),
            "recommended": recommended,
        }

        # Ensure readiness_score is an integer
        if isinstance(normalized["readiness_score"], str):
            try:
                normalized["readiness_score"] = int(normalized["readiness_score"])
                normalized["fit_score"] = normalized["readiness_score"]
            except ValueError:
                normalized["readiness_score"] = 50
                normalized["fit_score"] = 50

        # Ensure lists are actually lists
        for key in ["strengths", "concerns", "improvement_areas", "coaching_tips"]:
            if not isinstance(normalized[key], list):
                normalized[key] = [normalized[key]] if normalized[key] else []

        # Calculate readiness_score from individual scores if not provided
        if normalized["readiness_score"] == 0 and normalized["scores"]:
            scores = normalized["scores"]
            if scores:
                avg = sum(scores.values()) / len(scores)
                normalized["readiness_score"] = int(avg * 10)
                normalized["fit_score"] = normalized["readiness_score"]

        return normalized
