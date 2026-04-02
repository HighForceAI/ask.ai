"""
ask.ai demo — run 6 prompts across different skills and providers.

Start the server first:  uvicorn api.main:app --reload
Then run:                python demo.py
"""

from sdk import AskAI

PROMPTS = [
    "Review this pricing page copy: 'We offer solutions for businesses of all sizes. Contact us for pricing.' — why is conversion low?",
    "Our MRR dropped 12% last month but we added 30 new customers. What's going on?",
    "Review this Python function:\ndef get_user(id):\n    return db.execute(f'SELECT * FROM users WHERE id = {id}')",
    "We're choosing between Postgres and MongoDB for a new event-sourcing system. Team knows SQL. 50M events/day.",
    "Analyze this NDA clause: 'Receiving party shall not disclose Confidential Information for a period of perpetuity.'",
    "Should we raise a seed round now at $8M pre or wait 3 months for better metrics?",
]

def main():
    client = AskAI(api_key="dev-key-123", base_url="http://localhost:8000")

    for i, prompt in enumerate(PROMPTS, 1):
        print(f"\n{'='*70}")
        print(f"PROMPT {i}: {prompt[:80]}...")
        print(f"{'='*70}")

        result = client.ask(prompt)

        print(f"\nSkill:    {result.skill_used}")
        print(f"Model:    {result.model_used}")
        print(f"Reviewed: {result.reviewed}")
        print(f"Cost:     ${result.cost_usd:.4f}")
        print(f"Route:    {result.classifier.industry}/{result.classifier.task_type} "
              f"[{result.classifier.complexity}/{result.classifier.risk}]")
        print(f"Why:      {result.classifier.reasoning}")
        print(f"\n{result.answer[:500]}...")
        print()


if __name__ == "__main__":
    main()
