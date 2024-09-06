# Copyright (c) 2023, Wahni IT Solutions Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
import json
import copy
from frappe.utils import cint, floor, flt
from erpnext.accounts.doctype.pricing_rule.pricing_rule import (
    set_transaction_type,
    update_args_for_pricing_rule,
)
from erpnext.setup.doctype.item_group.item_group import get_child_item_groups
from erpnext.accounts.doctype.pricing_rule.utils import (
    get_pricing_rule_items,
    _get_pricing_rules,
    get_other_conditions,
)

apply_on_table = {"Item Code": "items", "Item Group": "item_groups", "Brand": "brands"}


def apply_pricing_rule(args, doc=None):
    if isinstance(args, str):
        args = json.loads(args)

    args = frappe._dict(args)

    if not args.transaction_type:
        set_transaction_type(args)

    out = {
        "rules": {},
        "items": {},
        "applied_schemes": {},
    }

    if args.get("doctype") == "Material Request":
        return out

    item_list = args.pop("items", [])

    item_code_list = tuple(item.get("item_code") for item in item_list)
    query_items = frappe.get_all(
        "Item",
        fields=["item_code", "has_serial_no"],
        filters=[["item_code", "in", item_code_list]],
        as_list=1,
    )
    serialized_items = dict()
    for item_code, val in query_items:
        serialized_items.setdefault(item_code, val)

    _stock_qty = 0
    for item in item_list:
        _stock_qty += item.get("stock_qty", 0)
        args_copy = copy.deepcopy(args)
        args_copy.update(item)
        data, _rules = get_pricing_rule_for_item(args_copy, doc=doc)
        for rule in _rules.keys():
            if out["rules"].get(rule):
                out["rules"][rule]["applicable_items"].append(item.get("name"))
            else:
                out["rules"].update({rule: _rules[rule]})
                out["rules"][rule]["applicable_items"] = [item.get("name")]
        if data:
            out["items"].update(
                {
                    item.get("name"): {
                        **data,
                        "item_code": item.get("item_code"),
                        "item_name": item.get("item_name"),
                        "qty": item.get("qty", 0),
                        "weight": item.get("total_weight", 0),
                        "stock_qty": item.get("stock_qty", 0),
                        "amount": item.get("net_amount", 0),
                    }
                }
            )
        if scheme := item.get("pricing_scheme"):
            out["applied_schemes"].setdefault(
                scheme,
                {
                    "title": frappe.db.get_value("Pricing Rule", scheme, "title"),
                    "items": [],
                },
            )
            out["applied_schemes"][scheme]["items"].append(item.get("name"))

    for tr_rule in filter_pricing_rule_based_on_condition(
        get_transaction_based_rules(doc), doc
    ):
        if doc.get("pricing_scheme") == tr_rule.name:
            continue

        if tr_rule.qty_based_on != "Stock":
            _stock_qty = doc.total_net_weight
        amount = doc.net_total
        if filter_pricing_rules_for_qty_amount(_stock_qty, amount, tr_rule, args):
            out["rules"].update({tr_rule.name: get_pricing_rule_details(args, tr_rule)})

    if scheme := doc.get("pricing_scheme"):
        out["applied_schemes"].setdefault(
            scheme,
            {
                "title": frappe.db.get_value("Pricing Rule", scheme, "title"),
                "items": [],
            },
        )

    return out


def get_pricing_rule_for_item(args, doc=None, for_validate=False):
    if isinstance(doc, str):
        doc = json.loads(doc)

    if doc:
        doc = frappe.get_doc(doc)

    if args.get("pricing_scheme"):
        return {}, {}

    if args.get("is_free_item"):
        return {}, {}

    item_details = frappe._dict(
        {
            "doctype": args.doctype,
            "has_margin": False,
            "name": args.name,
            "free_item_data": [],
            "parent": args.parent,
            "parenttype": args.parenttype,
            "child_docname": args.get("child_docname"),
        }
    )

    if not args.item_code:
        return item_details, {}

    update_args_for_pricing_rule(args)

    pricing_rules = get_pricing_rules(args, doc)
    rules = {}

    if pricing_rules:
        for pricing_rule in pricing_rules:
            if not pricing_rule:
                continue

            if isinstance(pricing_rule, str):
                pricing_rule = frappe.get_cached_doc("Pricing Rule", pricing_rule)

            if pricing_rule.get("suggestion"):
                continue

            rules.update(
                {pricing_rule.name: get_pricing_rule_details(args, pricing_rule)}
            )

        item_details.has_pricing_rule = 1
        item_details.pricing_rules = [d for d in rules.keys()]

    return item_details, rules


def get_pricing_rule_details(args, pricing_rule):
    free_items = []
    if pricing_rule.get("has_multiple_free_items"):
        free_items = frappe.get_all(
            "Pricing Rule Free Item",
            filters={"parent": pricing_rule.name, "parenttype": "Pricing Rule"},
            fields=["item_code", "uom", "description", "item_name", "unit_weight"],
        )

    item_wise_rates = {}
    if pricing_rule.get("has_item_wise_rates"):
        item_wise_rates = dict(
            frappe.get_all(
                "Pricing Rule Rate",
                filters={"parent": pricing_rule.name, "parenttype": "Pricing Rule"},
                fields=["item_code", "rate"],
                as_list=1,
            )
        )

    item_group_wise_discounts = {}
    if pricing_rule.get("has_item_group_wise_discounts"):
        item_group_wise_discounts = dict(
            frappe.get_all(
                "Pricing Rule Discount",
                filters={"parent": pricing_rule.name, "parenttype": "Pricing Rule"},
                fields=["item_group", "discount_percentage"],
                as_list=1,
            )
        )
        item_sub_groups = {}
        for item_group in item_group_wise_discounts.keys():
            item_sub_groups[item_group] = get_child_item_groups(item_group)

        for grp, children in item_sub_groups.items():
            for child in children:
                item_group_wise_discounts[child] = item_group_wise_discounts[grp]

    item_wise_discounts = {}
    if pricing_rule.get("has_item_wise_discounts"):
        item_wise_discounts = dict(
            frappe.get_all(
                "Pricing Rule Item Discount",
                filters={"parent": pricing_rule.name, "parenttype": "Pricing Rule"},
                fields=["item_code", "discount_percentage"],
                as_list=1,
            )
        )

    return frappe._dict(
        {
            "pricing_rule": pricing_rule.name,
            "rate_or_discount": pricing_rule.rate_or_discount,
            "margin_type": pricing_rule.margin_type,
            "item_code": args.get("item_code"),
            "child_docname": args.get("child_docname"),
            "free_items": free_items,
            "item_wise_rates": item_wise_rates,
            "title": pricing_rule.title,
            "recurse_for": pricing_rule.recurse_for,
            "free_qty": pricing_rule.free_qty,
            "free_qty_type": pricing_rule.free_qty_type,
            "qty_based_on": pricing_rule.qty_based_on,
            "is_recursive": pricing_rule.is_recursive,
            "price_or_product_discount": pricing_rule.price_or_product_discount,
            "min_amt": pricing_rule.min_amt,
            "max_amt": pricing_rule.max_amt,
            "min_qty": pricing_rule.min_qty,
            "max_qty": pricing_rule.max_qty,
            "apply_on": pricing_rule.apply_on,
            "rate": pricing_rule.rate,
            "discount_percentage": pricing_rule.discount_percentage,
            "discount_amount": pricing_rule.discount_amount,
            "apply_discount_on": pricing_rule.apply_discount_on,
            "rate_based_on": pricing_rule.rate_based_on,
            "free_item_uom": pricing_rule.free_item_uom,
            "auto_apply_scheme": pricing_rule.auto_apply_scheme,
            "allow_skipping": pricing_rule.allow_skipping,
            "item_group_wise_discounts": item_group_wise_discounts,
            "item_wise_discounts": item_wise_discounts,
        }
    )


def get_pricing_rules(args, doc=None):
    pricing_rules = []
    values = {}

    if not frappe.db.exists("Pricing Rule", {"disable": 0, args.transaction_type: 1}):
        return

    for apply_on in ["Item Code", "Item Group", "Brand"]:
        pricing_rules.extend(_get_pricing_rules(apply_on, args, values))

    rules = []

    pricing_rules = filter_pricing_rule_based_on_condition(pricing_rules, doc)

    if not pricing_rules:
        return []

    pricing_rules = sorted_by_priority(pricing_rules, args, doc)
    for pricing_rule in pricing_rules:
        if isinstance(pricing_rule, list):
            rules.extend(pricing_rule)
        else:
            rules.append(pricing_rule)

    return rules


def get_transaction_based_rules(doc):
    conditions = "apply_on = 'Transaction'"

    values = {}
    conditions = get_other_conditions(conditions, values, doc)

    return frappe.db.sql(
        f""" Select `tabPricing Rule`.* from `tabPricing Rule`
		where  {conditions} and `tabPricing Rule`.disable = 0
	""",
        values,
        as_dict=1,
    )


def filter_pricing_rules_for_qty_amount(qty, rate, rule, args=None):
    status = False
    conversion_factor = 1

    if flt(qty) >= (flt(rule.min_qty) * conversion_factor) and (
        flt(qty) <= (rule.max_qty * conversion_factor) if rule.max_qty else True
    ):
        status = True

    if status and (
        flt(rate) >= (flt(rule.min_amt) * conversion_factor)
        and (flt(rate) <= (rule.max_amt * conversion_factor) if rule.max_amt else True)
    ):
        status = True
    else:
        status = False

    return status


def filter_pricing_rules(args, pricing_rules, doc=None):
    if not isinstance(pricing_rules, list):
        pricing_rules = [pricing_rules]

    original_pricing_rule = copy.copy(pricing_rules)
    # filter for qty
    pricing_rules = []
    for rule in original_pricing_rule:
        if rule.territory and not args.get("territory"):
            continue

        stock_qty = flt(args.get("stock_qty"))
        amount = flt(args.get("net_amount"))

        pr_doc = frappe.get_cached_doc("Pricing Rule", rule.name)
        if pr_doc.qty_based_on == "Weight":
            stock_qty = flt(args.get("total_weight"))

        if rule.mixed_conditions and doc:
            stock_qty, amount = get_qty_and_rate_for_mixed_conditions(doc, pr_doc, args)

        if filter_pricing_rules_for_qty_amount(stock_qty, amount, rule, args):
            pricing_rules.append(rule)

    if len(pricing_rules) > 1:
        filtered_rules = list(
            filter(lambda x: x.currency == args.get("currency"), pricing_rules)
        )
        if filtered_rules:
            pricing_rules = filtered_rules

    if pricing_rules and not isinstance(pricing_rules, list):
        pricing_rules = list(pricing_rules)

    return pricing_rules


def get_qty_and_rate_for_mixed_conditions(doc, pr_doc, args):
    sum_qty, sum_amt = [0, 0]
    items = get_pricing_rule_items(pr_doc) or []
    apply_on = frappe.scrub(pr_doc.get("apply_on"))

    if items and doc.get("items"):
        for row in doc.get("items"):
            if row.get("is_free_item"):
                continue

            if row.get("pricing_scheme"):
                if args.get("validate_for") != row.get("pricing_scheme"):
                    continue

            if (row.get(apply_on) or args.get(apply_on)) not in items:
                continue

            amt = flt(row.get("amount"))
            if row.get("price_list_rate"):
                amt = flt(row.get("price_list_rate") * row.get("qty"))

            sum_qty += (
                flt(row.get("stock_qty"))
                if pr_doc.qty_based_on == "Stock"
                else flt(row.get("total_weight"))
            )
            sum_amt += amt

    return sum_qty, sum_amt


def get_free_item_qty(rule, stock_qty):
    if not rule.is_recursive:
        return rule.free_qty

    transaction_qty = stock_qty - flt(rule.apply_recursion_over)
    if not transaction_qty:
        return 0

    qty = flt(transaction_qty) * (rule.free_qty or 1) / flt(rule.recurse_for)
    if rule.round_free_qty:
        return floor(qty)

    return qty


def sorted_by_priority(pricing_rules, args, doc=None):
    # If more than one pricing rules, then sort by priority
    pricing_rules_list = []
    pricing_rule_dict = {}

    for pricing_rule in pricing_rules:
        prules = filter_pricing_rules(args, pricing_rule, doc)
        for rule in prules:
            if not rule.get("priority"):
                rule["priority"] = 4
                if rule.get("customer"):
                    rule["priority"] = 1
                elif rule.get("customer_group"):
                    rule["priority"] = 2
                elif rule.get("territory"):
                    rule["priority"] = 3

            pricing_rule_dict.setdefault(cint(rule.get("priority")), []).append(rule)

    for key in sorted(pricing_rule_dict):
        pricing_rules_list.extend(pricing_rule_dict.get(key))

    return pricing_rules_list


def filter_pricing_rule_based_on_condition(pricing_rules, doc=None):
    filtered_pricing_rules = []
    if doc:
        for pricing_rule in pricing_rules:
            if pricing_rule.condition:
                try:
                    if frappe.safe_eval(pricing_rule.condition, None, doc.as_dict()):
                        filtered_pricing_rules.append(pricing_rule)
                except Exception:
                    pass
            else:
                filtered_pricing_rules.append(pricing_rule)
    else:
        filtered_pricing_rules = pricing_rules

    return filtered_pricing_rules
