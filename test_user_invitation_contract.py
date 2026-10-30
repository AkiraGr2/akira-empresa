import ast
import os
from pathlib import Path
import unittest
from unittest.mock import patch
import akira_auth

NEXUS = Path("nexus.py")

class UserInvitationContractTests(unittest.TestCase):
    SECRET = "s" * 48
    NOW = 1_800_000_000

    @classmethod
    def setUpClass(cls):
        cls.source = NEXUS.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def _function_source(self, name):
        node = next(
            n for n in self.tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name
        )
        return ast.get_source_segment(self.source, node)

    def test_default_owner_and_authorized_emails_in_akira_auth(self):
        owners = akira_auth.owner_emails(["bjhon9161@gmail.com"])
        authorized = akira_auth.authorized_emails(["jnicolaslp41@gmail.com"])
        self.assertIn("bjhon9161@gmail.com", owners)
        self.assertIn("jnicolaslp41@gmail.com", authorized)
        self.assertNotIn("unauthorized@example.com", authorized)

    def test_owner_session_issued_and_verified(self):
        with patch.dict(
            os.environ,
            {
                "AKIRA_SESSION_SECRET": self.SECRET,
                "OWNER_EMAILS": "bjhon9161@gmail.com",
            },
            clear=False,
        ):
            token, exp, reason = akira_auth.issue_session(
                "sub-owner-1",
                "bjhon9161@gmail.com",
                role="owner",
                now=self.NOW,
            )
            self.assertIsNotNone(token)
            self.assertIsNone(reason)

            session = akira_auth.verify_session(
                token,
                default_owner_emails=("bjhon9161@gmail.com",),
                now=self.NOW + 1,
            )
            self.assertIsNotNone(session)
            self.assertEqual(session["email"], "bjhon9161@gmail.com")
            self.assertTrue(session["is_owner"])
            self.assertTrue(session["is_authorized"])
            self.assertEqual(session["role"], "owner")
            self.assertEqual(session["permissions"], ["*"])
            self.assertEqual(session["owner_scope"], "owner")

    def test_authorized_friend_session_issued_and_verified(self):
        with patch.dict(
            os.environ,
            {
                "AKIRA_SESSION_SECRET": self.SECRET,
                "OWNER_EMAILS": "bjhon9161@gmail.com",
                "AUTHORIZED_EMAILS": "jnicolaslp41@gmail.com",
            },
            clear=False,
        ):
            token, exp, reason = akira_auth.issue_session(
                "sub-friend-2",
                "jnicolaslp41@gmail.com",
                role="authorized",
                now=self.NOW,
            )
            self.assertIsNotNone(token)
            self.assertIsNone(reason)

            session = akira_auth.verify_session(
                token,
                default_owner_emails=("bjhon9161@gmail.com",),
                now=self.NOW + 1,
            )
            self.assertIsNotNone(session)
            self.assertEqual(session["email"], "jnicolaslp41@gmail.com")
            self.assertFalse(session["is_owner"])
            self.assertTrue(session["is_authorized"])
            self.assertEqual(session["role"], "authorized")
            self.assertIn("chat", session["permissions"])
            self.assertIn("trading", session["permissions"])
            self.assertNotIn("*", session["permissions"])
            self.assertNotEqual(session["owner_scope"], "owner")

    def test_nexus_has_authorized_emails_and_strict_auth_google(self):
        self.assertIn('AUTHORIZED_EMAILS=["jnicolaslp41@gmail.com"]', self.source)
        source_auth_google = self._function_source("auth_google")
        self.assertIn("acceso_no_autorizado", source_auth_google)
        self.assertIn("status_code=403", source_auth_google)
        self.assertIn("role = ", source_auth_google)
        self.assertIn("permissions = ", source_auth_google)

    def test_nexus_v8_me_returns_role_and_permissions(self):
        source_v8_me = self._function_source("v8_me")
        self.assertIn('s["is_owner"]', source_v8_me)
        self.assertIn('"is_authorized": is_authorized', source_v8_me)
        self.assertIn('"role": role', source_v8_me)
        self.assertIn('"permissions": permissions', source_v8_me)

if __name__ == "__main__":
    unittest.main()
