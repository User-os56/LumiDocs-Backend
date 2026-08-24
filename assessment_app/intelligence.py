import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)


def clean_ai_response(response_text: str):
    """
    Clean Groq output and extract a JSON array.
    """

    if not response_text:
        return None

    cleaned = response_text.strip()

    # Remove markdown code fences
    if "```" in cleaned:
        cleaned = cleaned.replace("```json", "")
        cleaned = cleaned.replace("```", "")
        cleaned = cleaned.strip()

    # Find JSON array
    start = cleaned.find("[")
    end = cleaned.rfind("]")

    if start != -1 and end != -1 and end > start:

        array_str = cleaned[start:end + 1]

        try:
            parsed = json.loads(array_str)

            if isinstance(parsed, list):
                return parsed

        except json.JSONDecodeError:
            pass

    # Try parsing entire response
    try:

        parsed = json.loads(cleaned)

        if isinstance(parsed, list):
            return parsed

        if isinstance(parsed, dict):

            for key in [
                "questions",
                "items",
                "data",
                "results"
            ]:

                if key in parsed and isinstance(
                    parsed[key],
                    list
                ):
                    return parsed[key]

            if "question_text" in parsed:
                return [parsed]

    except json.JSONDecodeError:
        pass

    return None


def generate_questions_from_text(
    text: str,
    difficulty: str = "medium",
    num_questions: int = 10
) -> list:

    # ---------------------------------------------------------
    # Validate document text
    # ---------------------------------------------------------

    if not text or not text.strip():
        raise ValueError(
            "The uploaded document contains no readable text."
        )

    # ---------------------------------------------------------
    # Limit text sent to Groq
    # ---------------------------------------------------------

    truncated_text = text[:7000].strip()

    # ---------------------------------------------------------
    # Prompt
    # ---------------------------------------------------------

    prompt = f"""
You are an expert academic examiner.

Your task is to create a multiple-choice assessment
using ONLY the information contained in the uploaded
study material below.

IMPORTANT:
Do not use outside knowledge.
Do not invent facts.
Do not create questions about information that does
not appear in the document.

STUDY MATERIAL:
----------------
{truncated_text}
----------------

Generate exactly {num_questions} multiple-choice questions.

Difficulty:
{difficulty}

STRICT REQUIREMENTS:

1. Return ONLY a valid JSON array.
2. Do not return markdown.
3. Do not use code fences.
4. Do not include text before or after the JSON.
5. Generate exactly {num_questions} questions.
6. Every question must have exactly four options.
7. Options must use exactly these keys:
   "a", "b", "c", "d"
8. "correct_answer" must contain only:
   "a", "b", "c", or "d"
9. Every question must be answerable using the study material.
10. Do not introduce outside information.
11. Avoid duplicate questions.
12. Provide a short explanation for every answer.

Use exactly this structure:

[
  {{
    "question_text": "Question goes here",
    "options": {{
      "a": "Option A",
      "b": "Option B",
      "c": "Option C",
      "d": "Option D"
    }},
    "correct_answer": "a",
    "explanation": "Why the correct answer is correct, based on the study material."
  }}
]
"""

    # ---------------------------------------------------------
    # Call Groq
    # ---------------------------------------------------------

    try:
        
        print("========================================")
        print("STARTING GROQ QUESTION GENERATION")
        print("========================================")
        print(f"Model: openai/gpt-oss-120b")
        print(f"Requested questions: {num_questions}")
        print(f"Difficulty: {difficulty}")
        print(f"Document characters: {len(truncated_text)}")

        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",

            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert academic examiner. "
                        "Create multiple-choice questions strictly "
                        "from the supplied documents."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],

            temperature=0.5,
            max_tokens=2000,

            response_format={
                "type": "json_object"
            }
        )
        print("========================================")
        print("GROQ RESPONSE RECEIVED")
        print("========================================")

    except Exception as e:

        print(
            f"Groq API error: "
            f"{type(e).__name__}: {e}"
        )

        raise RuntimeError(
            "The AI service could not generate questions."
        ) from e

    # ---------------------------------------------------------
    # Read response
    # ---------------------------------------------------------

    content = response.choices[0].message.content
    
    print("Raw response:")
    print(content)

    if not content:
        raise RuntimeError(
            "The AI service returned an empty response."
        )
    parsed = clean_ai_response(content)

    

    

    print(
        f"Groq response received "
        f"({len(content)} characters)."
    )

    # ---------------------------------------------------------
    # Parse JSON
    # ---------------------------------------------------------

    parsed = clean_ai_response(content)

    if not isinstance(parsed, list):
        raise RuntimeError(
            "The AI returned an invalid question format."
        )
    print(f"Parsed questions: {len(parsed)}")

    # ---------------------------------------------------------
    # Validate questions
    # ---------------------------------------------------------

    valid_questions = []

    required_options = {
        "a",
        "b",
        "c",
        "d"
    }

    for question in parsed:

        if not isinstance(question, dict):
            continue

        if not all(
            key in question
            for key in [
                "question_text",
                "options",
                "correct_answer"
            ]
        ):
            continue

        question_text = str(
            question.get(
                "question_text",
                ""
            )
        ).strip()

        if not question_text:
            continue

        options = question.get("options")

        if not isinstance(options, dict):
            continue

        if set(options.keys()) != required_options:
            continue

        if any(
            not str(options[key]).strip()
            for key in required_options
        ):
            continue

        correct_answer = str(
            question.get(
                "correct_answer",
                ""
            )
        ).strip().lower()

        if correct_answer not in required_options:
            continue

        explanation = str(
            question.get(
                "explanation",
                ""
            )
        ).strip()

        valid_questions.append({
            "question_text": question_text,

            "options": {
                "a": str(options["a"]).strip(),
                "b": str(options["b"]).strip(),
                "c": str(options["c"]).strip(),
                "d": str(options["d"]).strip()
            },

            "correct_answer": correct_answer,

            "explanation": explanation
        })

    # ---------------------------------------------------------
    # Ensure enough questions were generated
    # ---------------------------------------------------------

    if len(valid_questions) < num_questions:

        raise RuntimeError(
            f"AI generated only "
            f"{len(valid_questions)} valid questions "
            f"out of {num_questions} requested."
        )

    return valid_questions[:num_questions]