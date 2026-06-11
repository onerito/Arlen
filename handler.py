from PIL import Image
from dotenv import load_dotenv
import os
from anthropic import Anthropic
from typing import cast
from anthropic.types import ModelParam
import base64
from pathlib import Path

_ = load_dotenv()

api_key = os.getenv("ANTHROPIC_API_KEY")
raw_model = os.getenv("MODEL")
prompt = os.getenv("PROMPT")

if not api_key or not raw_model or not prompt:
    raise RuntimeError("ANTHROPIC_API_KEY/MODEL/PROMPT is missing, check your env file")

model = cast(ModelParam, raw_model)

client = Anthropic(api_key=api_key) # sets the big juicy

def image_block(path: str):
    data = base64.b64encode(Path(path).read_bytes()).decode("utf-8")

    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": "image/png",
            "data": data,
        },
    }

def on_screenshot(_images: list[Image.Image], paths: list[str]) -> None:
    """Called once per burst after ']' is pressed.
    images: the captured PIL.Image objects, in capture order.
    paths:  the matching saved file paths (e.g. mrbeast_0.png), same order/length.
    """
    content = []

    for path in paths:
        content.append(image_block(path)) # this makes it into base64 and then appends it to the content list, which we will give to claude

        content.append(
            {
                "type": "text",
                "text": prompt,
            }
        )
        message = client.messages.create(
            max_tokens=1024, # i didnt add this to the .env file since this is good
            messages=[
                {
                    "role": "user",
                    "content": content,
                }
            ],
            model=model,
        )
        print(message.content)
