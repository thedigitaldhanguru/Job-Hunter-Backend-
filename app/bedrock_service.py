import os
import json
import base64
import urllib.parse
import httpx
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class BedrockResumeExtractor:
    def __init__(self):
        self.use_bedrock = os.getenv("USE_BEDROCK", "false").lower() == "true"
        self.bedrock_api_key_raw = os.getenv("BEDROCK_API_KEY", "").strip()
        self.bedrock_api_key = self.bedrock_api_key_raw
        self.model_id = os.getenv("BEDROCK_MODEL_ID", "apac.amazon.nova-lite-v1:0")
        
        if self.use_bedrock and self.bedrock_api_key:
            logger.info(f"✓ Bedrock initialized with Amazon Nova Lite model")
        elif self.use_bedrock:
            logger.warning("❌ USE_BEDROCK=true but BEDROCK_API_KEY invalid. Falling back to regex.")
            self.use_bedrock = False

    async def extract_with_bedrock(self, resume_text: str) -> Optional[Dict[str, Any]]:
        """Extract resume fields using Amazon Nova Lite via AWS Bedrock Bearer Token"""
        
        if not self.use_bedrock or not self.bedrock_api_key:
            return None
            
        prompt = f"""Extract the following information from this resume text. Reply with ONLY valid JSON, no markdown code blocks, no extra text.
Keep employment and project descriptions concise. Summarize long bullet points into a maximum of 3 sentences.

Resume text:
{resume_text}

Return JSON with these exact fields (use null for missing fields/arrays):
{{
    "name": "full name",
    "email": "email address",
    "phone": "phone number",
    "location": "city/location",
    "degree": "degree name (e.g., B.Tech)",
    "university": "university name",
    "experience_years": "years of experience",
    "summary": "professional summary (max 200 words)",
    "skills": ["skill1", "skill2", "skill3"],
    "languages": ["language1", "language2"],
    "linkedin": "linkedin profile url",
    "github": "github profile url",
    "portfolio": "portfolio website url",
    "employment": [
        {{ "company": "company name", "title": "job title", "duration": "e.g., Jan 2020 - Present", "description": "brief description of work" }}
    ],
    "education": [
        {{ "institution": "institution name", "degree": "degree obtained", "details": "e.g., Graduated 2020" }}
    ],
    "projects": [
        {{ "title": "project title", "duration": "e.g., Jan 2021", "description": "brief description" }}
    ],
    "accomplishments": ["award or certification 1", "award 2"]
}}

Return ONLY the JSON object. No markdown, no code blocks."""

        try:
            url = f"https://bedrock-runtime.ap-south-1.amazonaws.com/model/{self.model_id}/invoke"
            headers = {
                "Authorization": f"Bearer {self.bedrock_api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "messages": [{"role": "user", "content": [{"text": prompt}]}],
                "inferenceConfig": {"maxTokens": 2048, "temperature": 0.3, "topP": 0.9}
            }
            
            async with httpx.AsyncClient(timeout=120.0, verify=False) as client:
                response = await client.post(url, headers=headers, json=payload)
                
                if response.status_code != 200:
                    logger.warning(f"Bedrock API error: {response.status_code} - {response.text} - will use regex fallback")
                    return None
                
                response_data = response.json()
                output_text = ""
                
                # Extract text from Bedrock response
                if "output" in response_data:
                    output_text = response_data["output"].get("message", {}).get("content", [{}])[0].get("text", "")
                elif "content" in response_data:
                    output_text = response_data["content"][0].get("text", "")
                
                if not output_text:
                    logger.warning("Empty response from Bedrock")
                    return None
                
                output_text = output_text.strip()
                if output_text.startswith("```json"):
                    output_text = output_text[7:]
                elif output_text.startswith("```"):
                    output_text = output_text[3:]
                if output_text.endswith("```"):
                    output_text = output_text[:-3]
                output_text = output_text.strip()
                
                # Try to parse JSON from response
                extracted = json.loads(output_text)
                logger.info("✓ Successfully extracted resume with Amazon Nova Lite")
                return extracted
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse Bedrock response as JSON: {e}")
            return None
        except (httpx.NetworkError, httpx.ConnectError) as e:
            logger.warning(f"Bedrock network error (will use regex fallback): {type(e).__name__}")
            return None
        except Exception as e:
            logger.warning(f"Bedrock extraction failed (will use regex fallback): {type(e).__name__}")
            return None

    def is_available(self) -> bool:
        """Check if Bedrock is available and configured"""
        return self.use_bedrock and bool(self.bedrock_api_key)


# Initialize global instance
bedrock_extractor = BedrockResumeExtractor()
