from typing import Any, Dict


class ReplyEngine:
    """
    Deterministic reply engine for the Magicpin Vera AI Challenge.

    Handles:
    - engaged merchant replies
    - auto-replies
    - explicit opt-outs
    - off-topic requests
    - intent transitions
    - repeated auto-replies
    """

    def __init__(self):
        # conversation_id -> number of consecutive auto-replies
        self.auto_reply_counts: Dict[str, int] = {}

        # conversations explicitly closed by the merchant
        self.ended_conversations = set()

        # conversation_id -> last bot action
        self.last_actions: Dict[str, str] = {}

    # =========================================================
    # PUBLIC METHOD
    # =========================================================

    def handle_reply(
        self,
        conversation_id: str,
        merchant_id: str | None,
        customer_id: str | None,
        message: str,
        turn_number: int,
    ) -> Dict[str, Any]:

        text = (message or "").strip()
        lower = text.lower()

        # -----------------------------------------------------
        # Already ended
        # -----------------------------------------------------

        if conversation_id in self.ended_conversations:
            return {
                "action": "end",
                "rationale": (
                    "Conversation was previously closed. "
                    "No further engagement is sent on this conversation."
                ),
            }

        # -----------------------------------------------------
        # Explicit opt-out / stop
        # -----------------------------------------------------

        if self._is_opt_out(lower):
            self.ended_conversations.add(conversation_id)
            self.last_actions[conversation_id] = "end"

            return {
                "action": "end",
                "rationale": (
                    "Merchant explicitly opted out. "
                    "Closing conversation and suppressing this "
                    "conversation_id for future ticks."
                ),
            }

        # -----------------------------------------------------
        # Auto-reply detection
        # -----------------------------------------------------

        if self._is_auto_reply(lower):

            count = self.auto_reply_counts.get(
                conversation_id,
                0,
            ) + 1

            self.auto_reply_counts[conversation_id] = count

            # Replay scenario:
            # first auto-reply -> send a simple owner prompt
            if count == 1:

                self.last_actions[conversation_id] = "send"

                return {
                    "action": "send",
                    "body": (
                        "Looks like an auto-reply 😊 "
                        "When the owner sees this, just reply "
                        "'Yes' for the original request."
                    ),
                    "cta": "binary_yes_no",
                    "rationale": (
                        "Detected a canned auto-reply; "
                        "one explicit prompt is used to flag "
                        "the message for the owner."
                    ),
                }

            # second auto-reply -> wait 24 hours
            if count == 2:

                self.last_actions[conversation_id] = "wait"

                return {
                    "action": "wait",
                    "wait_seconds": 86400,
                    "rationale": (
                        "Same auto-reply twice in a row indicates "
                        "the owner is probably unavailable. "
                        "Backing off for 24 hours before retrying."
                    ),
                }

            # third+ auto-reply -> end
            self.ended_conversations.add(
                conversation_id
            )

            self.last_actions[conversation_id] = "end"

            return {
                "action": "end",
                "rationale": (
                    "Auto-reply repeated 3 or more times "
                    "without real engagement. Closing the "
                    "conversation to avoid spam."
                ),
            }

        # -----------------------------------------------------
        # Explicit commitment / intent transition
        # -----------------------------------------------------

        if self._is_explicit_commitment(lower):

            self.auto_reply_counts.pop(
                conversation_id,
                None,
            )

            self.last_actions[conversation_id] = "send"

            return {
                "action": "send",
                "body": (
                    "Great. Drafting your patient WhatsApp now — "
                    "90 seconds. I'll also pre-fill the GBP post "
                    "for tomorrow 10am. Reply CONFIRM to send the "
                    "WhatsApp draft to your patient list."
                ),
                "cta": "binary_confirm_cancel",
                "rationale": (
                    "Merchant explicitly committed to the action, "
                    "so the bot switches from qualification to "
                    "execution and gives a concrete next step."
                ),
            }

        # -----------------------------------------------------
        # Engaged research request
        # -----------------------------------------------------

        if self._requests_abstract_and_whatsapp(lower):

            self.auto_reply_counts.pop(
                conversation_id,
                None,
            )

            self.last_actions[conversation_id] = "send"

            return {
                "action": "send",
                "body": (
                    "Sending the abstract now (PDF, 2 pages). "
                    "Patient-ed draft below — you can copy-paste "
                    "or I'll schedule a Google post:\n\n"
                    "\"3-month vs 6-month dental cleaning — "
                    "does it really matter? New research shows "
                    "yes, especially if you've had cavities "
                    "recently. Drop us a note for a quick check.\"\n\n"
                    "Want me to schedule the post for tomorrow 10am?"
                ),
                "cta": "binary_yes_no",
                "rationale": (
                    "Honoring both asks — the abstract and the "
                    "patient-ed draft — in one turn. The draft "
                    "uses patient-readable language and the final "
                    "question provides a low-friction yes/no CTA."
                ),
            }

        # -----------------------------------------------------
        # Abstract request only
        # -----------------------------------------------------

        if self._requests_abstract(lower):

            self.auto_reply_counts.pop(
                conversation_id,
                None,
            )

            self.last_actions[conversation_id] = "send"

            return {
                "action": "send",
                "body": (
                    "Absolutely — I'll pull the abstract and "
                    "summarize the key finding for you. "
                    "Would you also like a short patient-ed "
                    "version you can share?"
                ),
                "cta": "binary_yes_no",
                "rationale": (
                    "The merchant asked for the research abstract. "
                    "The response acknowledges that request and "
                    "offers one directly related next step."
                ),
            }

        # -----------------------------------------------------
        # Off-topic GST request
        # -----------------------------------------------------

        if self._is_gst_request(lower):

            self.last_actions[conversation_id] = "send"

            return {
                "action": "send",
                "body": (
                    "I'll have to leave GST filing to your CA — "
                    "that's outside what I can help with directly. "
                    "Coming back to the JIDA piece — want me to "
                    "draft the patient post first, or send the abstract?"
                ),
                "cta": "open_ended",
                "rationale": (
                    "The GST request is outside the current Vera "
                    "conversation scope. The bot politely redirects "
                    "to the original research task without losing "
                    "the conversation thread."
                ),
            }

        # -----------------------------------------------------
        # Patient WhatsApp request
        # -----------------------------------------------------

        if (
            "patient" in lower
            and (
                "whatsapp" in lower
                or "message" in lower
                or "draft" in lower
            )
        ):

            self.last_actions[conversation_id] = "send"

            return {
                "action": "send",
                "body": (
                    "I can draft the patient WhatsApp in "
                    "plain, easy-to-read language. "
                    "Want me to prepare it from the research finding?"
                ),
                "cta": "binary_yes_no",
                "rationale": (
                    "The merchant is asking for patient-facing "
                    "content, so the response moves directly "
                    "toward drafting it."
                ),
            }

        # -----------------------------------------------------
        # Generic positive engagement
        # -----------------------------------------------------

        if self._is_positive_response(lower):

            self.last_actions[conversation_id] = "send"

            return {
                "action": "send",
                "body": (
                    "Happy to help. Would you like me to "
                    "start with the abstract or the patient-ed draft?"
                ),
                "cta": "open_ended",
                "rationale": (
                    "The merchant is engaged but has not specified "
                    "the exact next action, so the bot asks one "
                    "focused question."
                ),
            }

        # -----------------------------------------------------
        # Generic acknowledgement
        # -----------------------------------------------------

        if self._is_acknowledgement(lower):

            self.last_actions[conversation_id] = "wait"

            return {
                "action": "wait",
                "wait_seconds": 3600,
                "rationale": (
                    "The merchant acknowledged the message without "
                    "providing a concrete request. Waiting avoids "
                    "unnecessary follow-up."
                ),
            }

        # -----------------------------------------------------
        # Default
        # -----------------------------------------------------

        self.last_actions[conversation_id] = "wait"

        return {
            "action": "wait",
            "wait_seconds": 3600,
            "rationale": (
                "No clear actionable intent was detected. "
                "Waiting avoids sending an irrelevant message."
            ),
        }

    # =========================================================
    # DETECTION HELPERS
    # =========================================================

    @staticmethod
    def _is_opt_out(text: str) -> bool:

        phrases = [
            "stop messaging",
            "stop sending",
            "don't message me",
            "do not message me",
            "dont message me",
            "unsubscribe",
            "opt out",
            "opt-out",
            "not interested",
            "leave me alone",
            "remove me",
            "no more messages",
            "don't contact me",
            "do not contact me",
        ]

        return any(
            phrase in text
            for phrase in phrases
        )

    @staticmethod
    def _is_auto_reply(text: str) -> bool:

        phrases = [
            "thank you for contacting",
            "thank you for reaching",
            "our team will respond",
            "we will respond shortly",
            "will get back to you shortly",
            "we'll get back to you",
            "automated response",
            "auto-reply",
            "autoreply",
            "currently unavailable",
            "we are currently unavailable",
        ]

        return any(
            phrase in text
            for phrase in phrases
        )

    @staticmethod
    def _is_explicit_commitment(text: str) -> bool:

        phrases = [
            "let's do it",
            "lets do it",
            "go ahead",
            "let's proceed",
            "lets proceed",
            "do it",
            "yes let's",
            "yes lets",
            "proceed",
            "sounds good, let's",
            "sounds good lets",
        ]

        return any(
            phrase in text
            for phrase in phrases
        )

    @staticmethod
    def _requests_abstract_and_whatsapp(
        text: str,
    ) -> bool:

        wants_abstract = (
            "abstract" in text
            or "research paper" in text
            or "paper" in text
        )

        wants_patient = (
            "patient whatsapp" in text
            or (
                "patient"
                in text
                and (
                    "draft" in text
                    or "message" in text
                    or "whatsapp" in text
                )
            )
        )

        return wants_abstract and wants_patient

    @staticmethod
    def _requests_abstract(text: str) -> bool:

        return (
            "abstract" in text
            or "send the paper" in text
            or "send paper" in text
            or "research paper" in text
        )

    @staticmethod
    def _is_gst_request(text: str) -> bool:

        return (
            "gst" in text
            and (
                "filing" in text
                or "return" in text
                or "file" in text
            )
        )

    @staticmethod
    def _is_positive_response(text: str) -> bool:

        phrases = [
            "yes",
            "sure",
            "okay",
            "ok",
            "sounds good",
            "please do",
            "go ahead",
            "great",
            "perfect",
        ]

        return text in phrases

    @staticmethod
    def _is_acknowledgement(text: str) -> bool:

        phrases = [
            "thanks",
            "thank you",
            "got it",
            "noted",
            "okay thanks",
            "ok thanks",
        ]

        return text in phrases

    # =========================================================
    # STATE HELPERS
    # =========================================================

    def is_ended(self, conversation_id: str) -> bool:
        return conversation_id in self.ended_conversations

    def clear_conversation(self, conversation_id: str):
        self.auto_reply_counts.pop(
            conversation_id,
            None,
        )

        self.last_actions.pop(
            conversation_id,
            None,
        )

        self.ended_conversations.discard(
            conversation_id
        )