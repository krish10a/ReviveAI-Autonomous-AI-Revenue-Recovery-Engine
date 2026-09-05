"""
ReviveAI Canonical Application Configuration & Business Constants.
Single source of truth for business rules, action costs, and policy parameters.
"""

from decimal import Decimal
from enum import Enum

# Canonical Action Costs in INR
PAYMENT_LINK_COST_INR = Decimal("1.50")
RETRY_COST_INR = Decimal("0.50")
NOTIFICATION_COST_INR = Decimal("0.20")
ESCALATION_COST_INR = Decimal("25.00")
WAIT_COST_INR = Decimal("0.00")
STOP_COST_INR = Decimal("0.00")

# Canonical Quiet Hours Policy (21:00 to 08:00 local time)
QUIET_HOURS_START_HOUR = 21  # 21:00 (9 PM)
QUIET_HOURS_END_HOUR = 8     # 08:00 (8 AM)

def is_quiet_hours(hour_or_dt) -> bool:
    """
    Check if a given hour or datetime falls within quiet hours (21:00 to 08:00).
    Boundary rules:
      - 20:59 (hour 20) -> False (Allowed)
      - 21:00 (hour 21) -> True (Quiet hours / Blocked)
      - 21:01 (hour 21) -> True (Quiet hours / Blocked)
      - 07:59 (hour 7) -> True (Quiet hours / Blocked)
      - 08:00 (hour 8) -> False (Allowed)
      - 08:01 (hour 8) -> False (Allowed)
    """
    if hasattr(hour_or_dt, "hour"):
        hour = hour_or_dt.hour
    else:
        hour = int(hour_or_dt)
    return hour >= QUIET_HOURS_START_HOUR or hour < QUIET_HOURS_END_HOUR


# Action Cost Lookup Map supporting enum values, enum instances, and string representations
ACTION_COST_MAP = {
    "generate_payment_link": PAYMENT_LINK_COST_INR,
    "payment_link": PAYMENT_LINK_COST_INR,
    "retry": RETRY_COST_INR,
    "retry_now": RETRY_COST_INR,
    "retry_later": RETRY_COST_INR,
    "send_notification": NOTIFICATION_COST_INR,
    "notification": NOTIFICATION_COST_INR,
    "notify": NOTIFICATION_COST_INR,
    "escalate": ESCALATION_COST_INR,
    "escalate_human": ESCALATION_COST_INR,
    "wait": WAIT_COST_INR,
    "stop": STOP_COST_INR,
}

def get_action_cost(action_type: str) -> Decimal:
    """Retrieve canonical cost for any action type representation."""
    if hasattr(action_type, "value"):
        key = str(action_type.value).lower()
    else:
        key = str(action_type).lower()
    return ACTION_COST_MAP.get(key, Decimal("0.00"))
