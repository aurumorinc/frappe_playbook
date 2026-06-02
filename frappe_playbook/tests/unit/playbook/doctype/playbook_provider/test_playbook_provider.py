import frappe
from frappe.tests import IntegrationTestCase
from frappe_playbook.playbook.doctype.playbook_provider.playbook_provider import get_provider_instance, PlaybookProviderBase
from unittest.mock import patch

class DummyProvider(PlaybookProviderBase):
    pass

class TestPlaybookProvider(IntegrationTestCase):
    def test_get_provider_instance_invalid(self):
        with self.assertRaises(frappe.ValidationError):
            get_provider_instance("Invalid")
            
    @patch("frappe.get_hooks")
    def test_get_provider_instance_valid(self, mock_get_hooks):
        mock_get_hooks.return_value = {"Dummy": ["frappe_playbook.tests.unit.playbook.doctype.playbook_provider.test_playbook_provider.DummyProvider"]}
        provider = get_provider_instance("Dummy")
        self.assertIsInstance(provider, DummyProvider)
