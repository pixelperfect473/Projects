import os
import json
import shutil
from openai import OpenAI

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

ai_instructions = """You are an expert QA Analyst for a customer support center. Your task is to analyze the provided phone call transcript between an agent and a customer, extract key metrics, and calculate a final weighted Productivity Score.

Strictly adhere to the following definitions, rubrics, and formulas.

### ANALYSIS CRITERIA

1. Topic: Identify the primary purpose or reason the call was initiated.
2. Sentiment: Determine the overall emotional tone of the call. Choose exactly ONE of these values: "Friendly", "Formal", "Confusing", "Aggressive", "Frustrated".
3. Service Score: Rate how well the agent communicated (clarity, active listening, helpfulness) on a scale from 1 (poor) to 5 (excellent).
4. Policy Adherence: Check if the agent made unauthorized account modifications.
   - Rule: The agent is ONLY allowed to set up a "Promise to Pay" (PTP). They are strictly forbidden from moving payment dates or extending payments without manager approval.
   - Output "true" if they complied with this rule. Output "false" if they made any other unauthorized changes.
5. Interruption Count: Count the exact number of times the agent spoke over or cut off the customer mid-sentence.

### PRODUCTIVITY SCORE CALCULATION (Weighted)
Calculate the final score out of 100 based on the following weights:

1. Policy Adherence (30% / 30 points):
   - 30 points if Policy Adherence is true.
   - 0 points if Policy Adherence is false.

2. Sentiment (30% / 30 points):
   - 30 points: "Friendly" or "Formal"
   - 15 points: "Confusing"
   - 0 points: "Aggressive" or "Frustrated"

3. Outcome Resolution (30% / 30 points):
   - Assess if the customer's core issue was resolved during the call.
   - 30 points: Issue fully resolved or next clear steps/PTP successfully established.
   - 15 points: Issue partially resolved or pending manager approval.
   - 0 points: Issue unresolved, or hung up without resolution.

4. Politeness & Interruptions (10% / 10 points):
   - Start with 10 points. 
   - Deduct 2 points for every interruption count. (Floor of 0 points).

Formula:
Productivity Score = [Policy Adherence Points] + [Sentiment Points] + [Outcome Points] + [Politeness Points]

Provide a brief, 1-2 sentence justification for how you calculated each sub-score."""

response_schema = {
    "name": "call_analysis",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "description": "The primary reason or purpose of the call."
            },
            "sentiment": {
                "type": "string",
                "enum": ["Friendly", "Formal", "Confusing", "Aggressive", "Frustrated"],
                "description": "The overall mood/tone of the call."
            },
            "service_score": {
                "type": "integer",
                "minimum": 1,
                "maximum": 5,
                "description": "Agent communication quality from 1 (poor) to 5 (excellent)."
            },
            "policy_adherence": {
                "type": "boolean",
                "description": "True if agent only set up a promise to pay. False if they moved/extended payments or made other unauthorized changes."
            },
            "interruption_count": {
                "type": "integer",
                "minimum": 0,
                "description": "Number of times the agent interrupted the customer."
            },
            "scoring_breakdown": {
                "type": "object",
                "properties": {
                    "policy_adherence_points": {"type": "integer", "enum": [0, 30]},
                    "sentiment_points": {"type": "integer", "enum": [0, 15, 30]},
                    "outcome_points": {"type": "integer", "enum": [0, 15, 30]},
                    "politeness_points": {"type": "integer", "minimum": 0, "maximum": 10},
                    "justification": {
                        "type": "string",
                        "description": "Brief 1-2 sentence breakdown of how these points were assigned."
                    }
                },
                "required": ["policy_adherence_points", "sentiment_points", "outcome_points", "politeness_points", "justification"],
                "additionalProperties": False
            },
            "final_productivity_score": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
                "description": "The sum of the four scoring breakdown categories."
            }
        },
        "required": [
            "topic",
            "sentiment",
            "service_score",
            "policy_adherence",
            "interruption_count",
            "scoring_breakdown",
            "final_productivity_score"
        ],
        "additionalProperties": False
    }
}

# Folder setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIALOGUE_DIR = os.path.join(BASE_DIR, "dialogue")
RESULTS_DIR = os.path.join(BASE_DIR, "results")
PROCESSED_DIR = os.path.join(BASE_DIR, "processed")

os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)

def process_transcript(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        transcript_text = f.read()

    response = client.responses.create(
        model="gpt-5.6",  
        instructions=ai_instructions,
        text={
            "format": {
                "type": "json_schema",
                **response_schema
            }
        },
        input=transcript_text
    )

    return response.output_text


def get_analysis():
    txt_files = [f for f in os.listdir(DIALOGUE_DIR) if f.lower().endswith(".txt")]

    if not txt_files:
        print(f"No .txt files found in {DIALOGUE_DIR}")
        return

    for filename in txt_files:
        filepath = os.path.join(DIALOGUE_DIR, filename)
        print(f"Processing: {filename}")

        try:
            output_text = process_transcript(filepath)

           
            parsed = json.loads(output_text)

            result_filename = os.path.splitext(filename)[0] + ".json"
            result_path = os.path.join(RESULTS_DIR, result_filename)
            with open(result_path, "w", encoding="utf-8") as out_f:
                json.dump(parsed, out_f, indent=2, ensure_ascii=False)

            # Move processed transcript
            shutil.move(filepath, os.path.join(PROCESSED_DIR, filename))

            print(f"  -> Saved result to {result_path}")
            print(f"  -> Moved transcript to {PROCESSED_DIR}")

        except Exception as e:
            print(f"  !! Error processing {filename}: {e}")
            # Leave the file in dialogue/ so it can be retried

if __name__ == "__main__":
    get_analysis()