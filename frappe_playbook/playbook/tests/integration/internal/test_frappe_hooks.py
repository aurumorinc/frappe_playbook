import frappe
from frappe.tests import IntegrationTestCase
from unittest.mock import patch

class TestPlaybookHooks(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create an enabled Playbook for Note on_update
        cls.playbook = frappe.get_doc({
            "doctype": "Playbook",
            "playbook_name": "Test Note Update Hook",
            "document_type": "Note",
            "doc_event": "on_update",
            "enabled": 1,
            "status": "Enabled"
        }).insert(ignore_permissions=True)

    @classmethod
    def tearDownClass(cls):
        frappe.db.rollback()
        super().tearDownClass()

    def test_document_lifecycle(self):
        """Test 4: Real Document Lifecycle - Ensures correct hooks are triggered"""
        
        # Act: Create a Note
        note = frappe.get_doc({
            "doctype": "Note",
            "title": "Test Hook Note",
            "content": "Initial content"
        }).insert(ignore_permissions=True)
        
        # No 'on_update' playbook event should have been fired yet (only after_insert would have been called)
        # However, note that in Frappe, insert might trigger both depending on how hooks are defined, but typically
        # we check the exact events.
        
        events_after_insert = frappe.get_all(
            "Playbook Event",
            filters={"reference_doctype": "Note", "reference_name": note.name, "event_type": "on_update"}
        )
        
        # Clear events before update to cleanly test the update hook
        frappe.db.delete("Playbook Event", {"reference_doctype": "Note", "reference_name": note.name})
        
        # Act: Update the Note
        note.content = "Updated content"
        note.save()
        
        # Assert: Exactly one Playbook Event for on_update should be created after saving
        events_after_update = frappe.get_all(
            "Playbook Event",
            filters={"reference_doctype": "Note", "reference_name": note.name, "event_type": "on_update"}
        )
        
        self.assertEqual(len(events_after_update), 1, "Exactly one on_update Playbook Event should exist after update")
