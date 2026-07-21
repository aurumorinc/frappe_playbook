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

    def test_cancel_and_delete_execution(self):
        playbook = frappe.get_doc({
            "doctype": "Playbook",
            "playbook_name": f"Test Cancel Playbook {frappe.generate_hash()}",
            "document_type": "ToDo",
            "doc_event": "after_insert",
            "status": "Enabled",
            "enabled": 1
        }).insert(ignore_links=True)

        todo = frappe.get_doc({
            "doctype": "ToDo",
            "description": "Test Cancel Execution"
        }).insert()

        execution = frappe.get_doc({
            "doctype": "Playbook Execution",
            "name": f"test-cancel-{frappe.generate_hash(length=8)}",
            "playbook": playbook.name,
            "reference_doctype": "ToDo",
            "reference_name": todo.name,
            "status": "running"
        }).insert(ignore_permissions=True, ignore_links=True)

        # Call cancel on execution doc
        self.assertTrue(execution.cancel())
        self.assertEqual(execution.status, "canceled")

        # Idempotency check: cancelling again returns False
        self.assertFalse(execution.cancel())

        # Calling delete should remove the document
        execution.delete()
        self.assertFalse(frappe.db.exists("Playbook Execution", execution.name))

    def test_playbook_cascade_on_delete(self):
        playbook = frappe.get_doc({
            "doctype": "Playbook",
            "playbook_name": f"Test Cascade PB {frappe.generate_hash()}",
            "document_type": "ToDo",
            "doc_event": "after_insert",
            "status": "Enabled",
            "enabled": 1
        }).insert(ignore_links=True)

        todo = frappe.get_doc({
            "doctype": "ToDo",
            "description": "Test Cascade"
        }).insert()

        event = frappe.get_doc({
            "doctype": "Playbook Event",
            "playbook": playbook.name,
            "reference_doctype": "ToDo",
            "reference_name": todo.name,
            "event_type": "after_insert"
        }).insert(ignore_permissions=True, ignore_links=True)

        execution = frappe.get_doc({
            "doctype": "Playbook Execution",
            "name": f"test-cascade-{frappe.generate_hash(length=8)}",
            "playbook": playbook.name,
            "playbook_event": event.name,
            "reference_doctype": "ToDo",
            "reference_name": todo.name,
            "status": "running"
        }).insert(ignore_permissions=True, ignore_links=True)

        # Deleting Playbook should cascade delete the Playbook Event and Playbook Execution
        frappe.delete_doc("Playbook", playbook.name, ignore_permissions=True)

        self.assertFalse(frappe.db.exists("Playbook", playbook.name))
        self.assertFalse(frappe.db.exists("Playbook Event", event.name))
        self.assertFalse(frappe.db.exists("Playbook Execution", execution.name))

    def test_event_cascade_on_delete(self):
        playbook = frappe.get_doc({
            "doctype": "Playbook",
            "playbook_name": f"Test Event Cascade PB {frappe.generate_hash()}",
            "document_type": "ToDo",
            "doc_event": "after_insert",
            "status": "Enabled",
            "enabled": 1
        }).insert(ignore_links=True)

        todo = frappe.get_doc({
            "doctype": "ToDo",
            "description": "Test Event Cascade"
        }).insert()

        event = frappe.get_doc({
            "doctype": "Playbook Event",
            "playbook": playbook.name,
            "reference_doctype": "ToDo",
            "reference_name": todo.name,
            "event_type": "after_insert"
        }).insert(ignore_permissions=True, ignore_links=True)

        execution = frappe.get_doc({
            "doctype": "Playbook Execution",
            "name": f"test-event-cascade-{frappe.generate_hash(length=8)}",
            "playbook": playbook.name,
            "playbook_event": event.name,
            "reference_doctype": "ToDo",
            "reference_name": todo.name,
            "status": "running"
        }).insert(ignore_permissions=True, ignore_links=True)

        # Deleting Playbook Event should cascade delete Playbook Execution
        frappe.delete_doc("Playbook Event", event.name, ignore_permissions=True)

        self.assertFalse(frappe.db.exists("Playbook Event", event.name))
        self.assertFalse(frappe.db.exists("Playbook Execution", execution.name))

    def test_bulk_cancel_and_delete(self):
        playbook = frappe.get_doc({
            "doctype": "Playbook",
            "playbook_name": f"Test Bulk PB {frappe.generate_hash()}",
            "document_type": "ToDo",
            "doc_event": "after_insert",
            "status": "Enabled",
            "enabled": 1
        }).insert(ignore_links=True)

        todo = frappe.get_doc({
            "doctype": "ToDo",
            "description": "Test Bulk"
        }).insert()

        execution1 = frappe.get_doc({
            "doctype": "Playbook Execution",
            "name": f"test-bulk1-{frappe.generate_hash(length=8)}",
            "playbook": playbook.name,
            "reference_doctype": "ToDo",
            "reference_name": todo.name,
            "status": "running"
        }).insert(ignore_permissions=True, ignore_links=True)

        execution2 = frappe.get_doc({
            "doctype": "Playbook Execution",
            "name": f"test-bulk2-{frappe.generate_hash(length=8)}",
            "playbook": playbook.name,
            "reference_doctype": "ToDo",
            "reference_name": todo.name,
            "status": "queued"
        }).insert(ignore_permissions=True, ignore_links=True)

        from frappe_playbook.playbook.doctype.playbook_execution.playbook_execution import cancel_bulk, delete_bulk

        # Cancel bulk for this specific playbook
        cancel_bulk({"playbook": playbook.name})

        doc1 = frappe.get_doc("Playbook Execution", execution1.name)
        doc2 = frappe.get_doc("Playbook Execution", execution2.name)

        self.assertEqual(doc1.status, "canceled")
        self.assertEqual(doc2.status, "canceled")

        # Delete bulk
        delete_bulk({"playbook": playbook.name})

        self.assertFalse(frappe.db.exists("Playbook Execution", execution1.name))
        self.assertFalse(frappe.db.exists("Playbook Execution", execution2.name))
