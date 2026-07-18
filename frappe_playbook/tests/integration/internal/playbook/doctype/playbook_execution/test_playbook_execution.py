import frappe
from frappe.tests import IntegrationTestCase
from unittest.mock import patch, MagicMock
from frappe_playbook.playbook.doctype.playbook_execution.playbook_execution import run

class TestPlaybookExecution(IntegrationTestCase):
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

    def test_valid_status_transition(self):
        playbook = frappe.get_doc({
            "doctype": "Playbook",
            "playbook_name": "Test Playbook",
            "document_type": "ToDo",
            "doc_event": "after_insert",
            "provider": "",
            "status": "Enabled",
            "enabled": 1
        }).insert(ignore_permissions=True)
        # Ensure provider is empty so n8n hooks ignore it
        playbook.db_set("provider", "")
        todo = frappe.get_doc({"doctype": "ToDo", "description": "test"}).insert()

        execution = frappe.get_doc({
            "doctype": "Playbook Execution",
            "name": f"test-{frappe.generate_hash(length=8)}",
            "playbook": playbook.name,
            "reference_doctype": "ToDo",
            "reference_name": todo.name,
            "status": "queued"
        }).insert(ignore_permissions=True, ignore_links=True)

        execution.status = "running"
        execution.save()
        self.assertEqual(execution.status, "running")

    def test_invalid_status_transition(self):
        playbook = frappe.get_doc({
            "doctype": "Playbook",
            "playbook_name": "Test Playbook",
            "document_type": "ToDo",
            "doc_event": "after_insert",
            "provider": "",
            "status": "Enabled",
            "enabled": 1
        }).insert(ignore_permissions=True)
        playbook.db_set("provider", "")
        todo = frappe.get_doc({"doctype": "ToDo", "description": "test"}).insert()
        
        execution = frappe.get_doc({
            "doctype": "Playbook Execution",
            "name": f"test-{frappe.generate_hash(length=8)}",
            "playbook": playbook.name,
            "reference_doctype": "ToDo",
            "reference_name": todo.name,
            "status": "success"
        }).insert(ignore_permissions=True, ignore_links=True)

        execution.status = "running"
        with self.assertRaises(frappe.exceptions.ValidationError) as context:
            execution.save()
        self.assertIn("Invalid status transition", str(context.exception))

    def test_native_execution_idempotency(self):
        execution_name = "test-idempotency-key"
        
        playbook = frappe.get_doc({
            "doctype": "Playbook",
            "playbook_name": f"Test Idempotency Playbook {frappe.generate_hash()}",
            "document_type": "ToDo",
            "doc_event": "after_insert",
            "status": "Enabled",
            "enabled": 1
        }).insert(ignore_links=True)

        todo = frappe.get_doc({
            "doctype": "ToDo",
            "description": "Test Idempotency"
        }).insert()

        # First run
        run(playbook.name, "ToDo", todo.name, {}, execution_name)
        
        executions = frappe.get_all("Playbook Execution", filters={"name": execution_name})
        self.assertEqual(len(executions), 1)
        
        # Second run with same key
        run(playbook.name, "ToDo", todo.name, {}, execution_name)
        
        executions_after = frappe.get_all("Playbook Execution", filters={"name": execution_name})
        self.assertEqual(len(executions_after), 1)
