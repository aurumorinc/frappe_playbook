# Copyright (c) 2026, Aquiveal and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase


# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]



class IntegrationTestPlaybook(IntegrationTestCase):
	"""
	Integration tests for Playbook.
	Use this class for testing interactions between multiple components.
	"""
	def setUp(self):
		super().setUp()
		frappe.db.delete("Playbook")
		frappe.db.delete("Playbook Event")

	def test_meets_condition_python(self):
		import frappe
		doc = frappe.get_doc({"doctype": "ToDo", "status": "Open"})
		playbook = frappe.get_doc({
			"doctype": "Playbook",
			"playbook_name": "Test Python Condition",
			"document_type": "ToDo",
			"condition_type": "Python",
			"condition": "doc.status == 'Open'"
		})
		self.assertTrue(playbook.meets_condition(doc))

		doc.status = "Closed"
		self.assertFalse(playbook.meets_condition(doc))

	def test_meets_condition_filters(self):
		import frappe
		doc = frappe.get_doc({"doctype": "ToDo", "status": "Open"})
		playbook = frappe.get_doc({
			"doctype": "Playbook",
			"playbook_name": "Test Filters Condition",
			"document_type": "ToDo",
			"condition_type": "Filters",
			"filters": [
				{
					"fieldname": "status",
					"operator": "=",
					"value": "Open"
				}
			]
		})
		self.assertTrue(playbook.meets_condition(doc))

		doc.status = "Closed"
		self.assertFalse(playbook.meets_condition(doc))

	def test_meets_condition_invalid_filters(self):
		import frappe
		doc = frappe.get_doc({"doctype": "ToDo", "status": "Open"})
		playbook = frappe.get_doc({
			"doctype": "Playbook",
			"playbook_name": "Test Invalid Filters Condition",
			"document_type": "ToDo",
			"condition_type": "Filters",
			"filters": [
				{
					"fieldname": "status",
					"operator": "invalid_operator",
					"value": "Open"
				}
			]
		})
		self.assertFalse(playbook.meets_condition(doc))

	def test_on_trash_deletes_workflow(self):
		import frappe
		from unittest.mock import patch

		try:
			frappe.get_doc({"doctype": "Playbook Provider", "provider_name": "Dummy"}).insert()
		except (frappe.UniqueValidationError, frappe.DuplicateEntryError):
			pass

		playbook = frappe.get_doc({
			"doctype": "Playbook",
			"playbook_name": "Test Trash Playbook",
			"document_type": "ToDo",
			"provider": "Dummy",
			"dummy_workflow_id": "123"
		}).insert()

		with patch("frappe_playbook.playbook.doctype.playbook.playbook.enqueue") as mock_enqueue:
			with patch("frappe_playbook.playbook.doctype.playbook.playbook.Playbook.get", return_value="123"):
				playbook.delete()
			mock_enqueue.assert_called_once()
			args, kwargs = mock_enqueue.call_args
			self.assertEqual(args[0], "frappe_playbook.playbook.doctype.playbook_provider.playbook_provider.delete_workflow")
			self.assertEqual(kwargs["provider"], "Dummy")
			self.assertEqual(kwargs["workflow_id"], "123")

	def test_create_playbook_event(self):
		import frappe
		from frappe_playbook.playbook.doctype.playbook.playbook import create_playbook_event

		# Cleanup existing events for this doc
		frappe.db.delete("Playbook Event", {"reference_doctype": "ToDo", "event_type": "New"})

		doc = frappe.get_doc({"doctype": "ToDo", "status": "Open", "description": "Test"}).insert()

		playbook_name = "Test Trigger Playbook"
		if frappe.db.exists("Playbook", playbook_name):
			frappe.delete_doc("Playbook", playbook_name)

		playbook = frappe.get_doc({
			"doctype": "Playbook",
			"playbook_name": playbook_name,
			"document_type": "ToDo",
			"doc_event": "New",
			"status": "Enabled",
			"is_active": 1,
			"condition_type": "Python",
			"condition": "doc.status == 'Open'"
		}).insert()

		create_playbook_event(doc, "after_insert")
		
		events = frappe.get_all("Playbook Event", filters={"reference_doctype": "ToDo", "reference_name": doc.name, "event_type": "New"})
		self.assertEqual(len(events), 1)
