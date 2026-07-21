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
            "doc_event": "after_insert",
            "status": "Enabled",
            "enabled": 1
        }).insert(ignore_links=True)

        # Insert a ToDo
        todo = frappe.get_doc({
            "doctype": "ToDo",
            "description": "Test Insert Event"
        }).insert(ignore_links=True)

        # Check if Playbook Event was created
        events = frappe.get_all("Playbook Event", filters={"reference_doctype": "ToDo", "reference_name": todo.name, "event_type": "after_insert"})
        self.assertTrue(len(events) > 0)

    def test_no_event_if_no_active_playbook(self):
        # Ensure no active playbooks for ToDo Save
        frappe.db.set_value("Playbook", {"document_type": "ToDo", "doc_event": "on_update"}, "enabled", 0)

        todo = frappe.get_doc({
            "doctype": "ToDo",
            "description": "Test No Event"
        }).insert(ignore_links=True)
        
        # Update to trigger Save
        todo.description = "Updated"
        todo.save()

        events = frappe.get_all("Playbook Event", filters={"reference_doctype": "ToDo", "reference_name": todo.name, "event_type": "on_update"})
        self.assertEqual(len(events), 0)

    def test_no_event_for_ignored_doctypes(self):
        playbook = frappe.get_doc({
            "doctype": "Playbook",
            "playbook_name": "Test Ignored Doctype",
            "document_type": "Error Log",
            "doc_event": "after_insert",
            "status": "Enabled",
            "enabled": 1
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
            "doc_event": "after_insert",
            "status": "Enabled",
            "enabled": 1
        }).insert(ignore_links=True)

        frappe.flags.in_import = True
        try:
            todo = frappe.get_doc({
                "doctype": "ToDo",
                "description": "Test Import"
            }).insert(ignore_links=True)
        finally:
            frappe.flags.in_import = False

        events = frappe.get_all("Playbook Event", filters={"reference_doctype": "ToDo", "reference_name": todo.name, "event_type": "after_insert"})
        self.assertEqual(len(events), 0)

    @patch("frappe_playbook.playbook.doctype.playbook_execution.playbook_execution.queue_trigger_execution")
    def test_queue_execution_native(self, mock_native_queue):
        playbook = frappe.get_doc({
            "doctype": "Playbook",
            "playbook_name": "Test Queue Native",
            "document_type": "ToDo",
            "doc_event": "after_insert",
            "status": "Enabled",
            "enabled": 1
        }).insert(ignore_links=True)

        todo = frappe.get_doc({
            "doctype": "ToDo",
            "description": "Test Queue Native"
        }).insert(ignore_links=True)

        event = frappe.get_doc({
            "doctype": "Playbook Event",
            "playbook": playbook.name,
            "reference_doctype": "ToDo",
            "reference_name": todo.name,
            "event_type": "after_insert"
        }).insert(ignore_links=True)

        queue_trigger_execution(event.name)

        self.assertTrue(mock_native_queue.call_count >= 1)

    @patch("frappe_playbook.playbook.doctype.playbook_execution.playbook_execution.queue_trigger_execution")
    def test_concurrency_execution_name_generation(self, mock_native_queue):
        playbook = frappe.get_doc({
            "doctype": "Playbook",
            "playbook_name": f"Test Concurrency {frappe.generate_hash()}",
            "document_type": "ToDo",
            "doc_event": "after_insert",
            "status": "Enabled",
            "enabled": 1
        }).insert(ignore_links=True)

        todo = frappe.get_doc({
            "doctype": "ToDo",
            "description": "Test Concurrency"
        }).insert(ignore_links=True)

        # todo.insert() already created one event, let's get it specifically for our playbook
        event1_name = frappe.get_all("Playbook Event", filters={"reference_name": todo.name, "playbook": playbook.name})[0].name
        event1 = frappe.get_doc("Playbook Event", event1_name)
        
        # Create a second event manually to simulate concurrency
        event2 = frappe.get_doc({
            "doctype": "Playbook Event",
            "playbook": playbook.name,
            "reference_doctype": "ToDo",
            "reference_name": todo.name,
            "event_type": "after_insert"
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
        
        execution_name1 = args1[4]
        execution_name2 = args2[4]
        
        self.assertNotEqual(execution_name1, execution_name2)
        self.assertEqual(len(execution_name1), 10)
        self.assertEqual(len(execution_name2), 10)

    def test_playbook_event_enqueue_as_child_false(self):
        job_type_name = frappe.db.exists("Controller Job Type", {"method": "parent_job_test"})
        if not job_type_name:
            job_type = frappe.get_doc({
                "doctype": "Controller Job Type",
                "method": "parent_job_test",
                "create_log": 1
            }).insert(ignore_permissions=True)
            job_type_name = job_type.name

        parent_job = frappe.get_doc({
            "doctype": "FS Job",
            "job_type": job_type_name,
            "job_name": "parent_job_test",
            "status": "queued",
            "queue": "low"
        }).insert(ignore_permissions=True)

        frappe.flags.current_job_id = parent_job.name
        frappe.flags.current_job_step = 1

        try:
            event = frappe.get_doc({
                "doctype": "Playbook Event",
                "reference_doctype": "ToDo",
                "reference_name": "SomeName",
                "event_type": "after_insert"
            }).insert(ignore_links=True)

            enqueued_jobs = frappe.get_all(
                "FS Job",
                filters={"job_name": "frappe_playbook.playbook.doctype.playbook_event.playbook_event.queue_trigger_execution"},
                fields=["name", "parent_job", "idx"]
            )
            target_job = None
            for j in enqueued_jobs:
                doc = frappe.get_doc("FS Job", j.name)
                import json
                args = json.loads(doc.arguments or "{}")
                if args.get("event_name") == event.name:
                    target_job = j
                    break

            self.assertIsNotNone(target_job)
            self.assertIsNone(target_job.get("parent_job"))
            self.assertEqual(frappe.flags.current_job_step, 1)
        finally:
            frappe.flags.current_job_id = None
            frappe.flags.current_job_step = None

    def test_disabled_playbook_event_waiting(self):
        from frappe_controller.utils.controller import SuspendJob
        
        playbook = frappe.get_doc({
            "doctype": "Playbook",
            "playbook_name": f"Test Disabled Wait {frappe.generate_hash()}",
            "document_type": "ToDo",
            "doc_event": "after_insert",
            "status": "Disabled",
            "enabled": 0
        }).insert(ignore_links=True)

        todo = frappe.get_doc({
            "doctype": "ToDo",
            "description": "Test Disabled Wait"
        }).insert(ignore_links=True)

        event = frappe.get_doc({
            "doctype": "Playbook Event",
            "reference_doctype": "ToDo",
            "reference_name": todo.name,
            "event_type": "after_insert",
            "playbook": playbook.name
        }).insert(ignore_links=True)

        job_type_name = frappe.db.exists("Controller Job Type", {"method": "test_waiting_job"})
        if not job_type_name:
            job_type = frappe.get_doc({
                "doctype": "Controller Job Type",
                "method": "test_waiting_job",
                "create_log": 1
            }).insert(ignore_permissions=True)
            job_type_name = job_type.name

        job = frappe.get_doc({
            "doctype": "FS Job",
            "job_type": job_type_name,
            "job_name": "test_waiting_job",
            "status": "queued",
            "queue": "low"
        }).insert(ignore_permissions=True)

        frappe.flags.current_job_id = job.name
        try:
            with self.assertRaises(SuspendJob):
                queue_trigger_execution(event.name)

            match_conditions = frappe.get_all(
                "FS Match Condition",
                filters={
                    "job": job.name,
                    "event_key": f"doc:Playbook:on_update:{playbook.name}",
                    "is_satisfied": 0
                }
            )
            self.assertEqual(len(match_conditions), 1)
        finally:
            frappe.flags.current_job_id = None

