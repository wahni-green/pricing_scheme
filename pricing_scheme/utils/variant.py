# Copyright (c) 2023, Wahni IT Solutions Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from erpnext.controllers.item_variant import create_variant, get_variant


@frappe.whitelist()
def get_door_attributes():
	attributes = frappe.db.get_all("Item Attribute", pluck='attribute_name')
	attribute = []
	idx = int(len(attributes) / 2)
	for attr in attributes:
		attribute_name = str(attr).lower().replace(" ", "_")
		attribute.append({
			"label": attr,
			"fieldname": attribute_name,
			"fieldtype": 'Select',
			"options": frappe.db.get_all("Item Attribute Value", {"parent": attr}, pluck="attribute_value", order_by="attribute_value asc"),
			"reqd": 0,
			"hidden": 1,
			"default": ""
		})
		idx -= 1
		if not idx:
			attribute.append({
				"fieldname": 'col_break_' + str(idx),
				"fieldtype": 'Column Break'
			})

	return attribute


@frappe.whitelist()
def get_door_variant(model, attributes):
	item = get_variant(model, args=attributes)
	if not item:
		variant = create_variant(model, args=attributes)
		variant.has_serial_no = 1
		variant.serial_no_series = model + "-.YYYY.-.#####"
		variant.save()
		return variant.name

	return item


@frappe.whitelist()
def get_model_attributes(model):
	attributes = frappe.db.get_all("Item Variant Attribute", filters={'parent': model}, pluck='attribute')
	attribute = {}
	for attr in attributes:
		attribute_name = str(attr).lower().replace(" ", "_")
		attribute[attribute_name] = attr

	return attribute


@frappe.whitelist()
def get_default_attributes_value(model, attribute, doc):
	so_items = frappe.parse_json(doc)
	for row in reversed(so_items):
		if row.get('variant') == model:
			return frappe.db.get_value('Item Variant Attribute', {
				'parent': row['item_code'],
				'attribute': attribute
				}, 'attribute_value')
	item = frappe.db.get_all('Sales Order Item', filters={
		"variant": model
	}, fields=['item_code'], page_length=1, order_by='creation desc')
	if item:
		return frappe.db.get_value('Item Variant Attribute', {
			'parent': item[0]['item_code'],
			'attribute': attribute
		}, 'attribute_value')
