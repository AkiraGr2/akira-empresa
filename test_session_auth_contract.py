import os
import unittest
from unittest.mock import patch

import akira_auth


class SessionAuthContractTests(unittest.TestCase):
    SECRET = "s" * 48
    NOW = 1_800_000_000

    def test_issue_and_verify_owner_session(self):
        with patch.dict(
            os.environ,
            {
                "AKIRA_SESSION_SECRET": self.SECRET,
                "OWNER_EMAILS": "owner@example.com",
            },
            clear=False,
        ):
            token, exp, reason = akira_auth.issue_session(
                "google-sub-123",
                "owner@example.com",
                now=self.NOW,
            )
            self.assertIsNotNone(token)
            self.assertEqual(reason, None)
            self.assertEqual(exp, self.NOW + akira_auth.SESSION_TTL_SECONDS)

            session = akira_auth.verify_session(
                token,
                default_owner_emails=(),
                now=self.NOW + 1,
            )

        self.assertIsNotNone(session)
        self.assertEqual(session["sub"], "google-sub-123")
        self.assertEqual(session["email"], "owner@example.com")
        self.assertTrue(session["is_owner"])
        self.assertEqual(session["owner_scope"], "owner")
        self.assertEqual(session["exp"], exp)

    def test_owner_status_is_derived_from_server_owner_list(self):
        with patch.dict(
            os.environ,
            {
                "AKIRA_SESSION_SECRET": self.SECRET,
                "OWNER_EMAILS": "owner@example.com",
            },
            clear=False,
        ):
            token, _, _ = akira_auth.issue_session(
                "google-sub-456",
                "attacker@example.com",
                now=self.NOW,
            )
            session = akira_auth.verify_session(
                token,
                default_owner_emails=(),
                now=self.NOW + 1,
            )

        self.assertIsNotNone(session)
        self.assertFalse(session["is_owner"])

    def test_tampering_and_expiry_fail_closed(self):
        with patch.dict(
            os.environ,
            {
                "AKIRA_SESSION_SECRET": self.SECRET,
                "OWNER_EMAILS": "",
            },
            clear=False,
        ):
            token, exp, _ = akira_auth.issue_session(
                "google-sub-789",
                "user@example.com",
                now=self.NOW,
            )
            body, signature = token.split(".", 1)
            tampered = body + "x." + signature

            self.assertIsNone(
                akira_auth.verify_session(
                    tampered,
                    default_owner_emails=(),
                    now=self.NOW + 1,
                )
            )
            self.assertIsNone(
                akira_auth.verify_session(
                    token,
                    default_owner_emails=(),
                    now=exp,
                )
            )

    def test_bearer_header_parser_requires_valid_scheme_and_token(self):
        with patch.dict(
            os.environ,
            {
                "AKIRA_SESSION_SECRET": self.SECRET,
                "OWNER_EMAILS": "",
            },
            clear=False,
        ):
            token, _, _ = akira_auth.issue_session(
                "google-sub-header",
                "user@example.com",
                now=self.NOW,
            )
            valid = akira_auth.session_from_header(
                "Bearer " + token,
                default_owner_emails=(),
                now=self.NOW + 1,
            )
            invalid_scheme = akira_auth.session_from_header(
                "Basic " + token,
                default_owner_emails=(),
                now=self.NOW + 1,
            )
            missing = akira_auth.session_from_header(
                None,
                default_owner_emails=(),
                now=self.NOW + 1,
            )

        self.assertIsNotNone(valid)
        self.assertEqual(valid["owner_scope"], "g:google-sub-header")
        self.assertIsNone(invalid_scheme)
        self.assertIsNone(missing)

    def test_missing_or_short_secret_never_issues_session(self):
        with patch.dict(
            os.environ,
            {
                "AKIRA_SESSION_SECRET": "too-short",
            },
            clear=False,
        ):
            token, exp, reason = akira_auth.issue_session(
                "google-sub-secret",
                "user@example.com",
                now=self.NOW,
            )

        self.assertIsNone(token)
        self.assertIsNone(exp)
        self.assertEqual(reason, "session_secret_missing_or_short")


if __name__ == "__main__":
    unittest.main()
