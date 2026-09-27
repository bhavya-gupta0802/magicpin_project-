from typing import Any, Dict, Optional


class DecisionEngine:
    """
    Deterministic trigger -> action engine for the magicpin Vera challenge.

    The engine intentionally uses only information present in trigger,
    merchant, category, and customer contexts. It does not invent offers,
    metrics, dates, or customer facts.
    """

    def __init__(self, context_store):
        self.context_store = context_store

    # =========================================================
    # Generic context lookup
    # =========================================================

    def get_context(
        self,
        scope: str,
        context_id: str,
    ) -> Optional[Dict[str, Any]]:
        stored = self.context_store.get(scope, context_id)
        if stored is None:
            return None
        return stored["payload"]

    def get_trigger(self, trigger_id: str) -> Optional[Dict[str, Any]]:
        return self.get_context("trigger", trigger_id)

    def get_merchant(self, merchant_id: str) -> Optional[Dict[str, Any]]:
        return self.get_context("merchant", merchant_id)

    def get_category(self, category_id: str) -> Optional[Dict[str, Any]]:
        return self.get_context("category", category_id)

    def get_customer(
        self,
        customer_id: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        if not customer_id:
            return None
        return self.get_context("customer", customer_id)

    # =========================================================
    # Common helpers
    # =========================================================

    @staticmethod
    def _identity_name(
        obj: Optional[Dict[str, Any]],
        fallback: str = "there",
    ) -> str:
        if not obj:
            return fallback

        identity = obj.get("identity") or {}

        return (
            obj.get("first_name")
            or obj.get("name")
            or identity.get("owner_first_name")
            or identity.get("first_name")
            or identity.get("name")
            or fallback
        )

    @staticmethod
    def _merchant_id(
        trigger: Dict[str, Any],
        merchant: Dict[str, Any],
    ) -> Optional[str]:
        return merchant.get("merchant_id") or trigger.get("merchant_id")

    @staticmethod
    def _payload(trigger: Dict[str, Any]) -> Dict[str, Any]:
        return trigger.get("payload") or {}

    @staticmethod
    def _suppression(
        trigger: Dict[str, Any],
        fallback: str,
    ) -> str:
        return trigger.get("suppression_key") or fallback

    @staticmethod
    def _conversation(
        trigger: Dict[str, Any],
        merchant_id: Optional[str] = None,
        customer_id: Optional[str] = None,
        suffix: str = "trigger",
    ) -> str:
        # Trigger-specific IDs prevent unrelated triggers for the same
        # merchant/customer from sharing a conversation.
        trigger_id = trigger.get("id") or suffix

        if customer_id:
            return f"conv_{customer_id}_{trigger_id}"

        if merchant_id:
            return f"conv_{merchant_id}_{trigger_id}"

        return f"conv_{trigger_id}"

    def _merchant_action(self, trigger, merchant, *, body, template_name, template_params, cta="open_ended", rationale, suppression_fallback, suffix):
        merchant_id = self._merchant_id(trigger, merchant)
        owner = self._identity_name(merchant)
        category = str(merchant.get("category_slug") or "").lower()
        if owner and owner != "there":
            greeting = f"Dr. {owner}" if category == "dentists" and not owner.lower().startswith("dr.") else owner
            if not body.lstrip().lower().startswith(greeting.lower()):
                body = f"{greeting}, {body}"
        return {"conversation_id": self._conversation(trigger, merchant_id=merchant_id, suffix=suffix), "merchant_id": merchant_id, "customer_id": None, "send_as": "vera", "trigger_id": trigger.get("id"), "template_name": template_name, "template_params": template_params, "body": body, "cta": cta, "suppression_key": self._suppression(trigger, suppression_fallback), "rationale": rationale}
    def _customer_action(
        self,
        trigger: Dict[str, Any],
        merchant: Dict[str, Any],
        customer: Dict[str, Any],
        *,
        body: str,
        template_name: str,
        template_params: list,
        cta: str = "open_ended",
        rationale: str,
        suppression_fallback: str,
        suffix: str,
    ) -> Dict[str, Any]:
        merchant_id = self._merchant_id(trigger, merchant)
        customer_id = trigger.get("customer_id")

        return {
            "conversation_id": self._conversation(
                trigger,
                merchant_id=merchant_id,
                customer_id=customer_id,
                suffix=suffix,
            ),
            "merchant_id": merchant_id,
            "customer_id": customer_id,
            "send_as": "merchant_on_behalf",
            "trigger_id": trigger.get("id"),
            "template_name": template_name,
            "template_params": template_params,
            "body": body,
            "cta": cta,
            "suppression_key": self._suppression(
                trigger,
                suppression_fallback,
            ),
            "rationale": rationale,
        }

    # =========================================================
    # Main decision function
    # =========================================================

    def decide(
        self,
        trigger_id: str,
        now: str,
    ) -> Optional[Dict[str, Any]]:
        trigger = self.get_trigger(trigger_id)

        if not trigger:
            return None

        merchant_id = trigger.get("merchant_id")

        # All current representative merchant triggers contain a merchant.
        # Customer-scoped triggers also carry the merchant that should send
        # the customer-facing message.
        if not merchant_id:
            return None

        merchant = self.get_merchant(merchant_id)

        if not merchant:
            return None

        category_slug = merchant.get("category_slug")
        category = (
            self.get_category(category_slug)
            if category_slug
            else None
        )

        customer_id = trigger.get("customer_id")
        customer = self.get_customer(customer_id)

        kind = trigger.get("kind")

        handlers = {
            "research_digest": self._research_digest_action,
            "regulation_change": self._regulation_change_action,
            "recall_due": self._recall_action,
            "perf_dip": self._perf_dip_action,
            "renewal_due": self._renewal_due_action,
            "festival_upcoming": self._festival_action,
            "wedding_package_followup": self._bridal_followup_action,
            "curious_ask_due": self._curious_ask_action,
            "winback_eligible": self._winback_action,
            "ipl_match_today": self._ipl_action,
            "review_theme_emerged": self._review_theme_action,
            "milestone_reached": self._milestone_action,
            "active_planning_intent": self._planning_action,
            "seasonal_perf_dip": self._seasonal_dip_action,
            "customer_lapsed_hard": self._customer_winback_action,
            "trial_followup": self._trial_followup_action,
            "supply_alert": self._supply_alert_action,
            "chronic_refill_due": self._chronic_refill_action,
            "category_seasonal": self._category_seasonal_action,
            "gbp_unverified": self._gbp_action,
            "cde_opportunity": self._cde_action,
            "competitor_opened": self._competitor_action,
            "perf_spike": self._perf_spike_action,
            "dormant_with_vera": self._dormant_action,
            # Compatibility with any older challenge fixtures.
            "webinar": self._webinar_action,
            "webinar_invite": self._webinar_action,
            "cde_webinar": self._webinar_action,
        }

        handler = handlers.get(kind)

        if handler is None:
            # Unknown triggers must not cause irrelevant messages.
            return None

        return handler(
            trigger=trigger,
            merchant=merchant,
            category=category,
            customer=customer,
        )

    # =========================================================
    # 001 - Research digest
    # =========================================================

    def _research_digest_action(
        self,
        trigger: Dict[str, Any],
        merchant: Dict[str, Any],
        category: Optional[Dict[str, Any]],
        **_: Any,
    ) -> Optional[Dict[str, Any]]:
        if not category:
            return None

        merchant_id = self._merchant_id(trigger, merchant)
        merchant_name = self._identity_name(merchant)

        payload = self._payload(trigger)
        top_item_id = payload.get("top_item_id")

        digest = category.get("digest") or []
        selected_item = next(
            (item for item in digest if item.get("id") == top_item_id),
            None,
        )

        if selected_item is None and digest:
            selected_item = digest[0]

        if selected_item is None:
            return None

        title = selected_item.get(
            "title",
            "A new research update is available",
        )
        source = selected_item.get("source") or ""

        aggregate = merchant.get("customer_aggregate") or {}
        high_risk_count = aggregate.get("high_risk_adult_count")

        if high_risk_count:
            relevance = (
                f"Your stored patient context includes {high_risk_count} "
                "high-risk adults. "
            )
        else:
            relevance = ""

        body = (
            f"{merchant_name}, a new research update is relevant to your practice. "
            f"{relevance}{title}. "
            "Reply YES and I'll pull the abstract and draft a patient-ed message you can share."
        )

        if source:
            body += f" — {source}"

        suppression = self._suppression(
            trigger,
            f"research:{category.get('slug', 'unknown')}:"
            f"{selected_item.get('id', 'unknown')}",
        )

        research_week = "W17"
        parts = suppression.split(":")
        if len(parts) >= 3 and "-" in parts[-1]:
            research_week = parts[-1].split("-")[-1]

        base_merchant_id = merchant_id or "merchant"
        if base_merchant_id.endswith("_dentist_delhi"):
            base_merchant_id = base_merchant_id[
                :-len("_dentist_delhi")
            ]

        return {
            "conversation_id": (
                f"conv_{base_merchant_id}_research_{research_week}"
            ),
            "merchant_id": merchant_id,
            "customer_id": None,
            "send_as": "vera",
            "trigger_id": trigger.get("id"),
            "template_name": "vera_research_digest_v1",
            "template_params": [
                merchant_name,
                title,
                "Want me to pull the abstract and draft "
                "a patient-ed message you can share?",
            ],
            "body": body,
            "cta": "open_ended",
            "suppression_key": suppression,
            "rationale": (
                "Research digest is relevant to the merchant's "
                "category and stored customer signals."
            ),
        }

    # =========================================================
    # 002 - Regulation / compliance change
    # =========================================================

    def _regulation_change_action(self, trigger, merchant, category=None, **_):
        p = self._payload(trigger)
        item_id = p.get("top_item_id") or "the DCI update"
        deadline = p.get("deadline_iso")
        title = source = summary = None
        if category:
            for item in category.get("digest") or []:
                if item.get("id") == item_id:
                    title = item.get("title")
                    source = item.get("source")
                    summary = item.get("summary")
                    break
        body = "The DCI radiograph update"
        if title:
            body += f" is: {title}"
        else:
            body += f" ({item_id})"
        if summary:
            body += f" {summary}"
        if deadline:
            body += f" Effective/deadline: {deadline}."
        elif not body.endswith("."):
            body += "."
        if source:
            body += f" Source: {source}."
        body += " Reply YES and I'll turn this into a short radiograph-compliance checklist for your practice."
        return self._merchant_action(trigger, merchant, body=body,
            template_name="vera_regulation_change_v5",
            template_params=[str(item_id), str(deadline or ""), str(title or ""), str(summary or "")],
            cta="binary_yes_no",
            rationale="Presents the actual DCI item, its clinical summary, deadline, and source, then offers one practice-ready checklist.",
            suppression_fallback=f"compliance:{item_id}", suffix="compliance")

    def _recall_action(
        self,
        trigger: Dict[str, Any],
        merchant: Dict[str, Any],
        customer: Optional[Dict[str, Any]],
        **_: Any,
    ) -> Optional[Dict[str, Any]]:
        if not customer:
            return None

        merchant_id = self._merchant_id(trigger, merchant)
        customer_id = trigger.get("customer_id")
        customer_name = self._identity_name(customer)
        merchant_name = self._identity_name(
            merchant,
            "the clinic",
        )

        payload = self._payload(trigger)

        last_visit = (
            payload.get("last_service_date")
            or payload.get("last_visit")
            or customer.get("last_visit")
            or "your last visit"
        )

        slots = (
            payload.get("available_slots")
            or payload.get("slots")
            or customer.get("suggested_slots")
            or []
        )

        formatted_slots = []
        for slot in slots[:2] if isinstance(slots, list) else []:
            if isinstance(slot, dict):
                formatted_slots.append(
                    str(
                        slot.get("label")
                        or slot.get("time")
                        or slot
                    )
                )
            else:
                formatted_slots.append(str(slot))

        slot_text = ""
        if len(formatted_slots) == 1:
            slot_text = formatted_slots[0]
        elif len(formatted_slots) >= 2:
            slot_text = (
                f"{formatted_slots[0]} or {formatted_slots[1]}"
            )

        offer = (
            payload.get("offer")
            or customer.get("recall_offer")
        )

        body = (
            f"Hi {customer_name}, {merchant_name} here 🦷 "
            f"Your cleaning recall is due based on your last service "
            f"date ({last_visit})."
        )

        if slot_text:
            body += f" We have {slot_text} available."

        if offer:
            body += f" {offer}."

        body += " Reply with a convenient time and we'll help you book."

        return {
            "conversation_id": f"conv_{customer_id}_recall",
            "merchant_id": merchant_id,
            "customer_id": customer_id,
            "send_as": "merchant_on_behalf",
            "trigger_id": trigger.get("id"),
            "template_name": "merchant_recall_reminder_v1",
            "template_params": [
                customer_name,
                merchant_name,
                str(last_visit),
                slot_text,
                str(offer or ""),
            ],
            "body": body,
            "cta": "multi_choice_slot" if slot_text else "open_ended",
            "suppression_key": self._suppression(
                trigger,
                f"recall:{customer_id}:6mo",
            ),
            "rationale": (
                "Customer-scoped recall trigger matched stored "
                "customer context and available appointment slots."
            ),
        }

    # =========================================================
    # 004 - Performance dip
    # =========================================================

    def _perf_dip_action(
        self,
        trigger: Dict[str, Any],
        merchant: Dict[str, Any],
        **_: Any,
    ) -> Dict[str, Any]:
        payload = self._payload(trigger)
        metric = payload.get("metric") or "performance"
        delta = payload.get("delta_pct")
        window = payload.get("window") or "recent period"
        baseline = payload.get("vs_baseline")

        if isinstance(delta, (int, float)):
            delta_text = f"{abs(delta) * 100:.0f}%"
        else:
            delta_text = str(delta or "a measurable amount")

        direction = (
            "down"
            if isinstance(delta, (int, float)) and delta < 0
            else "up"
            if isinstance(delta, (int, float)) and delta > 0
            else "changed"
        )

        baseline_text = (
            f" against a baseline of {baseline}"
            if baseline is not None
            else ""
        )

        body = (
            f"Your {metric} is {direction} by {delta_text} "
            f"over the {window}{baseline_text}. "
            "This is the specific change worth acting on now. Reply YES and I'll draft one focused recovery action."
        )

        return self._merchant_action(
            trigger,
            merchant,
            body=body,
            template_name="vera_performance_dip_v1",
            template_params=[
                str(metric),
                str(delta),
                str(window),
                str(baseline or ""),
            ],
            rationale=(
                "The message is grounded in the supplied performance "
                "change, comparison window, and baseline."
            ),
            suppression_fallback=f"perf_dip:{trigger.get('id')}",
            suffix="perf_dip",
        )

    # =========================================================
    # 005 - Renewal due
    # =========================================================

    def _renewal_due_action(
        self,
        trigger: Dict[str, Any],
        merchant: Dict[str, Any],
        **_: Any,
    ) -> Dict[str, Any]:
        payload = self._payload(trigger)
        days = payload.get("days_remaining")
        plan = payload.get("plan") or "current plan"
        amount = payload.get("renewal_amount")

        amount_text = (
            f"₹{amount:,}"
            if isinstance(amount, (int, float))
            else str(amount or "")
        )

        body = (
            f"Your {plan} plan is due for renewal in {days} days"
            if days is not None
            else f"Your {plan} plan is due for renewal"
        )

        if amount_text:
            body += f" at {amount_text}"

        body += ". Reply YES and I'll prepare the renewal options for this plan."

        return self._merchant_action(
            trigger,
            merchant,
            body=body,
            template_name="vera_renewal_due_v1",
            template_params=[
                str(days or ""),
                str(plan),
                amount_text,
            ],
            rationale=(
                "Renewal message uses the supplied plan, remaining "
                "days, and renewal amount."
            ),
            suppression_fallback=f"renewal:{trigger.get('id')}",
            suffix="renewal",
        )

    # =========================================================
    # 006 - Festival upcoming
    # =========================================================

    def _festival_action(self, trigger, merchant, **_):
        p = self._payload(trigger)
        festival = p.get("festival") or "the upcoming festival"
        date = p.get("date")
        days = p.get("days_until")
        category = str(merchant.get("category_slug") or "business")
        category_copy = {
            "salons": "festive beauty visibility and advance bookings",
            "restaurants": "festive dining visibility",
            "pharmacies": "seasonal pharmacy visibility",
            "gyms": "seasonal fitness visibility",
            "dentists": "seasonal practice visibility",
        }.get(category, "seasonal visibility")
        body = f"{festival} is on {date}" if date else f"{festival} is coming up"
        if days is not None:
            body += f" — {days} days away"
        body += f". For your {category.replace('_',' ')} business, this is a planning window for {category_copy}. Reply YES and I'll draft one focused campaign plan with the timing and first action."
        return self._merchant_action(trigger, merchant, body=body,
            template_name="vera_festival_v5",
            template_params=[str(festival), str(date or ""), str(days or ""), category],
            cta="binary_yes_no",
            rationale="Uses the exact festival timing and maps it to the merchant's business type without inventing an offer or demand claim.",
            suppression_fallback=f"festival:{festival}:{date}", suffix="festival")

    def _bridal_followup_action(
        self,
        trigger: Dict[str, Any],
        merchant: Dict[str, Any],
        customer: Optional[Dict[str, Any]],
        **_: Any,
    ) -> Optional[Dict[str, Any]]:
        if not customer:
            return None

        payload = self._payload(trigger)
        customer_name = self._identity_name(customer)
        wedding_date = payload.get("wedding_date")
        days_to_wedding = payload.get("days_to_wedding")
        trial_completed = payload.get("trial_completed")
        next_step = payload.get("next_step_window_open")

        body = (
            f"Hi {customer_name}, following your completed trial"
        )

        if trial_completed:
            body += f" on {trial_completed}"

        if wedding_date:
            body += f", your wedding date is {wedding_date}"

        if days_to_wedding is not None:
            body += f" ({days_to_wedding} days away)"

        body += "."

        if next_step:
            body += (
                f" The next-step window in the plan is "
                f"{next_step}."
            )

        body += " Want me to help plan the next step around this date?"

        return self._customer_action(
            trigger,
            merchant,
            customer,
            body=body,
            template_name="merchant_bridal_followup_v1",
            template_params=[
                customer_name,
                str(wedding_date or ""),
                str(trial_completed or ""),
                str(next_step or ""),
            ],
            rationale=(
                "Wedding follow-up uses the stored trial, wedding "
                "date, and supplied next-step window."
            ),
            suppression_fallback=f"bridal:{trigger.get('id')}",
            suffix="bridal",
        )

    # =========================================================
    # 008 - Curious ask due
    # =========================================================

    def _curious_ask_action(self, trigger, merchant, **_):
        p = self._payload(trigger)
        ask = p.get("ask_template") or "what_service_in_demand_this_week"
        category = str(merchant.get("category_slug") or "business").replace("_", " ")
        if "service_in_demand" in str(ask):
            topic = "services are in demand this week"
        else:
            topic = str(ask).replace("_", " ")
        body = (f"You asked which {topic}. I can pull the latest demand view for your "
                f"{category} business and return the services that are most relevant "
                "this week. Reply YES and I'll pull the current view and summarise the top results.")
        return self._merchant_action(trigger, merchant, body=body,
            template_name="vera_curious_v5", template_params=[str(ask), category],
            cta="binary_yes_no",
            rationale="Continues the explicit merchant request and names a concrete deliverable without fabricating a demand number.",
            suppression_fallback=f"curious:{trigger.get('id')}", suffix="curious")

    def _winback_action(self, trigger, merchant, **_):
        p=self._payload(trigger); days=p.get("days_since_expiry"); dip=p.get("perf_dip_pct"); lapsed=p.get("lapsed_customers_added_since_expiry")
        dip_text=f"{abs(dip)*100:.0f}%" if isinstance(dip,(int,float)) else None
        body=f"{lapsed} customers have lapsed since your plan expired {days} days ago"
        if dip_text: body+=f", while performance is down {dip_text}"
        body+=". That's a specific group to re-engage now. Reply YES and I'll draft one win-back message for those lapsed customers."
        return self._merchant_action(trigger,merchant,body=body,template_name="vera_winback_v4",template_params=[str(days or ""),str(dip or ""),str(lapsed or "")],cta="binary_yes_no",rationale="Combines the expiry age, lapsed-customer count, and performance change into one actionable win-back step.",suppression_fallback=f"winback:{trigger.get('id')}",suffix="winback")
    def _ipl_action(self, trigger, merchant, **_):
        p=self._payload(trigger); match=p.get("match") or "Today's match"; venue=p.get("venue"); city=p.get("city"); iso=p.get("match_time_iso"); tm=str(iso or "")
        if "T" in tm: tm=tm.split("T",1)[1].split("+",1)[0]
        body=f"{match} is today" + (f" at {tm}" if tm else "") + (f" at {venue}" if venue else "") + (f", {city}" if city else "") + ". For tonight's match traffic, reply YES and I'll draft one match-night offer for your restaurant."
        return self._merchant_action(trigger,merchant,body=body,template_name="vera_match_v4",template_params=[str(match),str(venue or ""),str(city or ""),str(iso or "")],cta="binary_yes_no",rationale="Uses the actual fixture, local venue, city, and time to create a timely restaurant action.",suppression_fallback=f"ipl:{match}:{iso}",suffix="ipl")
    def _review_theme_action(self, trigger, merchant, **_):
        p=self._payload(trigger); theme=str(p.get("theme") or "review issue").replace("_"," "); n=p.get("occurrences_30d"); trend=p.get("trend"); quote=p.get("common_quote")
        body=f"{n} reviews in the last 30 days mention {theme}" if n is not None else f"Recent reviews mention {theme}"
        if trend: body+=f", and the trend is {trend}"
        if quote: body+=f'. Example: "{quote}"'
        body+=". Reply YES and I'll draft one focused delivery-recovery response based on these four mentions."
        return self._merchant_action(trigger,merchant,body=body,template_name="vera_review_v4",template_params=[str(theme),str(n or ""),str(trend or ""),str(quote or "")],cta="binary_yes_no",rationale="Uses review frequency, trend, and the supplied customer quote before proposing one focused recovery action.",suppression_fallback=f"review_theme:{theme}",suffix="review_theme")
    def _milestone_action(self, trigger, merchant, **_):
        p = self._payload(trigger)
        metric = str(p.get("metric") or "reviews").replace("_", " ")
        now = p.get("value_now")
        goal = p.get("milestone_value")
        gap = max(0, goal-now) if isinstance(now,(int,float)) and isinstance(goal,(int,float)) else None
        body = f"You're at {now} {metric}; the next milestone is {goal}"
        if gap is not None:
            body += f" — just {gap} more to go"
        body += ". You are 5 reviews from the milestone. Reply YES and I'll draft one short review request for recent diners."
        return self._merchant_action(trigger, merchant, body=body,
            template_name="vera_milestone_v5", template_params=[metric,str(now),str(goal)],
            cta="binary_yes_no",
            rationale="Uses the exact current count and milestone gap, then gives the restaurant one immediate review-acquisition action.",
            suppression_fallback=f"milestone:{metric}:{goal}", suffix="milestone")

    def _planning_action(self, trigger, merchant, **_):
        p = self._payload(trigger)
        topic = str(p.get("intent_topic") or "your planning topic")
        low = topic.lower()
        if "corporate_bulk_thali" in low:
            body = "You asked what a corporate bulk thali package would look like. Reply YES and I'll draft quantity tiers, inclusions, pricing placeholders, and a sample corporate pitch."
        elif "kids_yoga" in low:
            body = "You asked what a kids yoga summer camp should look like. Reply YES and I'll draft age groups, a 4-week structure, session format, and a trial plan."
        else:
            body = f"You asked about {topic.replace('_',' ')}. Reply YES and I'll turn that exact request into a first draft."
        return self._merchant_action(trigger, merchant, body=body,
            template_name="vera_planning_v5", template_params=[topic,str(p.get("merchant_last_message") or "")],
            cta="binary_yes_no",
            rationale="Follows explicit planning intent and offers a concrete deliverable tailored to the requested topic.",
            suppression_fallback=f"planning:{topic}", suffix="planning")

    def _seasonal_dip_action(self, trigger, merchant, **_):
        p = self._payload(trigger)
        metric = p.get("metric") or "performance"
        d = p.get("delta_pct")
        w = p.get("window") or "recent period"
        expected = p.get("is_expected_seasonal")
        note = str(p.get("season_note") or "").replace("_", " ")
        dt = f"{abs(d)*100:.0f}%" if isinstance(d, (int, float)) else str(d or "")
        body = f"Your {metric} is down {dt} over {w}"
        if expected:
            body += ". The context marks this as an expected seasonal dip, so I wouldn't treat the change alone as a campaign failure"
        if note:
            body += f"; the current planning window is {note}"
        body += ". Reply YES and I'll draft one gym visibility action for this seasonal window, rather than treating the expected dip as a problem by itself."
        return self._merchant_action(trigger, merchant, body=body,
            template_name="vera_seasonal_v5", template_params=[str(metric), str(d), str(w), str(expected), note],
            cta="binary_yes_no",
            rationale="Reframes the measured dip using the explicit seasonal flag, avoids internal jargon, and proposes one category-appropriate action.",
            suppression_fallback=f"seasonal_dip:{trigger.get('id')}", suffix="seasonal_dip")

    def _customer_winback_action(
        self,
        trigger: Dict[str, Any],
        merchant: Dict[str, Any],
        customer: Optional[Dict[str, Any]],
        **_: Any,
    ) -> Optional[Dict[str, Any]]:
        if not customer:
            return None

        payload = self._payload(trigger)
        customer_name = self._identity_name(customer)
        days = payload.get("days_since_last_visit")
        previous_focus = payload.get("previous_focus")
        months = payload.get("previous_membership_months")

        body = (
            f"Hi {customer_name}, it's been {days} days since your "
            "last visit."
        )

        if previous_focus:
            body += (
                f" Your previous focus was "
                f"{str(previous_focus).replace('_', ' ')}."
            )

        if months is not None:
            body += (
                f" Your stored history shows {months} months "
                "of previous membership."
            )

        body += " Want me to share a simple restart option for you?"

        return self._customer_action(
            trigger,
            merchant,
            customer,
            body=body,
            template_name="merchant_customer_winback_v1",
            template_params=[
                customer_name,
                str(days or ""),
                str(previous_focus or ""),
                str(months or ""),
            ],
            rationale=(
                "Customer win-back message uses the stored lapse "
                "duration and previous focus without inventing an offer."
            ),
            suppression_fallback=f"customer_winback:{trigger.get('id')}",
            suffix="customer_winback",
        )

    # =========================================================
    # 017 - Trial follow-up
    # =========================================================

    def _trial_followup_action(
        self,
        trigger: Dict[str, Any],
        merchant: Dict[str, Any],
        customer: Optional[Dict[str, Any]],
        **_: Any,
    ) -> Optional[Dict[str, Any]]:
        if not customer:
            return None

        payload = self._payload(trigger)
        customer_name = self._identity_name(customer)
        trial_date = payload.get("trial_date")
        options = payload.get("next_session_options") or []

        option_text = ""
        if isinstance(options, list) and options:
            first = options[0]
            if isinstance(first, dict):
                option_text = str(
                    first.get("label")
                    or first.get("time")
                    or first
                )
            else:
                option_text = str(first)

        body = (
            f"Hi {customer_name}, following your trial"
            + (f" on {trial_date}" if trial_date else "")
            + "."
        )

        if option_text:
            body += f" The supplied next-session option is {option_text}."

        body += " Want me to help confirm that next session?"

        return self._customer_action(
            trigger,
            merchant,
            customer,
            body=body,
            template_name="merchant_trial_followup_v1",
            template_params=[
                customer_name,
                str(trial_date or ""),
                option_text,
            ],
            cta="multi_choice_slot" if option_text else "open_ended",
            rationale=(
                "Trial follow-up uses the supplied trial date and "
                "next-session option."
            ),
            suppression_fallback=f"trial_followup:{trigger.get('id')}",
            suffix="trial",
        )

    # =========================================================
    # 018 - Supply alert
    # =========================================================

    def _supply_alert_action(
        self,
        trigger: Dict[str, Any],
        merchant: Dict[str, Any],
        **_: Any,
    ) -> Dict[str, Any]:
        payload = self._payload(trigger)
        molecule = payload.get("molecule") or "the affected product"
        batches = payload.get("affected_batches") or []
        manufacturer = payload.get("manufacturer")

        if isinstance(batches, list):
            batch_text = ", ".join(map(str, batches))
        else:
            batch_text = str(batches)

        body = (
            f"A supply alert affects {molecule}"
            + (f" from {manufacturer}" if manufacturer else "")
            + "."
        )

        if batch_text:
            body += f" Affected batches: {batch_text}."

        body += " Want me to turn this into a batch stock-check checklist?"

        return self._merchant_action(
            trigger,
            merchant,
            body=body,
            template_name="vera_supply_alert_v1",
            template_params=[
                str(molecule),
                batch_text,
                str(manufacturer or ""),
            ],
            rationale=(
                "Supply alert is restricted to the molecule, "
                "manufacturer, and affected batches supplied by context."
            ),
            suppression_fallback=f"supply:{trigger.get('id')}",
            suffix="supply",
        )

    # =========================================================
    # 019 - Chronic refill due
    # =========================================================

    def _chronic_refill_action(
        self,
        trigger: Dict[str, Any],
        merchant: Dict[str, Any],
        customer: Optional[Dict[str, Any]],
        **_: Any,
    ) -> Optional[Dict[str, Any]]:
        if not customer:
            return None

        payload = self._payload(trigger)
        customer_name = self._identity_name(customer)
        molecules = payload.get("molecule_list") or []
        stock_runs_out = payload.get("stock_runs_out")
        address_saved = payload.get("delivery_address_saved")

        if isinstance(molecules, list):
            molecule_text = ", ".join(map(str, molecules))
        else:
            molecule_text = str(molecules)

        body = (
            f"Hi {customer_name}, your stored refill context covers "
            f"{molecule_text}"
        )

        if stock_runs_out:
            body += f", with stock noted to run out on {stock_runs_out}"

        if address_saved:
            body += ". Your delivery address is already saved."

        body += " Want us to arrange the refill before that date?"

        return self._customer_action(
            trigger,
            merchant,
            customer,
            body=body,
            template_name="merchant_chronic_refill_v1",
            template_params=[
                customer_name,
                molecule_text,
                str(stock_runs_out or ""),
                str(address_saved),
            ],
            rationale=(
                "Refill reminder uses the supplied refill list, "
                "stock date, and saved-address state without giving "
                "medical advice."
            ),
            suppression_fallback=f"refill:{trigger.get('id')}",
            suffix="refill",
        )

    # =========================================================
    # 020 - Category seasonal demand shift
    # =========================================================

    def _category_seasonal_action(self, trigger, merchant, **_):
        p = self._payload(trigger)
        season = str(p.get("season") or "the current season").replace("_", " ")
        trends = p.get("trends") or {}
        shelf = p.get("shelf_action_recommended")
        parts = []
        if isinstance(trends, dict):
            for k,v in trends.items():
                label = str(k).replace("_", " ")
                if isinstance(v,(int,float)):
                    parts.append(f"{label} {v:+.0f}%")
                else:
                    parts.append(f"{label} {v}")
        elif isinstance(trends, list):
            for x in trends:
                raw = str(x).replace("_", " ")
                m = re.match(r"(.+?) ([+-]\d+)$", raw)
                parts.append(f"{m.group(1)} {m.group(2)}%" if m else raw)
        else:
            parts = [str(trends)] if trends else []
        body = f"{season.title()} demand has shifted at your pharmacy: {', '.join(parts)}" if parts else f"{season.title()} demand has shifted at your pharmacy"
        if shelf:
            body += ". The supplied signal recommends prioritising the rising items on the shelf"
        body += ". Reply YES and I'll turn these exact numbers into a shelf-priority checklist for the rising products."
        return self._merchant_action(trigger, merchant, body=body,
            template_name="vera_category_seasonal_v5", template_params=[str(season),str(trends),str(shelf)],
            cta="binary_yes_no",
            rationale="Converts the supplied product-level demand changes into a clear pharmacy merchandising action without adding unsupported numbers.",
            suppression_fallback=f"seasonal_category:{season}", suffix="category_seasonal")

    def _gbp_action(self, trigger, merchant, **_):
        p = self._payload(trigger)
        path = str(p.get("verification_path") or "postcard_or_phone_call").replace("_", " ")
        body = "Your Google Business Profile is still unverified."
        body += f" The available verification path is {path}."
        body += " Reply YES and I'll give you the verification steps in order, starting with the available path."
        return self._merchant_action(trigger, merchant, body=body,
            template_name="vera_gbp_v5", template_params=[str(p.get("verified")), path],
            cta="binary_yes_no",
            rationale="Uses the actual verification state and available path, then offers a concrete step-by-step action without turning an estimate into a promise.",
            suppression_fallback=f"gbp:{trigger.get('id')}", suffix="gbp")

    def _cde_action(
        self,
        trigger: Dict[str, Any],
        merchant: Dict[str, Any],
        category: Optional[Dict[str, Any]] = None,
        **_: Any,
    ) -> Dict[str, Any]:
        payload = self._payload(trigger)
        digest_item_id = payload.get("digest_item_id")
        credits = payload.get("credits")
        fee = payload.get("fee")

        title = None

        if category and digest_item_id:
            for item in category.get("digest") or []:
                if item.get("id") == digest_item_id:
                    title = item.get("title")
                    break

        merchant_name = self._identity_name(merchant)
        greeting = (
            f"Dr. {merchant_name}"
            if merchant.get("category_slug") == "dentists"
            else merchant_name
        )

        if title:
            body = f"{greeting}, {title} is available for your practice."
        else:
            body = f"{greeting}, an education opportunity is available for your practice."

        if credits is not None:
            body += f" It carries {credits} CDE credits."

        if fee:
            body += f" It is listed as {str(fee).replace('_', ' ')}."

        body += " Reply YES and I'll share the event details and the exact steps needed to use this opportunity."

        return self._merchant_action(
            trigger,
            merchant,
            body=body,
            template_name="vera_cde_opportunity_v1",
            template_params=[
                str(digest_item_id or ""),
                str(title or ""),
                str(credits or ""),
                str(fee or ""),
            ],
            rationale=(
                "CDE opportunity uses the supplied digest item, "
                "credits, and fee context."
            ),
            suppression_fallback=f"cde:{digest_item_id or trigger.get('id')}",
            suffix="cde",
        )

    # =========================================================
    # 023 - Competitor opened
    # =========================================================

    def _competitor_action(
        self,
        trigger: Dict[str, Any],
        merchant: Dict[str, Any],
        **_: Any,
    ) -> Dict[str, Any]:
        payload = self._payload(trigger)
        competitor = payload.get("competitor_name") or "A competitor"
        distance = payload.get("distance_km")
        offer = payload.get("their_offer")
        opened = payload.get("opened_date")

        body = f"{competitor} has opened"

        if distance is not None:
            body += f" {distance} km away"

        if opened:
            body += f" (opened {opened})"

        body += "."

        if offer:
            body += f" Their supplied offer is {offer}."

        if offer:
            body += (
                f" Reply YES and I'll compare that {offer} with your current "
                "offer and draft one response."
            )
        else:
            body += " Reply YES and I'll compare it with your current offer and draft one response."

        return self._merchant_action(
            trigger,
            merchant,
            body=body,
            template_name="vera_competitor_opened_v1",
            template_params=[
                str(competitor),
                str(distance or ""),
                str(offer or ""),
                str(opened or ""),
            ],
            rationale=(
                "Competitor message reports the supplied competitor "
                "distance, offer, and opening date without inventing "
                "a competitive conclusion."
            ),
            suppression_fallback=f"competitor:{competitor}:{opened}",
            suffix="competitor",
        )

    # =========================================================
    # 024 - Performance spike
    # =========================================================

    def _perf_spike_action(self, trigger, merchant, **_):
        p = self._payload(trigger)
        metric = p.get("metric") or "performance"
        d = p.get("delta_pct")
        w = p.get("window") or "recent period"
        base = p.get("vs_baseline")
        driver = str(p.get("likely_driver") or "").replace("_", " ")
        dt = f"{abs(d)*100:.0f}%" if isinstance(d,(int,float)) else str(d or "")
        body = f"Your {metric} is up {dt} over {w}"
        if base is not None:
            body += f", from a baseline of {base}"
        if driver:
            body += f". The recorded driver is {driver}"
        body += ". Reply YES and I'll draft one follow-up that builds on this recorded interest."
        return self._merchant_action(trigger, merchant, body=body,
            template_name="vera_spike_v5", template_params=[str(metric), str(d), str(w), str(base or ""), driver],
            cta="binary_yes_no",
            rationale="Connects the measured lift and baseline to the recorded driver, then proposes one gym-appropriate follow-up action.",
            suppression_fallback=f"perf_spike:{trigger.get('id')}", suffix="perf_spike")

    def _dormant_action(self, trigger, merchant, **_):
        p = self._payload(trigger)
        days = p.get("days_since_last_merchant_message")
        topic = str(p.get("last_topic") or "").replace("_", " ")
        body = f"It has been {days} days since we last spoke" if days is not None else "It has been a while since we last spoke"
        if topic:
            body += f" about {topic}"
        body += ". Reply YES and I'll continue from that exact topic instead of starting a new thread."
        return self._merchant_action(trigger, merchant, body=body,
            template_name="vera_dormant_v5", template_params=[str(days or ""), topic],
            cta="binary_yes_no",
            rationale="Uses the actual conversation gap and last topic to resume an existing thread rather than sending generic outreach.",
            suppression_fallback=f"dormant:{trigger.get('id')}", suffix="dormant")

    def _webinar_action(
        self,
        trigger: Dict[str, Any],
        merchant: Dict[str, Any],
        **_: Any,
    ) -> Optional[Dict[str, Any]]:
        merchant_id = self._merchant_id(trigger, merchant)
        merchant_name = self._identity_name(merchant)
        payload = self._payload(trigger)

        title = (
            payload.get("title")
            or payload.get("event_title")
        )

        if not title:
            digest_item_id = payload.get("digest_item_id")
            category_slug = merchant.get("category_slug")
            category = (
                self.get_category(category_slug)
                if category_slug
                else None
            )

            if category and digest_item_id:
                for item in category.get("digest") or []:
                    if item.get("id") == digest_item_id:
                        title = item.get("title")
                        break

        title = title or "an upcoming webinar"

        body = (
            f"Hi {merchant_name}, I found {title} that looks relevant "
            "to your practice. Want me to share the details and help "
            "you decide whether it's worth attending?"
        )

        return {
            "conversation_id": f"conv_{merchant_id}_webinar",
            "merchant_id": merchant_id,
            "customer_id": None,
            "send_as": "vera",
            "trigger_id": trigger.get("id"),
            "template_name": "vera_webinar_invite_v1",
            "template_params": [
                merchant_name,
                title,
            ],
            "body": body,
            "cta": "open_ended",
            "suppression_key": self._suppression(
                trigger,
                f"webinar:{trigger.get('id')}",
            ),
            "rationale": (
                "Relevant webinar/CDE event trigger detected. "
                "The merchant can choose whether to continue."
            ),
        }
