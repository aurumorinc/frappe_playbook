import unittest
from unittest.mock import patch, call, MagicMock
import frappe
from frappe_playbook.playbook.doctype.playbook.playbook import trigger_test_execution

class TestPlaybookTestExecutionUnit(unittest.TestCase):
    def setUp(self):
        self.playbook_doc = MagicMock()
        self.playbook_doc.name = "Test Playbook"
        self.playbook_doc.document_type = "Test Doc"
        self.playbook_doc.provider = None
        self.playbook_doc.meets_condition.return_value = True

    @patch("frappe_playbook.playbook.doctype.playbook.playbook.frappe.utils.now", return_value="2024-01-01 12:00:00")
    @patch("frappe_playbook.playbook.doctype.playbook.playbook.frappe.get_doc")
    @patch("frappe_playbook.playbook.doctype.playbook.playbook.frappe.get_all")
    @patch("frappe_playbook.playbook.doctype.playbook_execution.playbook_execution.queue_trigger_execution")
    def test_prioritizes_waiting_executions(self, mock_queue, mock_get_all, mock_get_doc, mock_now):
        # Arrange
        # mock_get_doc should return the playbook first, then the target doc
        target_doc = MagicMock()
        target_doc.doctype = "Test Doc"
        target_doc.name = "TEST-001"
        target_doc.as_dict.return_value = {"name": "TEST-001"}
        
        def side_effect(doctype, name=None):
            if doctype == "Playbook":
                return self.playbook_doc
            return target_doc
            
        mock_get_doc.side_effect = side_effect
        
        waiting_exec = frappe._dict({
            "reference_doctype": "Test Doc",
            "reference_name": "TEST-001"
        })
        mock_get_all.return_value = [waiting_exec]

        # Act
        result = trigger_test_execution("Test Playbook")

        # Assert
        self.assertEqual(result.get("status"), "success")
        mock_queue.assert_called_once()
        args = mock_queue.call_args[0]
        self.assertEqual(args[0], self.playbook_doc)
        self.assertEqual(args[1], "Test Doc")
        self.assertEqual(args[2], "TEST-001")
        self.assertEqual(args[3], {"doc": {"name": "TEST-001"}})
        self.assertTrue(args[4].startswith("test-Test Playbook-"))
        
        # Verify get_all was called for Playbook Execution
        mock_get_all.assert_called_once_with(
            "Playbook Execution",
            filters={"playbook": "Test Playbook", "status": "waiting"},
            fields=["reference_doctype", "reference_name"],
            order_by="creation desc",
            limit=1
        )

    @patch("frappe_playbook.playbook.doctype.playbook.playbook.frappe.utils.now", return_value="2024-01-01 12:00:00")
    @patch("frappe_playbook.playbook.doctype.playbook.playbook.frappe.get_doc")
    @patch("frappe_playbook.playbook.doctype.playbook.playbook.frappe.get_all")
    @patch("frappe_playbook.playbook.doctype.playbook_execution.playbook_execution.queue_trigger_execution")
    def test_fallback_to_condition_matching(self, mock_queue, mock_get_all, mock_get_doc, mock_now):
        # Arrange
        doc1 = MagicMock()
        doc1.name = "TEST-002"
        doc1.doctype = "Test Doc"
        
        doc2 = MagicMock()
        doc2.name = "TEST-003"
        doc2.doctype = "Test Doc"
        doc2.as_dict.return_value = {"name": "TEST-003"}
        
        def meets_condition_side_effect(doc):
            return doc.name == "TEST-003"
            
        self.playbook_doc.meets_condition.side_effect = meets_condition_side_effect
        
        def get_all_side_effect(doctype, **kwargs):
            if doctype == "Playbook Execution":
                return []
            return [frappe._dict({"name": "TEST-002"}), frappe._dict({"name": "TEST-003"})]
            
        mock_get_all.side_effect = get_all_side_effect
        
        def get_doc_side_effect(doctype, name=None):
            if doctype == "Playbook":
                return self.playbook_doc
            if name == "TEST-002":
                return doc1
            if name == "TEST-003":
                return doc2
            return None
            
        mock_get_doc.side_effect = get_doc_side_effect

        # Act
        result = trigger_test_execution("Test Playbook")

        # Assert
        self.assertEqual(result.get("status"), "success")
        mock_queue.assert_called_once()
        self.assertEqual(mock_queue.call_args[0][2], "TEST-003")

    @patch("frappe_playbook.playbook.doctype.playbook.playbook.frappe.get_doc")
    @patch("frappe_playbook.playbook.doctype.playbook.playbook.frappe.get_all")
    @patch("frappe_playbook.playbook.doctype.playbook_execution.playbook_execution.queue_trigger_execution")
    def test_no_documents_found(self, mock_queue, mock_get_all, mock_get_doc):
        # Arrange
        mock_get_doc.return_value = self.playbook_doc
        mock_get_all.return_value = []
        
        # Act
        result = trigger_test_execution("Test Playbook")

        # Assert
        self.assertEqual(result, {"status": "failed", "message": "No matching document found."})
        mock_queue.assert_not_called()

    @patch("frappe_playbook.playbook.doctype.playbook.playbook.frappe.utils.now", return_value="2024-01-01 12:00:00")
    @patch("frappe_playbook.playbook.doctype.playbook.playbook.get_provider_instance")
    @patch("frappe_playbook.playbook.doctype.playbook.playbook.frappe.get_doc")
    @patch("frappe_playbook.playbook.doctype.playbook.playbook.frappe.get_all")
    @patch("frappe_playbook.playbook.doctype.playbook_execution.playbook_execution.queue_trigger_execution")
    def test_external_provider_routing(self, mock_queue, mock_get_all, mock_get_doc, mock_get_provider, mock_now):
        # Arrange
        self.playbook_doc.provider = "n8n"
        
        target_doc = MagicMock()
        target_doc.doctype = "Test Doc"
        target_doc.name = "TEST-001"
        target_doc.as_dict.return_value = {"name": "TEST-001"}
        
        def get_doc_side_effect(doctype, name=None):
            if doctype == "Playbook":
                return self.playbook_doc
            return target_doc
            
        mock_get_doc.side_effect = get_doc_side_effect
        
        mock_get_all.return_value = [frappe._dict({"reference_doctype": "Test Doc", "reference_name": "TEST-001"})]
        
        fake_provider = MagicMock()
        mock_get_provider.return_value = fake_provider

        # Act
        trigger_test_execution("Test Playbook")

        # Assert
        mock_queue.assert_not_called()
        fake_provider.queue_test_execution.assert_called_once()
        self.assertEqual(fake_provider.queue_test_execution.call_args[0][0], self.playbook_doc)
        self.assertEqual(fake_provider.queue_test_execution.call_args[0][1], "Test Doc")
        self.assertEqual(fake_provider.queue_test_execution.call_args[0][2], "TEST-001")
