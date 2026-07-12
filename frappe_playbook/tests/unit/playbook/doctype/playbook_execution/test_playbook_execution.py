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
            "status": "Enabled",
            "enabled": 1
        }).insert()
        todo = frappe.get_doc({"doctype": "ToDo", "description": "test"}).insert()

        execution = frappe.get_doc({
            "doctype": "Playbook Execution",
            "name": f"test-{frappe.generate_hash(length=8)}",
            "playbook": playbook.name,
            "reference_doctype": "ToDo",
            "reference_name": todo.name,
            "status": "running"
        }).insert(ignore_permissions=True, ignore_links=True)

        execution.status = "success"
        execution.save()
        self.assertEqual(execution.status, "success")

    def test_invalid_status_transition(self):
        playbook = frappe.get_doc({
            "doctype": "Playbook",
            "playbook_name": "Test Playbook",
            "document_type": "ToDo",
            "doc_event": "after_insert",
            "status": "Enabled",
            "enabled": 1
        }).insert()
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

    @patch("frappe_playbook.playbook.doctype.playbook_execution.playbook_execution.get_provider_instance")
    def test_cancel_calls_provider_stop(self, mock_get_provider):
        playbook = frappe.get_doc({
            "doctype": "Playbook",
            "playbook_name": "Test Cancel Playbook",
            "document_type": "ToDo",
            "doc_event": "after_insert",
            "status": "Enabled",
            "enabled": 1,
            "provider": "DummyProvider"
        }).insert(ignore_links=True)

        todo = frappe.get_doc({"doctype": "ToDo", "description": "test"}).insert()

        execution = frappe.get_doc({
            "doctype": "Playbook Execution",
            "name": f"test-{frappe.generate_hash(length=8)}",
            "playbook": playbook.name,
            "reference_doctype": "ToDo",
            "reference_name": todo.name,
            "status": "running"
        }).insert(ignore_permissions=True, ignore_links=True)

        mock_provider = MagicMock()
        mock_get_provider.return_value = mock_provider

        execution.status = "canceled"
        execution.save()

        mock_provider.stop_execution.assert_called_once_with(execution)

    @patch("frappe_playbook.playbook.doctype.playbook_execution.playbook_execution.frappe.msgprint")
    @patch("frappe_playbook.playbook.doctype.playbook_execution.playbook_execution.frappe.log_error")
    @patch("frappe_playbook.playbook.doctype.playbook_execution.playbook_execution.get_provider_instance")
    def test_cancel_allows_failure_in_provider_stop(self, mock_get_provider, mock_log_error, mock_msgprint):
        playbook = frappe.get_doc({
            "doctype": "Playbook",
            "playbook_name": "Test Cancel Fail Playbook",
            "document_type": "ToDo",
            "doc_event": "after_insert",
            "status": "Enabled",
            "enabled": 1,
            "provider": "DummyProvider"
        }).insert(ignore_links=True)

        todo = frappe.get_doc({"doctype": "ToDo", "description": "test"}).insert()

        execution = frappe.get_doc({
            "doctype": "Playbook Execution",
            "name": f"test-{frappe.generate_hash(length=8)}",
            "playbook": playbook.name,
            "reference_doctype": "ToDo",
            "reference_name": todo.name,
            "status": "running"
        }).insert(ignore_permissions=True, ignore_links=True)

        mock_provider = MagicMock()
        mock_provider.stop_execution.side_effect = Exception("Provider Error")
        mock_get_provider.return_value = mock_provider

        execution.status = "canceled"
        execution.save()

        self.assertEqual(execution.status, "canceled")
        mock_log_error.assert_called_once()
        mock_msgprint.assert_called_once()

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
