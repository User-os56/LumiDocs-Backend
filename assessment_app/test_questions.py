import json
import os
import sys

# Fix path so it can find intelligence.py
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from intelligence import generate_question_batch

print("=== Testing Question Generation ===\n")

questions = generate_question_batch(
    start_step=1,
    current_theta=0.0,
    batch_size=5
)

print(f"✅ Successfully generated {len(questions)} questions\n")

if questions:
    print("First question preview:")
    print(json.dumps(questions[0], indent=2))
    print("\nSecond question preview:")
    print(json.dumps(questions[1], indent=2))
    print("\nThird question preview:")
    print(json.dumps(questions[2], indent=2))
else:
    print("❌ No questions generated!")