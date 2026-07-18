import frappe
from frappe.tests import UnitTestCase
from frappe_playbook.playbook.doctype.playbook.playbook import create_playbook_event

class TestPlaybookEvents(UnitTestCase):
    @classmethod
    def tearDownClass(cls):
        frappe.db.rollback()
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        # Create a mock playbook for our tests
        self.playbook = frappe.get_doc({
            "doctype": "Playbook",
            "playbook_name": "Test Webhook Options Playbook",
            "document_type": "ToDo",
            "doc_event": "after_insert",
            "enabled": 1,
            "status": "Enabled"
        }).insert(ignore_permissions=True)

    def tearDown(self):
        frappe.db.rollback()
        super().tearDown()

    def test_event_mapping_consistency(self):
        """Test 1: Event Mapping Consistency - matches exactly"""
        # Arrange
        todo = frappe.get_doc({
            "doctype": "ToDo",
            "description": "Test ToDo for Playbook"
        }).insert(ignore_permissions=True)
        
        # Act: manually call the event function
        create_playbook_event(todo, "after_insert")
        
        # Assert: verify event was created
        events = frappe.get_all(
            "Playbook Event", 
            filters={"reference_doctype": "ToDo", "reference_name": todo.name, "event_type": "after_insert"}
        )
        self.assertTrue(len(events) > 0, "Playbook Event was not created for after_insert")

    def test_ignored_methods(self):
        """Test 2: Ignored Methods - mismatched method creates no events"""
        # Arrange
        todo = frappe.get_doc({
            "doctype": "ToDo",
            "description": "Test ToDo 2"
        }).insert(ignore_permissions=True)
        
        # Act: call with a method that the playbook is NOT configured for
        create_playbook_event(todo, "on_submit")
        
        # Assert
        events = frappe.get_all(
            "Playbook Event", 
            filters={"reference_doctype": "ToDo", "reference_name": todo.name, "event_type": "on_submit"}
        )
        self.assertEqual(len(events), 0, "Playbook Event should NOT have been created")

    def test_disabled_playbook_ignore(self):
        """Test 3: Disabled Playbook Ignore"""
        # Arrange: create a disabled playbook
        frappe.get_doc({
            "doctype": "Playbook",
            "playbook_name": "Test Disabled Playbook",
            "document_type": "ToDo",
            "doc_event": "on_trash",
            "enabled": 0,
            "status": "Disabled"
        }).insert(ignore_permissions=True)
        
        todo = frappe.get_doc({
            "doctype": "ToDo",
            "description": "Test ToDo 3"
        }).insert(ignore_permissions=True)
        
        # Act
        create_playbook_event(todo, "on_trash")
        
        # Assert
        events = frappe.get_all(
            "Playbook Event", 
            filters={"reference_doctype": "ToDo", "reference_name": todo.name, "event_type": "on_trash"}
        )
        self.assertEqual(len(events), 0, "Disabled playbooks should not create events")
