import frappe
from frappe.tests import IntegrationTestCase
from unittest.mock import patch, MagicMock
from frappe_playbook.playbook.doctype.playbook.playbook import create_playbook_event
from frappe_playbook.playbook.doctype.playbook_event.playbook_event import queue_trigger_execution

class TestPlaybookEvent(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not frappe.db.exists("DocType", "ToDo"):
            frappe.throw("ToDo DocType not found")

    @classmethod
    def tearDownClass(cls):
        frappe.db.rollback()
        super().tearDownClass()

    def tearDown(self):
        frappe.db.rollback()

    def test_create_playbook_event_on_insert(self):
        # Create active playbook
        playbook = frappe.get_doc({
            "doctype": "Playbook",
            "playbook_name": "Test Event Insert",
            "document_type": "ToDo",
            "doc_event": "New",
            "status": "Enabled",
            "is_active": 1
        }).insert(ignore_links=True)

        # Insert a ToDo
        todo = frappe.get_doc({
            "doctype": "ToDo",
            "description": "Test Insert Event"
        }).insert(ignore_links=True)

        # Check if Playbook Event was created
        events = frappe.get_all("Playbook Event", filters={"reference_doctype": "ToDo", "reference_name": todo.name, "event_type": "New"})
        self.assertTrue(len(events) > 0)

    def test_no_event_if_no_active_playbook(self):
        # Ensure no active playbooks for ToDo Save
        frappe.db.set_value("Playbook", {"document_type": "ToDo", "doc_event": "Save"}, "is_active", 0)

        todo = frappe.get_doc({
            "doctype": "ToDo",
            "description": "Test No Event"
        }).insert(ignore_links=True)
        
        # Update to trigger Save
        todo.description = "Updated"
        todo.save()

        events = frappe.get_all("Playbook Event", filters={"reference_doctype": "ToDo", "reference_name": todo.name, "event_type": "Save"})
        self.assertEqual(len(events), 0)

    def test_no_event_for_ignored_doctypes(self):
        playbook = frappe.get_doc({
            "doctype": "Playbook",
            "playbook_name": "Test Ignored Doctype",
            "document_type": "Error Log",
            "doc_event": "New",
            "status": "Enabled",
            "is_active": 1
        }).insert(ignore_links=True)

        error_log = frappe.get_doc({
            "doctype": "Error Log",
            "error": "Test Error"
        }).insert(ignore_links=True)

        events = frappe.get_all("Playbook Event", filters={"reference_doctype": "Error Log", "reference_name": error_log.name})
        self.assertEqual(len(events), 0)

    def test_no_event_during_import(self):
        playbook = frappe.get_doc({
            "doctype": "Playbook",
            "playbook_name": "Test Import Flag",
            "document_type": "ToDo",
            "doc_event": "New",
            "status": "Enabled",
            "is_active": 1
        }).insert(ignore_links=True)

        frappe.flags.in_import = True
        try:
            todo = frappe.get_doc({
                "doctype": "ToDo",
                "description": "Test Import"
            }).insert(ignore_links=True)
        finally:
            frappe.flags.in_import = False

        events = frappe.get_all("Playbook Event", filters={"reference_doctype": "ToDo", "reference_name": todo.name, "event_type": "New"})
        self.assertEqual(len(events), 0)

    @patch("frappe_playbook.playbook.doctype.playbook_provider.playbook_provider.get_provider_instance")
    def test_queue_execution_with_provider(self, mock_get_provider):
        playbook = frappe.get_doc({
            "doctype": "Playbook",
            "playbook_name": "Test Queue Provider",
            "document_type": "ToDo",
            "doc_event": "New",
            "status": "Enabled",
            "is_active": 1,
            "provider": "DummyProvider"
        }).insert(ignore_links=True)

        todo = frappe.get_doc({
            "doctype": "ToDo",
            "description": "Test Queue"
        }).insert(ignore_links=True)

        event = frappe.get_doc({
            "doctype": "Playbook Event",
            "reference_doctype": "ToDo",
            "reference_name": todo.name,
            "event_type": "New"
        }).insert(ignore_links=True)

        mock_provider = MagicMock()
        mock_get_provider.return_value = mock_provider

        queue_trigger_execution(event.name)

        # It might be called multiple times if other tests created active playbooks
        self.assertTrue(mock_provider.queue_trigger_execution.call_count >= 1)

    @patch("frappe_playbook.playbook.doctype.playbook_execution.playbook_execution.queue_trigger_execution")
    def test_queue_execution_native(self, mock_native_queue):
        playbook = frappe.get_doc({
            "doctype": "Playbook",
            "playbook_name": "Test Queue Native",
            "document_type": "ToDo",
            "doc_event": "New",
            "status": "Enabled",
            "is_active": 1
        }).insert(ignore_links=True)

        todo = frappe.get_doc({
            "doctype": "ToDo",
            "description": "Test Queue Native"
        }).insert(ignore_links=True)

        event = frappe.get_doc({
            "doctype": "Playbook Event",
            "reference_doctype": "ToDo",
            "reference_name": todo.name,
            "event_type": "New"
        }).insert(ignore_links=True)

        queue_trigger_execution(event.name)

        self.assertTrue(mock_native_queue.call_count >= 1)

    @patch("frappe_playbook.playbook.doctype.playbook_execution.playbook_execution.queue_trigger_execution")
    def test_concurrency_idempotency_key_generation(self, mock_native_queue):
        playbook = frappe.get_doc({
            "doctype": "Playbook",
            "playbook_name": f"Test Concurrency {frappe.generate_hash()}",
            "document_type": "ToDo",
            "doc_event": "New",
            "status": "Enabled",
            "is_active": 1
        }).insert(ignore_links=True)

        todo = frappe.get_doc({
            "doctype": "ToDo",
            "description": "Test Concurrency"
        }).insert(ignore_links=True)

        # todo.insert() already created one event, let's get it
        event1_name = frappe.get_all("Playbook Event", filters={"reference_name": todo.name})[0].name
        event1 = frappe.get_doc("Playbook Event", event1_name)
        
        # Create a second event manually to simulate concurrency
        event2 = frappe.get_doc({
            "doctype": "Playbook Event",
            "reference_doctype": "ToDo",
            "reference_name": todo.name,
            "event_type": "New"
        }).insert(ignore_links=True)

        queue_trigger_execution(event1.name)
        queue_trigger_execution(event2.name)

        self.assertTrue(mock_native_queue.call_count >= 2)
        
        # Filter calls for our specific playbook
        calls = [call for call in mock_native_queue.call_args_list if call[0][0].name == playbook.name]
        self.assertTrue(len(calls) >= 2)
        
        # Check that the idempotency keys are unique per event
        args1, kwargs1 = calls[0]
        args2, kwargs2 = calls[1]
        
        idempotency_key1 = args1[4]
        idempotency_key2 = args2[4]
        
        self.assertNotEqual(idempotency_key1, idempotency_key2)
        self.assertEqual(idempotency_key1, f"{playbook.name}-{event1.name}")
        self.assertEqual(idempotency_key2, f"{playbook.name}-{event2.name}")
