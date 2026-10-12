import json
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI()  # reads OPENAI_API_KEY from .env

MODEL = "gpt-5.4-nano"  # use the exact name shown in your OpenAI dashboard

def score_job(job, profile_text):
    prompt = f"""You are a job-matching assistant. Candidate profile:
{profile_text}

Job:
Title: {job['title']}
Company: {job['company']}
Location: {job['location']}
Description: {job['description'][:4000]}

Return ONLY JSON with these keys:
"score" (0-100), "reason" (max 2 sentences),
"matched_skills" (list), "red_flags" (list)."""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_completion_tokens=1000,
        )
        print("Tokens used:", response.usage.total_tokens)
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"Scoring failed: {e}")
        return {"score": 0, "reason": "scoring failed",
                "matched_skills": [], "red_flags": []}