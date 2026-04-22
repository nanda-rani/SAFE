import json
import os
import threading
from typing import Dict

# ================================
# CONFIG
# ================================

CONTEXT_THRESHOLD = 272000  # tokens

# Pricing per 1M tokens ($ USD)
PRICING = {
    "gpt-5.4": {
        "short": {"prompt": 2.50, "completion": 15.00},
        "long": {"prompt": 5.00, "completion": 22.50},
    },
    "gpt-5.4-mini": {
        "short": {"prompt": 0.75, "completion": 4.50},
    },
    "gpt-5.4-nano": {
        "short": {"prompt": 0.20, "completion": 1.25},
    },
    "gpt-5.4-pro": {
        "short": {"prompt": 30.00, "completion": 180.00},
        "long": {"prompt": 60.00, "completion": 270.00},
    },
    "gpt-5.2":{
        "short": {"prompt": 1.75, "completion": 14.00},
    },
    "gpt-5.1": {
        "short": {"prompt": 1.25, "completion": 10.00},
        "long": {"prompt": 1.25, "completion": 10.00},
    },
    "gpt-5": {
        "short": {"prompt": 1.25,  "completion": 10.00},
        "long": {"prompt": 1.25,  "completion": 10.00},
    },
    "gpt-5-mini": {
       "short": {"prompt": 0.25, "completion": 2.00},
       "long": {"prompt": 0.25, "completion": 2.00},
    },

    # fallback models
    "gpt-4o": {
        "short": {"prompt": 2.50, "completion": 10.00},
    },
    "gpt-4o-mini": {
        "short": {"prompt": 0.15, "completion": 0.60},
    }
}

MODEL_MAPPINGS = {
    "gpt-4o": "gpt-4o",
    "gpt-4o-mini": "gpt-4o-mini",
    "gpt-5": "gpt-5",
    "gpt-5.4-mini-2026-03-17": "gpt-5-mini",
    "gpt-5.1": "gpt-5.1",
    "gpt-5.2": "gpt-5.2",
    "gpt-5.4": "gpt-5.4",
    "gpt-5.4-mini": "gpt-5.4-mini",
    "gpt-5.4-nano": "gpt-5.4-nano",
    "gpt-5.4-pro": "gpt-5.4-pro",
}

_lock = threading.Lock()


class CostTracker:
    def __init__(self):
        self.global_cost_file = "outputs/costs/global_costs.json"

        os.makedirs("outputs/costs", exist_ok=True)

        if not os.path.exists(self.global_cost_file):
            with open(self.global_cost_file, "w") as f:
                json.dump({
                    "total_cost_usd": 0.0,
                    "total_prompt_tokens": 0,
                    "total_completion_tokens": 0
                }, f)

    # ================================
    # Pricing selector
    # ================================
    def _get_pricing(self, model_string: str, prompt_tokens: int) -> Dict[str, float]:
        mapped = MODEL_MAPPINGS.get(model_string, model_string)
        model_pricing = PRICING.get(mapped)

        if not model_pricing:
            return {"prompt": 2.5, "completion": 15.0}  # safe fallback

        # 🔥 KEY: use prompt_tokens as context proxy
        context_type = "short" if prompt_tokens <= CONTEXT_THRESHOLD else "long"

        # fallback if long not available
        if context_type not in model_pricing:
            context_type = "short"

        return model_pricing[context_type]

    # ================================
    # Record call (UNCHANGED SIGNATURE)
    # ================================
    def record_call(self, finding_uid: str, model_string: str, prompt_tokens: int, completion_tokens: int):

        pricing = self._get_pricing(model_string, prompt_tokens)

        cost_usd = (
            (prompt_tokens / 1_000_000.0) * pricing["prompt"] +
            (completion_tokens / 1_000_000.0) * pricing["completion"]
        )

        with _lock:
            # ------------------------
            # Finding cost
            # ------------------------
            finding_cost_file = f"outputs/costs/{finding_uid}_cost.json"

            finding_cost = {
                "total_cost_usd": 0.0,
                "total_prompt_tokens": 0,
                "total_completion_tokens": 0
            }

            if os.path.exists(finding_cost_file):
                try:
                    with open(finding_cost_file, "r") as f:
                        finding_cost = json.load(f)
                except json.JSONDecodeError:
                    pass

            finding_cost["total_cost_usd"] += cost_usd
            finding_cost["total_prompt_tokens"] += prompt_tokens
            finding_cost["total_completion_tokens"] += completion_tokens

            with open(finding_cost_file, "w") as f:
                json.dump(finding_cost, f, indent=2)

            # ------------------------
            # Global cost
            # ------------------------
            global_cost = {
                "total_cost_usd": 0.0,
                "total_prompt_tokens": 0,
                "total_completion_tokens": 0
            }

            if os.path.exists(self.global_cost_file):
                try:
                    with open(self.global_cost_file, "r") as f:
                        global_cost = json.load(f)
                except json.JSONDecodeError:
                    pass

            global_cost["total_cost_usd"] += cost_usd
            global_cost["total_prompt_tokens"] += prompt_tokens
            global_cost["total_completion_tokens"] += completion_tokens

            with open(self.global_cost_file, "w") as f:
                json.dump(global_cost, f, indent=2)

        return cost_usd

    def get_global_totals(self) -> Dict[str, float]:
        with _lock:
            if os.path.exists(self.global_cost_file):
                try:
                    with open(self.global_cost_file, "r") as f:
                        return json.load(f)
                except json.JSONDecodeError:
                    pass
        return {"total_cost_usd": 0.0, "total_prompt_tokens": 0, "total_completion_tokens": 0}

    def get_finding_cost(self, finding_uid: str) -> Dict[str, float]:
        finding_cost_file = f"outputs/costs/{finding_uid}_cost.json"

        with _lock:
            if os.path.exists(finding_cost_file):
                try:
                    with open(finding_cost_file, "r") as f:
                        return json.load(f)
                except json.JSONDecodeError:
                    pass

        return {"total_cost_usd": 0.0, "total_prompt_tokens": 0, "total_completion_tokens": 0}


cost_tracker = CostTracker()









# import json
# import os
# import threading
# from typing import Dict

# # Approximate costs per 1K tokens ($ USD)
# PRICING = {
#     "gpt-4o": {
#         "prompt": 2.50,
#         "completion": 10.00
#     },
#     "gpt-4o-mini": {
#         "prompt": 0.15,
#         "completion": 0.60
#     },
#     "gpt-5.1": {
#         "prompt": 1.25,
#         "completion": 10.00
#     },
#     "gpt-5": {
#         "prompt": 1.25,
#         "completion": 10.00
#     },
#     "gpt-5-mini": {
#         "prompt": 0.25,
#         "completion": 2.00
#     },
#     "claude-3-5-sonnet-20241022": { # Usually claude-sonnet-4.5 doesn't exist yet but let's map sonnet 3.5 prices as proxy or match requested string
#         "prompt": 0.003,
#         "completion": 0.015
#     },
#     "claude-3-haiku-20240307": { # Map to haiku proxy
#         "prompt": 0.00025,
#         "completion": 0.00125
#     }
# }

# # Config string maps
# MODEL_MAPPINGS = {
#     "gpt-4o": "gpt-4o",
#     "gpt-4o-mini": "gpt-4o-mini",
#     "claude-sonnet-4.5": "claude-3-5-sonnet-20241022",
#     "claude-haiku-4.5": "claude-3-haiku-20240307"
# }

# _lock = threading.Lock()

# class CostTracker:
#     def __init__(self):
#         self.global_cost_file = "outputs/costs/global_costs.json"
        
#         # Initialize global tracking
#         os.makedirs("outputs/costs", exist_ok=True)
#         if not os.path.exists(self.global_cost_file):
#             with open(self.global_cost_file, "w") as f:
#                 json.dump({"total_cost_usd": 0.0, "total_prompt_tokens": 0, "total_completion_tokens": 0}, f)

#     def _get_pricing(self, model_string: str) -> Dict[str, float]:
#         mapped = MODEL_MAPPINGS.get(model_string, "gpt-4o") # fallback to 4o pricing
#         return PRICING.get(mapped, PRICING["gpt-4o"])

#     def record_call(self, finding_uid: str, model_string: str, prompt_tokens: int, completion_tokens: int):
#         pricing = self._get_pricing(model_string)
#         cost_usd = (prompt_tokens / 1000000.0) * pricing["prompt"] + (completion_tokens / 1000000.0) * pricing["completion"]

#         with _lock:
#             # 1. Update finding cost
#             finding_cost_file = f"outputs/costs/{finding_uid}_cost.json"
#             finding_cost = {"total_cost_usd": 0.0, "total_prompt_tokens": 0, "total_completion_tokens": 0}
#             if os.path.exists(finding_cost_file):
#                 try:
#                     with open(finding_cost_file, "r") as f:
#                         finding_cost = json.load(f)
#                 except json.JSONDecodeError:
#                     pass

#             finding_cost["total_cost_usd"] += cost_usd
#             finding_cost["total_prompt_tokens"] += prompt_tokens
#             finding_cost["total_completion_tokens"] += completion_tokens

#             with open(finding_cost_file, "w") as f:
#                 json.dump(finding_cost, f, indent=2)

#             # 2. Update global cost
#             global_cost = {"total_cost_usd": 0.0, "total_prompt_tokens": 0, "total_completion_tokens": 0}
#             if os.path.exists(self.global_cost_file):
#                 try:
#                     with open(self.global_cost_file, "r") as f:
#                         global_cost = json.load(f)
#                 except json.JSONDecodeError:
#                     pass

#             global_cost["total_cost_usd"] += cost_usd
#             global_cost["total_prompt_tokens"] += prompt_tokens
#             global_cost["total_completion_tokens"] += completion_tokens

#             with open(self.global_cost_file, "w") as f:
#                 json.dump(global_cost, f, indent=2)

#         return cost_usd

#     def get_global_totals(self) -> Dict[str, float]:
#         """Returns the current cumulative global cost totals."""
#         with _lock:
#             if os.path.exists(self.global_cost_file):
#                 try:
#                     with open(self.global_cost_file, "r") as f:
#                         return json.load(f)
#                 except json.JSONDecodeError:
#                     pass
#         return {"total_cost_usd": 0.0, "total_prompt_tokens": 0, "total_completion_tokens": 0}

#     def get_finding_cost(self, finding_uid: str) -> Dict[str, float]:
#         """Returns the cost breakdown for a specific finding UID."""
#         finding_cost_file = f"outputs/costs/{finding_uid}_cost.json"
#         with _lock:
#             if os.path.exists(finding_cost_file):
#                 try:
#                     with open(finding_cost_file, "r") as f:
#                         return json.load(f)
#                 except json.JSONDecodeError:
#                     pass
#         return {"total_cost_usd": 0.0, "total_prompt_tokens": 0, "total_completion_tokens": 0}

# cost_tracker = CostTracker()
