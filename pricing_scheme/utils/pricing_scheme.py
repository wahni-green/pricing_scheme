# Copyright (c) 2023, Wahni IT Solutions Pvt. Ltd. and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from pricing_scheme.utils.pricing_rule import (
    apply_pricing_rule,
    filter_pricing_rule_based_on_condition,
    filter_pricing_rules_for_qty_amount,
    get_qty_and_rate_for_mixed_conditions,
)


@frappe.whitelist()
def get_pricing_rules(doc):
    items = []
    if isinstance(doc, str):
        doc = json.loads(doc)
        items = doc.get("items", [])
        doc = frappe.get_doc(doc)
    else:
        items = [d.as_dict() for d in doc.items]

    args = {
        "customer": doc.customer,
        "customer_group": doc.customer_group,
        "territory": doc.territory,
        "currency": doc.currency,
        "conversion_rate": doc.conversion_rate,
        "price_list": doc.selling_price_list,
        "price_list_currency": doc.price_list_currency,
        "plc_conversion_rate": doc.plc_conversion_rate,
        "company": doc.company,
        "transaction_date": doc.transaction_date,
        "ignore_pricing_rule": 0,
        "doctype": "Sales Order",
        "name": doc.name,
        "items": items,
    }

    return apply_pricing_rule(args=args, doc=doc)


def auto_apply_primary_scheme(doc, method=None):
    rules = get_pricing_rules(doc)["rules"]
    for scheme, rule in rules.items():
        if not rule.get("auto_apply_scheme"):
            continue
        if rule.price_or_product_discount != "Price":
            continue
        if not rule.get("applicable_items"):
            continue

        for row in doc.items:
            if row.skip_auto_apply_scheme and rule.allow_skipping:
                continue

            if row.pricing_scheme:
                continue

            if row.name not in rule.applicable_items:
                continue

            row.pricing_scheme = scheme
            if rule.rate_or_discount == "Rate":
                rate = rule.item_wise_rates.get(row.item_code) or rule.get("rate")
                if rule.rate_based_on == "Weight":
                    row.rate = rate * row.weight_per_unit
                else:
                    row.rate = rate
            else:
                field = frappe.scrub(rule.rate_or_discount)
                row.set(field, rule.get(field))
                if field == "discount_percentage":
                    row.discount_percentage = (
                        rule.item_wise_discounts.get(row.item_code)
                        or rule.item_group_wise_discounts.get(row.item_group)
                        or row.discount_percentage
                    )
                    row.discount_amount = (
                        row.price_list_rate * row.discount_percentage / 100
                    )
                row.rate = row.price_list_rate - row.discount_amount

            row.discount_amount = row.price_list_rate - row.rate
            row.discount_percentage = row.discount_amount * 100 / row.price_list_rate


@frappe.whitelist()
def remove_selected_rule(order, rule):
    doc = frappe.get_doc("Sales Order", order)
    pricing_rule = frappe.db.get_value("Pricing Rule", rule, ["apply_on"], as_dict=True)
    if pricing_rule.apply_on != "Transaction":
        _items = []
        idx = 0
        for row in doc.items:
            if row.pricing_scheme == rule:
                if row.is_free_item:
                    continue
                row.skip_auto_apply_scheme = 1
                row.pricing_scheme = None
                row.discount_percentage = 0
                row.discount_amount = 0
                row.margin_type = ""
                row.margin_rate_or_amount = 0
                row.rate = row.price_list_rate

            idx += 1
            row.idx = idx
            _items.append(row)
        doc.set("items", _items)
    else:
        doc.apply_discount_on = ""
        doc.discount_amount = 0
        doc.additional_discount_percentage = 0
        doc.pricing_scheme = None

    doc.save()


def is_scheme_applied(doc, method=None):
    if doc.get("pricing_scheme"):
        doc.set_onload("scheme_applied", 1)
        return

    for row in doc.items:
        if not row.get("pricing_scheme"):
            continue
        doc.set_onload("scheme_applied", 1)
        return


def validate_applied_scheme(doc, method=None):
    _stock_qty = 0
    for row in doc.items:
        _stock_qty += row.stock_qty
        if row.is_free_item:
            row.rate = 0
            row.discount_percentage = 100
            continue

        if not row.get("pricing_scheme"):
            continue

        old_row = row.get_doc_before_save()
        if old_row and old_row.get("pricing_scheme") == row.pricing_scheme:
            for field in [
                "qty",
                "rate",
                "discount_percentage",
                "discount_amount",
                "price_list_rate",
                "margin_rate_or_amount",
            ]:
                if row.has_value_changed(field):
                    frappe.throw(
                        _(
                            "Row #{0}: {1} cannot be edited as scheme is already applied."
                        ).format(row.idx, row.meta.get_label(field))
                    )

        prule = frappe.get_doc("Pricing Rule", row.pricing_scheme)
        territories = get_child("Territory", prule.territory)
        if prule.territory and doc.territory not in territories:
            frappe.throw(
                _("Row #{2}: Pricing Rule {0}({1}) is not applicable.").format(
                    prule.name, prule.title, row.idx
                )
            )

        customer_groups = get_child("Customer Group", prule.customer_group)
        if prule.customer_group and doc.customer_group not in customer_groups:
            frappe.throw(
                _("Row #{2}: Pricing Rule {0}({1}) is not applicable.").format(
                    prule.name, prule.title, row.idx
                )
            )

        if not filter_pricing_rule_based_on_condition([prule], doc):
            frappe.throw(
                _("Row #{2}: Pricing Rule {0}({1}) is not applicable.").format(
                    prule.name, prule.title, row.idx
                )
            )

        sqty = row.stock_qty
        if prule.qty_based_on != "Stock":
            sqty = row.total_weight

        amount = row.net_amount
        if prule.mixed_conditions:
            sqty, amount = get_qty_and_rate_for_mixed_conditions(
                doc, prule, {"validate_for": prule.name}
            )

        if not filter_pricing_rules_for_qty_amount(sqty, amount, prule):
            frappe.throw(
                _("Row #{2}: Pricing Rule {0}({1}) is not applicable.").format(
                    prule.name, prule.title, row.idx
                )
            )

    if doc.get("pricing_scheme"):
        prule = frappe.get_doc("Pricing Rule", doc.pricing_scheme)
        if not filter_pricing_rule_based_on_condition([prule], doc):
            frappe.throw(
                _(
                    "Pricing Rule {0}({1}) is not applicable for the transaction."
                ).format(prule.name, prule.title)
            )
        if prule.qty_based_on != "Stock":
            _stock_qty = doc.total_net_weight
        if not filter_pricing_rules_for_qty_amount(_stock_qty, doc.net_total, prule):
            frappe.throw(
                _(
                    "Pricing Rule {0}({1}) is not applicable for the transaction."
                ).format(prule.name, prule.title)
            )


def get_child(doctype, parent):
    p_d = frappe.db.get_list(
        doctype,
        filters={"name": parent},
        fields=["lft", "rgt"],
    )
    if not p_d:
        return []

    p_d = p_d[0]
    if p_d.rgt - p_d.lft <= 1:
        parent = [parent]
    else:
        parent = [parent] + frappe.get_list(
            doctype,
            {"lft": [">", p_d.lft], "rgt": ["<", p_d.rgt]},
            pluck="name",
        )

    return parent
