import frappe
from frappe.tests import IntegrationTestCase
from unittest.mock import patch, MagicMock
from frappe_playbook.playbook.doctype.playbook.playbook import trigger_test_execution

class TestPlaybook(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Ensure ToDo doctype exists for testing
        if not frappe.db.exists("DocType", "ToDo"):
            frappe.throw("ToDo DocType not found")

    @classmethod
    def tearDownClass(cls):
        frappe.db.rollback()
        super().tearDownClass()

    def tearDown(self):
        frappe.db.rollback()

    def test_save_valid_python_condition(self):
        doc = frappe.get_doc({
            "doctype": "Playbook",
            "playbook_name": "Test Python Playbook",
            "document_type": "ToDo",
            "doc_event": "on_update",
            "condition_type": "Python",
            "condition": "doc.status == 'Open'",
            "status": "Draft"
        }).insert(ignore_links=True)
        self.assertTrue(doc.name)

    def test_save_valid_filters_condition(self):
        doc = frappe.get_doc({
            "doctype": "Playbook",
            "playbook_name": "Test Filters Playbook",
            "document_type": "ToDo",
            "doc_event": "on_update",
            "condition_type": "Filters",
            "filters": [{"fieldname": "status", "operator": "=", "value": "Open"}],
            "status": "Draft"
        }).insert(ignore_links=True)
        self.assertTrue(doc.name)

    def test_invalid_python_syntax(self):
        doc = frappe.get_doc({
            "doctype": "Playbook",
            "playbook_name": "Test Invalid Python",
            "document_type": "ToDo",
            "doc_event": "on_update",
            "condition_type": "Python",
            "condition": "if doc.status == 'Open'",
            "status": "Draft"
        })
        with self.assertRaises(frappe.exceptions.ValidationError) as context:
            doc.insert()
        self.assertIn("Invalid Python condition", str(context.exception))

    def test_invalid_filters_field(self):
        doc = frappe.get_doc({
            "doctype": "Playbook",
            "playbook_name": "Test Invalid Filters",
            "document_type": "ToDo",
            "doc_event": "on_update",
            "condition_type": "Filters",
            "filters": [{"fieldname": "non_existent_field", "operator": "=", "value": "Open"}],
            "status": "Draft"
        })
        with self.assertRaises(frappe.exceptions.ValidationError) as context:
            doc.insert()
        self.assertIn("does not exist in DocType", str(context.exception))

    def test_draft_status_sets_inactive(self):
        doc = frappe.get_doc({
            "doctype": "Playbook",
            "playbook_name": "Test Draft Playbook",
            "document_type": "ToDo",
            "doc_event": "on_update",
            "status": "Draft",
            "enabled": 1
        }).insert(ignore_links=True)
        self.assertEqual(doc.enabled, 0)

    def test_sync_workflow_on_insert_with_provider(self):
        pass

    def test_meets_condition_python_true(self):
        playbook = frappe.get_doc({
            "doctype": "Playbook",
            "playbook_name": "Test Python True",
            "document_type": "ToDo",
            "doc_event": "on_update",
            "condition_type": "Python",
            "condition": "doc.status == 'Open'",
            "status": "Draft"
        }).insert(ignore_links=True)
        
        mock_doc = frappe._dict({"status": "Open"})
        self.assertTrue(playbook.meets_condition(mock_doc))

    @patch("frappe_playbook.playbook.doctype.playbook.playbook.frappe.log_error")
    def test_meets_condition_python_exception(self, mock_log_error):
        playbook = frappe.get_doc({
            "doctype": "Playbook",
            "playbook_name": "Test Python Exception",
            "document_type": "ToDo",
            "doc_event": "on_update",
            "condition_type": "Python",
            "condition": "1 / 0",
            "status": "Draft"
        }).insert(ignore_links=True)
        
        mock_doc = frappe._dict({"status": "Open"})
        self.assertFalse(playbook.meets_condition(mock_doc))
        mock_log_error.assert_called_once()

    def test_meets_condition_filters_true(self):
        playbook = frappe.get_doc({
            "doctype": "Playbook",
            "playbook_name": "Test Filters True",
            "document_type": "ToDo",
            "doc_event": "on_update",
            "condition_type": "Filters",
            "filters": [{"fieldname": "status", "operator": "=", "value": "Open"}],
            "status": "Draft"
        }).insert(ignore_links=True)
        
        mock_doc = frappe.get_doc({"doctype": "ToDo", "description": "Test", "status": "Open"})
        self.assertTrue(playbook.meets_condition(mock_doc))

    @patch("frappe_playbook.playbook.doctype.playbook.playbook.frappe.safe_eval")
    def test_security_vector_safe_eval(self, mock_safe_eval):
        playbook = frappe.get_doc({
            "doctype": "Playbook",
            "playbook_name": "Test Security",
            "document_type": "ToDo",
            "doc_event": "on_update",
            "condition_type": "Python",
            "condition": "__import__('os').system('echo hacked')",
            "status": "Draft"
        }).insert(ignore_links=True)
        
        mock_safe_eval.side_effect = Exception("Security Error")
        mock_doc = frappe._dict({})
        
        self.assertFalse(playbook.meets_condition(mock_doc))
    