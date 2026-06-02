import frappe
from frappe.tests import IntegrationTestCase
from unittest.mock import patch, call
from frappe_playbook.playbook.doctype.playbook_execution.playbook_execution import queue_trigger_execution, queue_resume_execution

class TestPlaybookExecution(IntegrationTestCase):
    @patch("frappe_playbook.playbook.doctype.playbook_execution.playbook_execution.enqueue")
    def test_queue_trigger_execution(self, mock_enqueue):
        playbook_doc = frappe.get_doc({"doctype": "Playbook", "playbook_name": "Test Playbook", "document_type": "ToDo", "name": "Test Playbook"})
        payload = {"data": "test"}
        idempotency_key = "test-key"
        
        queue_trigger_execution(playbook_doc, "ToDo", "TASK-001", payload, idempotency_key)
        
        mock_enqueue.assert_called_once_with(
            "frappe_playbook.playbook.doctype.playbook_execution.playbook_execution.run",
            playbook_name="Test Playbook",
            reference_doctype="ToDo",
            reference_name="TASK-001",
            payload=payload,
            idempotency_key=idempotency_key,
            as_child=True
        )
        
    @patch("frappe_playbook.playbook.doctype.playbook_execution.playbook_execution.get_provider_instance")
    def test_on_cancel_stops_execution(self, mock_get_provider):
        try:
            frappe.get_doc({"doctype": "Playbook Provider", "provider_name": "Dummy"}).insert()
        except (frappe.UniqueValidationError, frappe.DuplicateEntryError):
            pass

        playbook_doc = frappe.get_doc({"doctype": "Playbook", "playbook_name": "Test Cancel Playbook", "document_type": "ToDo", "provider": "Dummy"}).insert()
        execution_doc = frappe.get_doc({"doctype": "Playbook Execution", "playbook": "Test Cancel Playbook", "name": "EXEC-CANCEL-001"}).insert()

        mock_provider = mock_get_provider.return_value
        execution_doc.status = "canceled"
        execution_doc.save()

        mock_provider.stop_execution.assert_called_once_with(execution_doc)

    @patch("frappe_playbook.playbook.doctype.playbook_execution.playbook_execution.emit_event")
    def test_queue_resume_execution(self, mock_emit_event):
        execution_doc = frappe.get_doc({"doctype": "Playbook Execution", "playbook": "Test Playbook", "name": "EXEC-001"})
        response_body = '{"status": "approved"}'
        
        queue_resume_execution(execution_doc, response_body)
        
        mock_emit_event.assert_called_once_with(
            key="playbook_resume_EXEC-001",
            argument={"response": response_body}
        )
