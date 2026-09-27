import requests
import json


BASE_URL = "http://127.0.0.1:8000"


def print_result(title, response):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)
    print("HTTP:", response.status_code)

    try:
        print(json.dumps(response.json(), indent=2))
    except Exception:
        print(response.text)


# =========================================================
# 1. HEALTH CHECK
# =========================================================

response = requests.get(
    f"{BASE_URL}/v1/healthz"
)

print_result(
    "1. HEALTH CHECK",
    response
)


# =========================================================
# 2. CATEGORY CONTEXT
# =========================================================

category_context = {
    "scope": "category",
    "context_id": "dentists",
    "version": 1,
    "delivered_at": "2026-04-26T09:45:00Z",
    "payload": {
        "slug": "dentists",
        "voice": {
            "tone": "peer_clinical",
            "vocab_taboo": [
                "guaranteed",
                "100% safe"
            ]
        },
        "offer_catalog": [
            {
                "id": "den_001",
                "title": "Dental Cleaning @ ₹299",
                "value": "299",
                "audience": "new_user",
                "type": "service_at_price"
            }
        ],
        "peer_stats": {
            "avg_rating": 4.4,
            "avg_ctr": 0.030
        },
        "digest": [
            {
                "id": "d_2026W17_jida_fluoride",
                "kind": "research",
                "title": "3-month fluoride recall cuts caries 38% better",
                "source": "JIDA Oct 2026, p.14"
            }
        ],
        "patient_content_library": [],
        "seasonal_beats": [
            {
                "month_range": "Nov-Feb",
                "note": "exam-stress bruxism spike"
            }
        ],
        "trend_signals": [
            {
                "query": "clear aligners delhi",
                "delta_yoy": 0.62
            }
        ]
    }
}

response = requests.post(
    f"{BASE_URL}/v1/context",
    json=category_context
)

print_result(
    "2. CATEGORY CONTEXT",
    response
)


# =========================================================
# 3. MERCHANT CONTEXT
# =========================================================

merchant_context = {
    "scope": "merchant",
    "context_id": "m_001_drmeera_dentist_delhi",
    "version": 1,
    "delivered_at": "2026-04-26T09:45:30Z",
    "payload": {
        "merchant_id": "m_001_drmeera_dentist_delhi",
        "category_slug": "dentists",
        "identity": {
            "name": "Dr. Meera's Dental Clinic",
            "city": "Delhi",
            "locality": "Lajpat Nagar",
            "verified": True,
            "languages": [
                "en",
                "hi"
            ],
            "owner_first_name": "Meera"
        },
        "subscription": {
            "status": "active",
            "plan": "Pro",
            "days_remaining": 82
        },
        "performance": {
            "window_days": 30,
            "views": 2410,
            "calls": 18,
            "directions": 45,
            "ctr": 0.021,
            "delta_7d": {
                "views_pct": 0.18,
                "calls_pct": -0.05
            }
        },
        "offers": [
            {
                "id": "o_meera_001",
                "title": "Dental Cleaning @ ₹299",
                "status": "active"
            }
        ],
        "conversation_history": [],
        "customer_aggregate": {
            "total_unique_ytd": 540,
            "lapsed_180d_plus": 78,
            "retention_6mo_pct": 0.38,
            "high_risk_adult_count": 124
        },
        "signals": [
            "stale_posts:22d",
            "ctr_below_peer_median",
            "high_risk_adult_cohort"
        ]
    }
}

response = requests.post(
    f"{BASE_URL}/v1/context",
    json=merchant_context
)

print_result(
    "3. MERCHANT CONTEXT",
    response
)


# =========================================================
# 4. RESEARCH TRIGGER
# =========================================================

trigger_context = {
    "scope": "trigger",
    "context_id": "trg_001_research_digest_dentists",
    "version": 1,
    "delivered_at": "2026-04-26T10:32:00Z",
    "payload": {
        "id": "trg_001_research_digest_dentists",
        "scope": "merchant",
        "kind": "research_digest",
        "source": "external",
        "merchant_id": "m_001_drmeera_dentist_delhi",
        "customer_id": None,
        "payload": {
            "category": "dentists",
            "top_item_id": "d_2026W17_jida_fluoride"
        },
        "urgency": 2,
        "suppression_key": "research:dentists:2026-W17",
        "expires_at": "2026-05-03T00:00:00Z"
    }
}

response = requests.post(
    f"{BASE_URL}/v1/context",
    json=trigger_context
)

print_result(
    "4. RESEARCH TRIGGER",
    response
)


# =========================================================
# 5. RUN TICK
# =========================================================

tick_request = {
    "now": "2026-04-26T10:35:00Z",
    "available_triggers": [
        "trg_001_research_digest_dentists"
    ]
}

response = requests.post(
    f"{BASE_URL}/v1/tick",
    json=tick_request
)

print_result(
    "5. /v1/tick RESULT",
    response
)


# =========================================================
# 6. CHECK EXPECTED RESULT
# =========================================================

if response.status_code != 200:
    print("\n❌ TEST FAILED: /v1/tick did not return 200.")

else:

    data = response.json()

    actions = data.get("actions", [])

    if len(actions) == 0:

        print(
            "\n❌ TEST FAILED: "
            "No action was generated."
        )

    else:

        action = actions[0]

        print("\n" + "=" * 70)
        print("6. IMPORTANT CHECKS")
        print("=" * 70)

        checks = {
            "conversation_id":
                action.get("conversation_id"),

            "merchant_id":
                action.get("merchant_id"),

            "send_as":
                action.get("send_as"),

            "trigger_id":
                action.get("trigger_id"),

            "template_name":
                action.get("template_name"),

            "cta":
                action.get("cta"),

            "suppression_key":
                action.get("suppression_key"),
        }

        for key, value in checks.items():
            print(f"{key}: {value}")

        print("\n" + "=" * 70)

        expected_conversation_id = (
            "conv_m_001_drmeera_research_W17"
        )

        if (
            action.get("conversation_id")
            == expected_conversation_id
        ):
            print(
                "✅ Conversation ID is correct:"
            )
            print(
                expected_conversation_id
            )
        else:
            print(
                "❌ Conversation ID is different."
            )

        if action.get("send_as") == "vera":
            print("✅ send_as = vera")
        else:
            print("❌ send_as is incorrect")

        if action.get("cta") == "open_ended":
            print("✅ CTA = open_ended")
        else:
            print("❌ CTA is incorrect")

        if (
            action.get("suppression_key")
            == "research:dentists:2026-W17"
        ):
            print("✅ Suppression key is correct")
        else:
            print("❌ Suppression key is incorrect")

        print("\n" + "=" * 70)
        print("FINAL TICK ACTION")
        print("=" * 70)

        print(
            json.dumps(
                action,
                indent=2,
                ensure_ascii=False
            )
        )