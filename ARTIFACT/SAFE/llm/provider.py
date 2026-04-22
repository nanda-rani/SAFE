import os
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic

def get_llm(model_id: str):
    """
    Factory function to instantiate LLMs based on model_id.
    Supports OpenAI and Anthropic models with flexible routing.
    """

    # ===============================
    # 🔹 OpenAI Models (ALL GPT)
    # ===============================
    if model_id.startswith("gpt"):
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set.")

        return ChatOpenAI(
            model=model_id,
            temperature=0.0
        )

    # ===============================
    # 🔹 Anthropic Models
    # ===============================
    elif model_id in ["claude-sonnet-4.5", "claude-haiku-4.5"]:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is not set.")

        anthropic_mapping = {
            "claude-sonnet-4.5": "claude-3-5-sonnet-20241022",
            "claude-haiku-4.5": "claude-3-haiku-20240307"
        }

        return ChatAnthropic(
            model_name=anthropic_mapping[model_id],
            temperature=0.0
        )

    # ===============================
    # 🔹 Unsupported
    # ===============================
    else:
        raise ValueError(f"Unsupported model: {model_id}")

# def get_llm(model_id: str):
#     """
#     Factory function to instantiate the underlying LangChain generic chat model
#     based on our custom configuration strings.
#     """
#     if model_id in ["gpt-4o", "gpt-4o-mini"]:
#         api_key = os.environ.get("OPENAI_API_KEY")
#         if not api_key:
#             raise ValueError("OPENAI_API_KEY environment variable is not set.")
#         return ChatOpenAI(model=model_id, temperature=0.0)
#     elif model_id in ["claude-sonnet-4.5", "claude-haiku-4.5"]:
#         api_key = os.environ.get("ANTHROPIC_API_KEY")
#         if not api_key:
#             raise ValueError("ANTHROPIC_API_KEY environment variable is not set.")
#         # Map our internal aliases to actual Anthropic names
#         anthropic_mapping = {
#             "claude-sonnet-4.5": "claude-3-5-sonnet-20241022",
#             "claude-haiku-4.5": "claude-3-haiku-20240307"
#         }
#         return ChatAnthropic(model_name=anthropic_mapping[model_id], temperature=0.0)
#     else:
#         raise ValueError(f"Unsupported model: {model_id}")
