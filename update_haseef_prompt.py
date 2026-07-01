#!/usr/bin/env python3
"""Update Haseef's cloud system prompt to fix show_expression tool description
and emotion names to match the actual library (81 emotions with number suffixes)."""
import asyncio
import os
import re

from dotenv import load_dotenv
from hsafa_sdk import HsafaSDK, SdkOptions

load_dotenv()

# The correct show_expression tool description for the prompt
NEW_EXPRESSION_TOOL = """- show_expression(emotion): Show an animated emotion clip with head
  motion and sound. The robot plays the clip at its natural duration.
  You MUST call this tool when the user asks to show an emotion.
  Valid emotion names (use EXACT name with number suffix):
  amazed1, anxiety1, attentive1, attentive2, boredom1, boredom2,
  calming1, cheerful1, come1, confused1, contempt1, curious1,
  dance1, dance2, dance3, disgusted1, displeased1, displeased2,
  downcast1, dying1, electric1, enthusiastic1, enthusiastic2,
  exhausted1, fear1, frustrated1, furious1, go_away1, grateful1,
  helpful1, helpful2, impatient1, impatient2, indifferent1,
  inquiring1, inquiring2, inquiring3, irritated1, irritated2,
  laughing1, laughing2, lonely1, lost1, loving1, no1, no_excited1,
  no_sad1, oops1, oops2, proud1, proud2, proud3, rage1, relief1,
  relief2, reprimand1, reprimand2, reprimand3, resigned1, sad1,
  sad2, scared1, serenity1, shy1, sleep1, success1, success2,
  surprised1, surprised2, thoughtful1, thoughtful2, tired1,
  uncertain1, uncomfortable1, understanding1, understanding2,
  welcoming1, welcoming2, yes1, yes_sad1.
  Common mappings: angry→furious1, happy→cheerful1, sad→sad1,
  surprised→surprised1, scared→scared1, tired→tired1, bored→boredom1,
  calm→calming1, confused→confused1, proud→proud1, laughing→laughing1.
  IMPORTANT: When the task is ONLY to show an emotion, call show_expression
  and do NOT call say_this. Gemini already spoke to the user — no extra
  speech is needed. Just play the emotion and finish."""


async def main():
    sdk = HsafaSDK(SdkOptions(
        core_url=os.environ["HSAFA_CORE_URL"],
        api_key=os.environ["HSAFA_CORE_KEY"],
        skill="robot_base",
    ))
    hid = os.environ["HASEEF_ID"]
    h = await sdk.haseef.get(hid)
    cfg = h.get("configJson", {})
    prompt = cfg.get("system_prompt", "")

    # Replace the old show_expression tool description with the new one
    # Match from "- show_expression(" to the next "- " tool or "\n\n==="
    pattern = r"- show_expression\(.*?(?=\n- |\n\n===)"
    prompt = re.sub(pattern, NEW_EXPRESSION_TOOL, prompt, flags=re.DOTALL, count=1)

    # Replace old emotion examples with correct ones
    old_examples = [
        (r'Task: "Show emotion happy"\nAction: call show_expression\(emotion="happy"\)',
         'Task: "Show emotion happy"\nAction: call show_expression(emotion="cheerful1")'),
        (r'Task: "Show emotion sad"\nAction: call show_expression\(emotion="sad"\)',
         'Task: "Show emotion sad"\nAction: call show_expression(emotion="sad1")'),
        (r'Task: "Look surprised"\nAction: call show_expression\(emotion="surprised"\)',
         'Task: "Look surprised"\nAction: call show_expression(emotion="surprised1")'),
    ]
    for old, new in old_examples:
        prompt = re.sub(old, new, prompt)

    # Add angry example if not present
    if "angry" not in prompt.lower() or "furious1" not in prompt:
        # Add after the surprised example
        prompt = prompt.replace(
            'Task: "Look surprised"\nAction: call show_expression(emotion="surprised1")',
            'Task: "Look surprised"\nAction: call show_expression(emotion="surprised1")\n\n'
            'Task: "Show anger" or "Be angry"\n'
            'Action: call show_expression(emotion="furious1")\n\n'
            'Task: "Be happy" or "Show me happy"\n'
            'Action: call show_expression(emotion="cheerful1")\n\n'
            'Task: "Look sad"\n'
            'Action: call show_expression(emotion="sad1")\n\n'
            'Task: "Be scared"\n'
            'Action: call show_expression(emotion="scared1")\n\n'
            'Task: "Dance"\n'
            'Action: call show_expression(emotion="dance1")\n\n'
            'Task: "Go to sleep"\n'
            'Action: call show_expression(emotion="sleep1")'
        )

    cfg["system_prompt"] = prompt
    cfg["max_tokens"] = 4096

    result = await sdk.haseef.update(hid, {"configJson": cfg})
    new_cfg = result.get("configJson", {})
    new_prompt = new_cfg.get("system_prompt", "")
    print("OK - prompt length:", len(new_prompt))

    # Verify the fix
    if "duration=2" in new_prompt:
        print("WARNING: duration=2 still in prompt!")
    else:
        print("GOOD: duration parameter removed")

    if "furious1" in new_prompt:
        print("GOOD: furious1 (angry mapping) found in prompt")
    else:
        print("WARNING: furious1 not found in prompt")

    if "show_expression(emotion=" in new_prompt:
        print("GOOD: show_expression examples present")
    else:
        print("WARNING: show_expression examples missing")


if __name__ == "__main__":
    asyncio.run(main())
