"""
Synthetic data generator for ReviveAI Recovery Engine.
Encodes realistic, non-random relationships between transaction context, candidate actions, and recovery outcomes.
"""

import numpy as np
import pandas as pd
from typing import Tuple, List, Dict, Any


ACTIONS = ["retry_now", "retry_later", "payment_link", "notification", "escalate", "wait"]
PAYMENT_METHODS = ["card", "upi", "netbanking", "wallet"]
BANKS = ["HDFC", "ICICI", "SBI", "Axis", "Kotak"]
FAILURE_CATEGORIES = [
    "insufficient_funds",
    "expired_card",
    "bank_declined",
    "authentication_failed",
    "technical_error",
    "transaction_not_allowed",
]
MERCHANT_CATEGORIES = ["ecommerce", "saas_subscription", "utilities", "travel", "digital_goods"]


def generate_synthetic_recovery_dataset(
    n_samples: int = 5000,
    seed: int = 42
) -> pd.DataFrame:
    """
    Generate synthetic transactions with context features and action-conditioned outcomes.
    Each sample represents a failed payment context evaluated for candidate recovery actions.
    """
    rng = np.random.RandomState(seed)

    amounts = rng.exponential(scale=3000, size=n_samples) + 200
    amounts = np.clip(amounts, 100, 75000)

    payment_methods = rng.choice(PAYMENT_METHODS, size=n_samples, p=[0.45, 0.35, 0.15, 0.05])
    banks = rng.choice(BANKS, size=n_samples, p=[0.30, 0.25, 0.20, 0.15, 0.10])
    failure_categories = rng.choice(FAILURE_CATEGORIES, size=n_samples, p=[0.30, 0.15, 0.20, 0.15, 0.10, 0.10])
    merchant_categories = rng.choice(MERCHANT_CATEGORIES, size=n_samples, p=[0.35, 0.30, 0.15, 0.10, 0.10])

    hours = rng.randint(0, 24, size=n_samples)
    days_of_week = rng.randint(0, 7, size=n_samples)
    customer_tenures = rng.exponential(scale=180, size=n_samples) + 15
    customer_tenures = np.clip(customer_tenures, 1, 1500)

    prev_successes = rng.poisson(lam=12, size=n_samples)
    prev_failures = rng.poisson(lam=2, size=n_samples)
    prev_recoveries = np.minimum(prev_failures, rng.binomial(n=prev_failures, p=0.6))

    retry_counts = rng.choice([0, 1, 2, 3], size=n_samples, p=[0.55, 0.25, 0.15, 0.05])
    time_since_failures = rng.exponential(scale=60, size=n_samples) + 1  # in minutes
    failure_streaks = rng.geometric(p=0.6, size=n_samples) - 1

    # Ratio of current amount vs customer average amount
    avg_customer_amounts = amounts * rng.normal(loc=1.0, scale=0.3, size=n_samples)
    avg_customer_amounts = np.maximum(avg_customer_amounts, 50)
    amount_ratios = amounts / avg_customer_amounts

    # Bank failure rate baseline + occasional degradation
    bank_failure_rates = np.zeros(n_samples)
    for i in range(n_samples):
        b = banks[i]
        base_rate = {"HDFC": 0.08, "ICICI": 0.09, "SBI": 0.12, "Axis": 0.10, "Kotak": 0.07}[b]
        if rng.rand() < 0.08:  # 8% chance of bank outage / degradation spike
            base_rate += rng.uniform(0.35, 0.65)
        bank_failure_rates[i] = min(base_rate, 0.95)

    historical_success_rates = (prev_successes + 1.0) / (prev_successes + prev_failures + 2.0)

    records = []

    for i in range(n_samples):
        # We sample candidate actions to train an action-conditioned model
        for action in ACTIONS:
            # Domain-grounded recovery likelihood formula
            p = 0.50

            # 1. Action compatibility with failure reason
            fc = failure_categories[i]
            if fc == "expired_card":
                if action in ["retry_now", "retry_later"]:
                    p -= 0.60  # Retrying an expired card will definitely fail
                elif action == "payment_link":
                    p += 0.35  # User can enter new card via payment link
                elif action == "notification":
                    p += 0.20
            elif fc == "insufficient_funds":
                if action == "retry_now":
                    p -= 0.20  # Immediate retry has low funds replenishment
                elif action == "retry_later":
                    p += 0.30  # Later retry (e.g. next morning or payday) has much higher success
                elif action == "payment_link":
                    p += 0.25
            elif fc == "bank_declined":
                if action == "retry_now":
                    p -= 0.30
                elif action == "wait":
                    p += 0.25  # Waiting allows temporary bank outage to clear
                elif action == "escalate":
                    p += 0.15
            elif fc == "technical_error":
                if action == "retry_later":
                    p += 0.35
                elif action == "wait":
                    p += 0.30

            # 2. Bank degradation penalty for direct retries
            if bank_failure_rates[i] > 0.25:
                if action in ["retry_now", "retry_later"]:
                    p -= 0.40 * (bank_failure_rates[i] / 0.8)
                elif action == "wait":
                    p += 0.30

            # 3. High amount penalty for automated retries vs human escalate
            if amounts[i] > 15000:
                if action in ["retry_now", "notification"]:
                    p -= 0.15
                elif action == "escalate":
                    p += 0.25

            # 4. Retry count fatigue
            if retry_counts[i] >= 2:
                if action in ["retry_now", "retry_later"]:
                    p -= 0.25 * retry_counts[i]
                elif action in ["payment_link", "escalate"]:
                    p += 0.10

            # 5. Customer tenure & historical success rate bonus
            p += 0.15 * (historical_success_rates[i] - 0.5)
            if customer_tenures[i] > 365:
                p += 0.08

            # Bound probability to [0.02, 0.98]
            prob = float(np.clip(p, 0.02, 0.98))
            recovered = int(rng.rand() < prob)

            records.append({
                "amount": amounts[i],
                "payment_method": payment_methods[i],
                "bank": banks[i],
                "failure_category": failure_categories[i],
                "merchant_category": merchant_categories[i],
                "hour": hours[i],
                "day_of_week": days_of_week[i],
                "customer_tenure": customer_tenures[i],
                "previous_successful_payments": prev_successes[i],
                "previous_failed_payments": prev_failures[i],
                "previous_recoveries": prev_recoveries[i],
                "retry_count": retry_counts[i],
                "time_since_failure": time_since_failures[i],
                "failure_streak": failure_streak[i] if 'failure_streak' in locals() else failure_streaks[i],
                "amount_relative_to_customer_history": amount_ratios[i],
                "recent_bank_failure_rate": bank_failure_rates[i],
                "historical_success_rate": historical_success_rates[i],
                "action": action,
                "recovered": recovered,
                "ground_truth_prob": prob,
            })

    return pd.DataFrame(records)


if __name__ == "__main__":
    df = generate_synthetic_recovery_dataset(1000)
    print(f"Generated {len(df)} samples across {len(ACTIONS)} actions.")
    print("Action distribution:\n", df.groupby("action")["recovered"].mean())
