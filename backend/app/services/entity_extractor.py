"""
Entity and Relationship Extraction using OpenAI
"""

from typing import List, Dict
from openai import AsyncOpenAI
from core.config import settings
import json
import structlog

logger = structlog.get_logger()

openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


class EntityExtractor:
    """Extract entities and relationships from text"""
    
    @staticmethod
    async def extract_from_text(text: str) -> Dict:
        """Extract entities and relationships using GPT-4"""
        
        prompt = f"""Extract entities and relationships from the following text.

Text:
{text[:3000]}  # Limit to avoid token limits

Return a JSON object with:
1. "entities": list of objects with "name" and "type" (Person, Organization, Location, Concept, etc.)
2. "relationships": list of objects with "from", "to", and "type" (describes the relationship)

Example:
{{
  "entities": [
    {{"name": "Albert Einstein", "type": "Person"}},
    {{"name": "Theory of Relativity", "type": "Concept"}}
  ],
  "relationships": [
    {{"from": "Albert Einstein", "to": "Theory of Relativity", "type": "DEVELOPED"}}
  ]
}}

Only return valid JSON, no other text."""

        response = await openai_client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {"role": "system", "content": "You are an expert at extracting structured information from text."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        
        logger.info("Entities extracted", 
                   entities=len(result.get('entities', [])),
                   relationships=len(result.get('relationships', [])))
        
        return result