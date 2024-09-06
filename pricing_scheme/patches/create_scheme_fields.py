# Copyright (c) 2024, Wahni IT Solutions Pvt Ltd and contributors
# For license information, please see license.txt

from frappe import make_property_setter
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    create_custom_fields(
        {
            "Pricing Rule": [
                {
                    "fieldname": "auto_apply_scheme",
                    "label": "Auto Apply Scheme",
                    "fieldtype": "Check",
                    "insert_after": "coupon_code_based",
                },
                {
                    "fieldname": "allow_skipping",
                    "label": "Allow Skipping Scheme",
                    "fieldtype": "Check",
                    "insert_after": "auto_apply_scheme",
                },
                {
                    "fieldname": "qty_based_on",
                    "label": "Qty Based On",
                    "fieldtype": "Select",
                    "options": "Stock\nWeight",
                    "insert_after": "max_qty",
                    "default": "Stock",
                },
                {
                    "fieldname": "free_qty_type",
                    "label": "Free Qty Type",
                    "fieldtype": "Select",
                    "options": "Qty\nPercentage",
                    "insert_after": "free_qty",
                    "default": "Qty",
                },
                {
                    "fieldname": "rate_based_on",
                    "label": "Rate Based On",
                    "fieldtype": "Select",
                    "options": "Qty\nWeight",
                    "insert_after": "rate",
                    "default": "Weight",
                },
                {
                    "fieldname": "has_item_wise_rates",
                    "label": "Has Item wise Rates",
                    "fieldtype": "Check",
                    "insert_after": "rate_based_on",
                    "depends_on": "eval:doc.rate_or_discount == 'Rate'",
                },
                {
                    "fieldname": "item_wise_rates",
                    "label": "Item wise Rates",
                    "fieldtype": "Table",
                    "options": "Pricing Rule Rate",
                    "insert_after": "has_item_wise_rates",
                    "depends_on": "eval:doc.has_item_wise_rates",
                },
                {
                    "fieldname": "has_item_group_wise_discounts",
                    "label": "Has Item Group wise Discounts",
                    "fieldtype": "Check",
                    "insert_after": "item_wise_rates",
                    "depends_on": "eval:doc.rate_or_discount != 'Rate'",
                },
                {
                    "fieldname": "item_group_wise_discounts",
                    "label": "Item Group wise Discounts",
                    "fieldtype": "Table",
                    "options": "Pricing Rule Discount",
                    "insert_after": "has_item_group_wise_discounts",
                    "depends_on": "eval:doc.has_item_group_wise_discounts",
                },
                {
                    "fieldname": "has_item_wise_discounts",
                    "label": "Has Item wise Discounts",
                    "fieldtype": "Check",
                    "insert_after": "item_group_wise_discounts",
                    "depends_on": "eval:doc.rate_or_discount != 'Rate'",
                },
                {
                    "fieldname": "item_wise_discounts",
                    "label": "Item wise Discounts",
                    "fieldtype": "Table",
                    "options": "Pricing Rule Item Discount",
                    "insert_after": "has_item_wise_discounts",
                    "depends_on": "eval:doc.has_item_wise_discounts",
                },
            ],
            "Sales Order Item": [
                {
                    "fieldname": "pricing_scheme",
                    "label": "Pricing Scheme",
                    "fieldtype": "Link",
                    "options": "Pricing Rule",
                    "insert_after": "pricing_rules",
                    "read_only": 1,
                },
                {
                    "fieldname": "skip_auto_apply_scheme",
                    "label": "Skip Primary Scheme",
                    "fieldtype": "Check",
                    "insert_after": "pricing_scheme",
                    "read_only": 1,
                },
            ],
            "Sales Invoice Item": [
                {
                    "fieldname": "pricing_scheme",
                    "label": "Pricing Scheme",
                    "fieldtype": "Link",
                    "options": "Pricing Rule",
                    "insert_after": "pricing_rules",
                    "read_only": 1,
                },
            ],
            "Sales Invoice": [
                {
                    "fieldname": "pricing_scheme",
                    "label": "Pricing Scheme",
                    "fieldtype": "Link",
                    "options": "Pricing Rule",
                    "insert_after": "apply_discount_on",
                    "read_only": 1,
                },
            ],
            "Sales Order": [
                {
                    "fieldname": "pricing_scheme",
                    "label": "Pricing Scheme",
                    "fieldtype": "Link",
                    "options": "Pricing Rule",
                    "insert_after": "apply_discount_on",
                    "read_only": 1,
                },
            ],
        }
    )

    for field in ["territory", "customer_group"]:
        make_property_setter(
            {
                "doctype": "Pricing Rule",
                "fieldname": field,
                "property": "depends_on",
                "value": "",
            },
            validate_fields_for_doctype=False,
            is_system_generated=True,
        )
