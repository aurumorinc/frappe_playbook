import unittest
from frappe_playbook.playbook.doctype.playbook_provider.playbook_provider import PlaybookProviderBase

class TestPlaybookProviderBaseTestExecution(unittest.TestCase):
    def test_base_provider_constraint(self):
        provider = PlaybookProviderBase()
        with self.assertRaises(NotImplementedError):
            provider.queue_test_execution(
                None, "DocType", "Name", {}, "key"
            )
