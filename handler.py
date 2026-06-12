from PIL import Image
from dotenv import load_dotenv
import os
from anthropic import Anthropic, DefaultHttpxClient
from typing import cast
from anthropic.types import ModelParam
import base64
import io

from indicators import flash_caps_lock, flash_corner_indicator

_ = load_dotenv()

api_key = os.getenv("ANTHROPIC_API_KEY")
raw_model = os.getenv("MODEL")
prompt = os.getenv("PROMPT")
delivery_mode = os.getenv("DELIVERY_MODE")

if not api_key or not raw_model or not prompt or not delivery_mode:
    raise RuntimeError("ANTHROPIC_API_KEY/MODEL/PROMPT/DELIVERY_MODE is missing, check your env file")

model = cast(ModelParam, raw_model)

max_long_edge = int(os.getenv("MAX_IMAGE_LONG_EDGE", "1568"))

proxy_url = os.getenv("PROXY")

# route all api traffic through a proxy when PROXY is set, otherwise hand the
# SDK its default client so timeouts/connection limits stay intact. supports
# http(s) and socks5 (e.g. socks5://127.0.0.1:9050); socks needs httpx[socks].
if proxy_url:
    client = Anthropic(api_key=api_key, http_client=DefaultHttpxClient(proxy=proxy_url))
else:
    client = Anthropic(api_key=api_key) # sets the big juicy

def image_block(path: str):
    # image tokens are billed on pixel dimensions (w*h/750), not file size,
    # so downscaling is what actually saves money. png stays lossless so
    # small text doesnt turn into jpeg mush.
    img = Image.open(path)
    if max(img.size) > max_long_edge:
        scale = max_long_edge / max(img.size)
        img = img.resize(
            (round(img.width * scale), round(img.height * scale)),
            Image.Resampling.LANCZOS,
        )

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    data = base64.b64encode(buf.getvalue()).decode("utf-8")

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

    # one prompt after all the images, not one per image (per-image repeated the whole prompt and burned tokens)
    content.append(
        {
            "type": "text",
            "text": prompt,
        }
    )
    message = client.messages.create(
        max_tokens=8000, # thinking counts against this cap, so it needs headroom or you get cut off mid-think with no answer
        thinking={"type": "adaptive"}, # reasons privately so the visible reply stays answers-only
        messages=[
            {
                "role": "user",
                "content": content,
            }
        ],
        model=model,
    )
    for block in message.content:
        if block.type == "text":
            print(f'Raw text: "{block.text}"')
            answer = block.text.strip()  # claude often tacks on a trailing newline; bare "A" must still match
            if answer == "A":
                if delivery_mode == "caps":
                    flash_caps_lock(1)
                elif delivery_mode == "pixel":
                    flash_corner_indicator(1)
            elif answer == "B":
                if delivery_mode == "caps":
                    flash_caps_lock(2)
                elif delivery_mode == "pixel":
                    flash_corner_indicator(2)
            elif answer == "C":
                if delivery_mode == "caps":
                    flash_caps_lock(3)
                elif delivery_mode == "pixel":
                    flash_corner_indicator(3)
            elif answer == "D":
                if delivery_mode == "caps":
                    flash_caps_lock(4)
                elif delivery_mode == "pixel":
                    flash_corner_indicator(4)
    