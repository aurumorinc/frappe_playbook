import frappe
from frappe.tests import IntegrationTestCase
from unittest.mock import patch, MagicMock
from frappe_playbook.playbook.doctype.todo.todo import on_update

class TestToDoIntegration(IntegrationTestCase):
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

    @patch("frappe_playbook.playbook.doctype.todo.todo.native_queue_resume_execution")
    def test_resume_execution_native(self, mock_native_resume):
        playbook = frappe.get_doc({
            "doctype": "Playbook",
            "playbook_name": "Test ToDo Native",
            "document_type": "ToDo",
            "doc_event": "after_insert",
            "status": "Enabled",
            "enabled": 1
        }).insert(ignore_links=True)

        execution = frappe.get_doc({
            "doctype": "Playbook Execution",
            "name": f"test-{frappe.generate_hash(length=8)}",
            "playbook": playbook.name,
            "reference_doctype": "ToDo",
            "reference_name": "Test",
            "status": "waiting"
        }).insert(ignore_permissions=True, ignore_links=True)

        todo = frappe.get_doc({
            "doctype": "ToDo",
            "description": "Test ToDo Native",
            "status": "Open",
            "playbook_execution": execution.name,
            "response_body": '{"result": "ok"}'
        }).insert(ignore_links=True)

        # Simulate closing the ToDo
        todo.status = "Closed"
        todo.save()

        mock_native_resume.assert_called_once()
        args, kwargs = mock_native_resume.call_args
        self.assertEqual(args[0].name, execution.name)
        self.assertEqual(args[1], '{"result": "ok"}')

    @patch("frappe_playbook.playbook.doctype.todo.todo.native_queue_resume_execution")
    def test_no_resume_if_not_closed(self, mock_native_resume):
        playbook = frappe.get_doc({
            "doctype": "Playbook",
            "playbook_name": "Test ToDo Not Closed",
            "document_type": "ToDo",
            "doc_event": "after_insert",
            "status": "Enabled",
            "enabled": 1
        }).insert(ignore_links=True)

        execution = frappe.get_doc({
            "doctype": "Playbook Execution",
            "name": f"test-{frappe.generate_hash(length=8)}",
            "playbook": playbook.name,
            "reference_doctype": "ToDo",
            "reference_name": "Test",
            "status": "waiting"
        }).insert(ignore_permissions=True, ignore_links=True)

        todo = frappe.get_doc({
            "doctype": "ToDo",
            "description": "Test ToDo Not Closed",
            "status": "Open",
            "playbook_execution": execution.name
        }).insert(ignore_links=True)

        # Update without closing
        todo.description = "Updated description"
        todo.save()

        mock_native_resume.assert_not_called()
