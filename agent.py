import json
import os
import re
from typing import Any, Optional

from dotenv import load_dotenv
from openai import OpenAI

from prompt_config import SYSTEM_PROMPT
from tools import TOOL_MAP, USER_OS


load_dotenv()

MODEL_NAME = os.environ.get("MODEL_NAME", "meta-llama/Llama-3.3-70B-Instruct")
HUGGINGFACE_API_KEY = os.environ.get("HUGGINGFACE_API_KEY")
SHOW_AGENT_TRACE = os.environ.get("SHOW_AGENT_TRACE", "true").lower() in {"1", "true", "yes", "on"}

if not HUGGINGFACE_API_KEY:
    raise RuntimeError("Missing HUGGINGFACE_API_KEY in environment.")

client = OpenAI(
    base_url="https://router.huggingface.co/v1",
    api_key=HUGGINGFACE_API_KEY,
)

VALID_STEPS = {"THINK", "TOOL", "OUTPUT"}


def extract_first_json_object(raw_content: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw_content)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", raw_content, re.DOTALL)
    if not match:
        raise json.JSONDecodeError("No JSON object found.", raw_content, 0)

    parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise json.JSONDecodeError("Top-level JSON is not an object.", raw_content, 0)
    return parsed


def parse_step_payload(raw_content: str) -> dict[str, Any]:
    payload = extract_first_json_object(raw_content)
    step = payload.get("step")

    if step not in VALID_STEPS:
        raise ValueError(f"Invalid step '{step}'. Expected one of {sorted(VALID_STEPS)}.")

    if step == "TOOL":
        tool_name = payload.get("tool_name")
        tool_args = payload.get("tool_args")
        if tool_name not in TOOL_MAP:
            raise ValueError(f"Tool '{tool_name}' does not exist.")
        if not isinstance(tool_args, dict):
            raise ValueError("tool_args must be a JSON object.")

    if step in {"THINK", "OUTPUT"} and not isinstance(payload.get("content"), str):
        raise ValueError(f"{step} responses must include a string content field.")

    return payload


def call_model(messages: list[dict[str, str]], *, json_mode: bool) -> str:
    request_kwargs: dict[str, Any] = {
        "model": MODEL_NAME,
        "messages": messages,
    }

    if json_mode:
        request_kwargs["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(**request_kwargs)
    return response.choices[0].message.content or ""


def render_trace(tool_name: str, tool_args: dict[str, Any], observation: Optional[Any] = None) -> str:
    if tool_name == "write_file":
        target_file = tool_args.get("filename", "unknown file")
        if observation is None:
            return f"Writing {target_file}"
        return f"Saved {target_file}"

    if tool_name == "fetch_website":
        target_url = tool_args.get("url", "unknown URL")
        if observation is None:
            return f"Fetching {target_url}"
        return f"Fetched summary for {target_url}"

    if tool_name == "execute_command":
        command = tool_args.get("cmd", "")
        if observation is None:
            return f"Running command: {command}"
        return str(observation)

    if observation is None:
        return f"Running {tool_name}"
    return str(observation)


def render_tool_args(tool_name: str, tool_args: dict[str, Any]) -> dict[str, Any]:
    if tool_name != "write_file":
        return tool_args

    content = tool_args.get("content", "")
    redacted_args = dict(tool_args)
    redacted_args["content"] = f"<redacted {len(content)} chars>"
    return redacted_args


def run_agent_loop(user_input: str, history: list[dict[str, str]]) -> None:
    history.append({"role": "user", "content": user_input})

    while True:
        try:
            raw_content = call_model(history, json_mode=True)
            history.append({"role": "assistant", "content": raw_content})
            payload = parse_step_payload(raw_content)
            step_type = payload["step"]

            if step_type == "THINK":
                if SHOW_AGENT_TRACE:
                    print(f"\n🧠 \033[94mTHINKING:\033[0m {payload['content']}")
                history.append(
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "step": "OBSERVE",
                                "content": "Thought recorded. Proceed to the next step.",
                            }
                        ),
                    }
                )
                continue

            if step_type == "TOOL":
                tool_name = payload["tool_name"]
                tool_args = payload["tool_args"]

                if SHOW_AGENT_TRACE:
                    print(f"\n🔧 \033[93mUSING TOOL:\033[0m {tool_name}")
                    print(f"   Args: {render_tool_args(tool_name, tool_args)}")

                observation = TOOL_MAP[tool_name](**tool_args)
                if SHOW_AGENT_TRACE:
                    print(f"👀 \033[95mOBSERVED:\033[0m {render_trace(tool_name, tool_args, observation)[:160]}")

                history.append(
                    {
                        "role": "user",
                        "content": json.dumps({"step": "OBSERVE", "content": observation}),
                    }
                )
                continue

            print(f"\n🤖 \033[92mAGENT:\033[0m {payload['content']}\n")
            return

        except json.JSONDecodeError:
            print("\n[Error] AI did not return valid JSON. Retrying...")
            history.append(
                {
                    "role": "user",
                    "content": (
                        "FORMAT ERROR: Respond with exactly one valid JSON object. "
                        "Do not include markdown or extra prose."
                    ),
                }
            )
        except ValueError as error:
            print(f"\n[Warning] {error}")
            history.append(
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "step": "OBSERVE",
                            "content": (
                                f"Protocol violation: {error}. Correct yourself and continue "
                                "with the next valid step."
                            ),
                        }
                    ),
                }
            )
        except Exception as error:
            print(f"\n[System Error] {error}")
            return


def main() -> None:
    print("Conversational AI agent with tool use and website cloning.")
    print("Type 'exit' or 'quit' to close the terminal.\n")

    history = [{"role": "system", "content": SYSTEM_PROMPT}]

    while True:
        try:
            user_input = input("\033[92mUser > \033[0m").strip()

            if user_input.lower() in {"exit", "quit"}:
                print("Goodbye!")
                break

            if not user_input:
                continue

            run_agent_loop(user_input, history)

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break


if __name__ == "__main__":
    main()
