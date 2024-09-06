// Copyright(c) 2024, Wahni IT Solutions Pvt.Ltd.and contributors
// For license information, please see license.txt

frappe.provide("pricing_scheme");

const isObjectEmpty = (objectName) => {
    return (
        objectName &&
        Object.keys(objectName).length === 0 &&
        objectName.constructor === Object
    );
};

// eslint-disable-next-line
pricing_scheme.isObjectEmpty = isObjectEmpty;

// eslint-disable-next-line
pricing_scheme.PricingScheme = class PricingScheme {
    constructor(frm) {
        this.frm = frm;
        this.schemes = {};
        this.applied_schemes = {};
        this.ignore_rule_fetch = false;
        this.rejection_callback = null;
        this.form_requires_save = false;
    }

    init() {
        if (this.frm.doc.docstatus != 0) {
            frappe.throw(__("Scheme can only be applied on draft documents."));
        }

        frappe.run_serially([
            () => this.get_pricing_scheme(),
            () => this.setup_dialog(),
        ]);
    }

    get_applied_rules() {
        let me = this;
        this.applied_schemes = {};
        me.frm.doc.items.forEach((item) => {
            if (item.pricing_scheme) {
                this.applied_schemes[item.pricing_scheme] =
                    this.applied_schemes[item.pricing_scheme] || [];
                this.applied_schemes[item.pricing_scheme].push(item.name);
            }
        });
    }

    setup_dialog() {
        let me = this;

        if (isObjectEmpty(me.schemes.rules) && isObjectEmpty(me.applied_schemes))
            return;

        let d = new frappe.ui.Dialog({
            title: __("Pricing Schemes"),
            size: "large",
            onhide: () => {
                this.rejection_callback && this.rejection_callback();
            },
            fields: [
                {
                    fieldtype: "Section Break",
                    label: "Applied Schemes",
                    hidden: isObjectEmpty(me.applied_schemes),
                    collapsible: isObjectEmpty(me.schemes.rules) ? 0 : 1,
                },
                { fieldtype: "HTML", fieldname: "applied_schemes" },
                {
                    fieldtype: "Section Break",
                    label: "Available Schemes",
                    hidden: isObjectEmpty(me.schemes.rules),
                },
                { fieldtype: "HTML", fieldname: "available_schemes" },
                {
                    fieldtype: "Section Break",
                    label: "Scheme Details",
                    hidden: isObjectEmpty(me.schemes.rules),
                },
                {
                    fieldtype: "Data",
                    fieldname: "selected_scheme",
                    label: "Scheme",
                    read_only: 1,
                },
                {
                    fieldtype: "Link",
                    fieldname: "pricing_rule",
                    options: "Pricing Rule",
                    read_only: 1,
                    hidden: 1,
                },
                {
                    fieldtype: "Data",
                    fieldname: "free_based_on",
                    label: "Free Based On",
                    read_only: 1,
                },
                { fieldtype: "Column Break" },
                {
                    fieldtype: "Float",
                    fieldname: "free_qty",
                    label: "Applicable Free Qty",
                    read_only: 1,
                },
                {
                    fieldtype: "Float",
                    fieldname: "remaining_qty",
                    label: "Remaining Free Qty",
                    read_only: 1,
                },
                {
                    fieldtype: "Section Break",
                    fieldname: "scheme_items_section",
                    hidden: isObjectEmpty(me.schemes.rules),
                },
                {
                    label: "Free Items",
                    fieldname: "free_items",
                    fieldtype: "Table",
                    cannot_add_rows: true,
                    cannot_delete_rows: true,
                    fields: [
                        {
                            label: "Item",
                            fieldname: "item_code",
                            fieldtype: "Link",
                            options: "Item",
                            in_list_view: 1,
                            read_only: 1,
                        },
                        {
                            label: "Qty",
                            fieldname: "qty",
                            fieldtype: "Float",
                            in_list_view: 1,
                            onchange: function () {
                                me.update_remaining_qty(d);
                            },
                        },
                        {
                            label: "Unit Weight",
                            fieldname: "unit_weight",
                            fieldtype: "Float",
                            read_only: 1,
                            in_list_view: 1,
                        },
                    ],
                    data: [],
                },
                {
                    label: "Scheme Items",
                    fieldtype: "Table",
                    fieldname: "scheme_items",
                    cannot_add_rows: true,
                    in_place_edit: false,
                    fields: [
                        {
                            label: "Item",
                            fieldname: "item_code",
                            fieldtype: "Link",
                            options: "Item",
                            in_list_view: 1,
                            read_only: 1,
                        },
                        {
                            label: "Qty",
                            fieldname: "qty",
                            fieldtype: "Float",
                            in_list_view: 1,
                            read_only: 1,
                        },
                        {
                            label: "Stock Qty",
                            fieldname: "stock_qty",
                            fieldtype: "Float",
                            read_only: 1,
                        },
                        {
                            label: "Weight",
                            fieldname: "weight",
                            fieldtype: "Float",
                            read_only: 1,
                            in_list_view: 1,
                        },
                        {
                            label: "Amount",
                            fieldname: "amount",
                            fieldtype: "Currency",
                            read_only: 1,
                            in_list_view: 1,
                        },
                        {
                            label: "Row Name",
                            fieldname: "row_name",
                            fieldtype: "Data",
                            hidden: 1,
                        },
                    ],
                    data: [],
                    get_data: () => {
                        d.set_value(
                            "free_qty",
                            me.calculate_free_item_qty(
                                d,
                                me.schemes.rules[d.get_value("pricing_rule")]
                            )
                        ).then(() => me.update_remaining_qty(d));
                        return d.fields_dict.scheme_items.grid.df.data;
                    },
                },
            ],
        });

        me.setup_dialog_primary_action(d);
        me.setup_applied_rules(d);
        me.setup_pricing_rule_selector(d);
        d.show();
    }

    update_remaining_qty(dialog) {
        let me = this;
        let rule = me.schemes.rules[dialog.get_value("pricing_rule")];
        let free_item_qty = dialog.get_value("free_qty");
        let actual_free_qty = me.calculate_selected_free_items(dialog, rule);
        dialog.set_value("remaining_qty", free_item_qty - actual_free_qty);
    }

    validate_rule_applicable(qty, amt, rule) {
        if (rule.min_qty && rule.min_qty > qty) return 0;
        if (rule.max_qty && rule.max_qty < qty) return 0;
        if (rule.min_amt && rule.min_amt > amt) return 0;
        if (rule.max_amt && rule.max_amt < amt) return 0;
        return true;
    }

    calculate_free_item_qty(dialog, rule) {
        let me = this;
        if (rule.price_or_product_discount != "Product") return 0;
        let selected_details = me.calculate_selected_items(dialog, rule);
        if (
            !me.validate_rule_applicable(
                selected_details[0],
                selected_details[1],
                rule
            )
        )
            return 0;

        if (rule.free_qty_type == "Percentage") {
            return Math.floor((selected_details[0] * rule.free_qty) / 10) / 10;
        }
        if (rule.is_recursive) {
            return (
                rule.free_qty *
                (Math.floor((10 * selected_details[0]) / rule.recurse_for) / 10)
            );
        }
        return rule.free_qty;
    }

    calculate_selected_items(dialog, rule) {
        let qty_field;
        if (rule.apply_on == "Transaction") {
            qty_field =
                rule.qty_based_on == "Stock" ? "total_qty" : "total_net_weight";
            return [this.frm.doc[qty_field], this.frm.doc.net_total];
        }
        qty_field = rule.qty_based_on == "Stock" ? "stock_qty" : "weight";
        return [
            dialog
                .get_value("scheme_items")
                .reduce((acc, item) => acc + item[qty_field], 0),
            dialog
                .get_value("scheme_items")
                .reduce((acc, item) => acc + item["amount"], 0),
        ];
    }

    calculate_selected_free_items(dialog, rule) {
        if (rule.qty_based_on == "Stock") {
            return dialog
                .get_value("free_items")
                .reduce((acc, item) => acc + item.qty, 0);
        }
        return dialog
            .get_value("free_items")
            .reduce((acc, item) => acc + item.unit_weight * item.qty, 0);
    }

    setup_dialog_primary_action(dialog) {
        let d = dialog;
        let me = this;

        d.set_secondary_action_label("Submit");
        d.set_secondary_action(() => {
            me.frm.doc.__pricing_scheme_set = true;
            me.frm.savesubmit();
            d.hide();
        });

        if (isObjectEmpty(me.schemes.rules)) return;
        d.set_primary_action("Apply", function () {
            if (me.frm.doc.__in_scheme_apply) {
                frappe.utils.play_sound("error");
                frappe.show_alert(
                    {
                        message: __(
                            "Please wait while the previous scheme is being applied."
                        ),
                        indicator: "orange",
                    },
                    5
                );
                return;
            }
            me.frm.doc.__in_scheme_apply = true;
            let rule = me.schemes.rules[d.get_value("pricing_rule")];
            let selected_details = me.calculate_selected_items(d, rule);
            if (
                !me.validate_rule_applicable(
                    selected_details[0],
                    selected_details[1],
                    rule
                )
            ) {
                frappe.utils.play_sound("error");
                frappe.show_alert(
                    {
                        message: __(
                            "The selected rule is no longer applicable due to criteria not being met."
                        ),
                        indicator: "red",
                    },
                    5
                );
                return;
            }
            me.form_requires_save = false;
            if (rule.apply_on != "Transaction") {
                if (rule.price_or_product_discount == "Product") {
                    me.add_free_items(d, rule).then(() => {
                        me.update_form(d);
                    });
                } else {
                    me.apply_item_discount(d, rule).then(() => {
                        me.update_form(d);
                    });
                }
            } else {
                me.apply_transaction_discount(rule).then(() => {
                    me.update_form(d);
                });
            }
        });
    }

    async update_form(dialog) {
        let me = this;
        me.frm.doc.__in_scheme_apply = false;
        if (!me.form_requires_save) return;
        await me.frm.save();
        me.form_requires_save = false;
        dialog.hide();
        me.init();
    }

    async apply_transaction_discount(rule) {
        let me = this;
        if (rule.rate_or_discount == "Rate") return;
        let disc_field = frappe.scrub(rule.rate_or_discount).replaceAll("-", "_");
        await me.frm.set_value("pricing_scheme", rule.pricing_rule);
        await me.frm.set_value("apply_discount_on", rule.apply_discount_on);
        await me.frm.set_value(
            disc_field == "discount_percentage"
                ? "additional_discount_percentage"
                : disc_field,
            rule[disc_field]
        );
        me.form_requires_save = true;
    }

    async apply_item_discount(dialog, rule) {
        let me = this;
        let d = dialog;

        let scheme_rows = d.get_value("scheme_items").map((item) => item.row_name);

        let disc_field = frappe.scrub(rule.rate_or_discount).replaceAll("-", "_");
        let weight_based_rule =
            rule.rate_or_discount == "Rate" && rule.rate_based_on == "Weight";

        for (const item of me.frm.doc.items) {
            if (scheme_rows.includes(item.name)) {
                item.pricing_scheme = d.get_value("pricing_rule");
                if (weight_based_rule) {
                    let rate = rule.item_wise_rates?.[item.item_code] || rule.rate;
                    await frappe.model.set_value(
                        item.doctype,
                        item.name,
                        "rate",
                        rate * item.weight_per_unit
                    );
                } else {
                    let value = rule[disc_field];
                    if (disc_field == "rate") {
                        value = rule.item_wise_rates?.[item.item_code] || rule.rate;
                    } else if (disc_field == "discount_percentage") {
                        value =
                            rule.item_wise_discounts?.[item.item_code] ||
                            rule.item_group_wise_discounts?.[item.item_group] ||
                            rule.discount_percentage;
                    }
                    await frappe.model.set_value(
                        item.doctype,
                        item.name,
                        disc_field,
                        value
                    );
                    item[disc_field] = value;
                }
            }
        }

        me.form_requires_save = true;
    }

    async add_free_items(dialog, rule) {
        let me = this;
        let d = dialog;
        let free_item_qty = me.calculate_selected_free_items(d, rule);
        let actual_free_qty = me.calculate_free_item_qty(d, rule);

        if (Math.abs(free_item_qty - actual_free_qty) >= 0.1) {
            frappe.msgprint(
                __("Please select exactly {0} free items, you have selected {1}.", [
                    actual_free_qty.toFixed(2),
                    free_item_qty.toFixed(2),
                ])
            );
            return;
        }

        let scheme_rows = d.get_value("scheme_items").map((item) => item.row_name);

        me.frm.doc.items.forEach((item) => {
            if (scheme_rows.includes(item.name)) {
                item.pricing_scheme = d.get_value("pricing_rule");
            }
        });

        for (const item of d.get_value("free_items")) {
            if (item.qty > 0) {
                let row = me.frm.add_child("items");
                row.item_code = item.item_code;
                await me.frm.script_manager.trigger("item_code", row.doctype, row.name);
                row.qty = item.qty;
                row.discount_percentage = 100;
                row.rate = 0;
                row.amount = 0;
                row.is_free_item = 1;
                row.pricing_scheme = d.get_value("pricing_rule");
                if (rule.free_item_uom) {
                    row.uom = rule.free_item_uom;
                    await me.frm.script_manager.trigger("uom", row.doctype, row.name);
                }
            }
        }

        me.form_requires_save = true;
    }

    setup_applied_rules(dialog) {
        let me = this;
        let d = dialog;

        let $wrapper = d.fields_dict.applied_schemes.$wrapper;
        let rule_html = `<div class="d-flex flex-row flex-wrap slot-info">`;
        Object.keys(me.applied_schemes).forEach((rule) => {
            rule_html += `
                <button class="btn btn-secondary"
                    data-name=${rule}
                    data-title="${me.applied_schemes[rule].title}"
                    style="margin: 0 10px 10px 0; width: auto; flex-grow: 1; flex-basis: 30%;"
                >
                    ${me.applied_schemes[rule].title || ""}<br>
                    (${rule})<br>
                </button>
            `;
        });
        rule_html += "</div><br>";

        $wrapper.css("margin-bottom", 0).addClass("text-center").html(rule_html);

        $wrapper.on("click", "button", function () {
            let $btn = $(this);
            frappe.confirm(
                `Are you sure want to remove the rule: ${$btn.data("title")}?`,
                () => me.remove_selected_rule(d, $btn.data("name")),
                () => { }
            );
        });
    }

    remove_selected_rule(dialog, rule) {
        let me = this;
        frappe.call({
            method: "pricing_scheme.utils.pricing_scheme.remove_selected_rule",
            args: {
                order: me.frm.doc.name,
                rule: rule,
            },
            callback: function (r) {
                if (!r.exc) {
                    frappe.run_serially([
                        () => me.frm.reload_doc(),
                        () => dialog.hide(),
                        () =>
                            frappe.show_alert(
                                {
                                    message: __("Rule removed successfully"),
                                    indicator: "green",
                                },
                                5
                            ),
                        () => me.init(),
                    ]);
                }
            },
        });
    }

    setup_pricing_rule_selector(dialog) {
        let me = this;
        let d = dialog;
        d.fields_dict.scheme_items.df.data = [];
        d.fields_dict.free_items.df.data = [];

        let $wrapper = d.fields_dict.available_schemes.$wrapper;
        let rule_html = `<div class="d-flex flex-row flex-wrap slot-info">`;
        Object.keys(me.schemes.rules).forEach((rule) => {
            rule_html += `
                <button class="btn btn-secondary"
                    data-name=${rule}
                    style="margin: 0 10px 10px 0; width: auto; flex-grow: 1; flex-basis: 30%;"
                >
                    ${me.schemes.rules[rule].title}<br>
                    (${rule})<br>
                </button>
            `;
        });
        rule_html += "</div><br>";

        $wrapper.css("margin-bottom", 0).addClass("text-center").html(rule_html);

        $wrapper.on("click", "button", function () {
            let $btn = $(this);
            d.set_value("pricing_rule", $btn.data("name"));
            d.set_value("selected_scheme", me.schemes.rules[$btn.data("name")].title);
            if (me.schemes.rules[$btn.data("name")].apply_on != "Transaction") {
                d.set_value(
                    "free_based_on",
                    me.schemes.rules[$btn.data("name")].qty_based_on
                );
                d.fields_dict.scheme_items.df.data = [];
                d.fields_dict.scheme_items.grid.refresh();
                me.schemes.rules[$btn.data("name")].applicable_items.forEach((item) => {
                    let item_details = me.schemes.items[item];
                    d.fields_dict.scheme_items.df.data.push({
                        item_code: item_details.item_code,
                        qty: item_details.qty,
                        stock_qty: item_details.stock_qty,
                        amount: item_details.amount,
                        weight: item_details.weight,
                        row_name: item,
                    });
                });
                d.fields_dict.scheme_items.grid.refresh();

                d.fields_dict.free_items.df.data = [];
                d.fields_dict.free_items.grid.refresh();
                me.schemes.rules[$btn.data("name")].free_items.forEach((item) => {
                    d.fields_dict.free_items.df.data.push({
                        item_code: item.item_code,
                        qty: 0,
                        unit_weight: item.unit_weight,
                    });
                });
                d.fields_dict.free_items.grid.refresh();
                let _qty = me.calculate_free_item_qty(
                    d,
                    me.schemes.rules[$btn.data("name")]
                );
                d.set_value("free_qty", _qty);
                d.set_value("remaining_qty", _qty);
                d.set_df_property("scheme_items_section", "hidden", 0);
            } else {
                d.set_df_property("scheme_items_section", "hidden", 1);
            }
        });
    }

    async get_pricing_scheme() {
        let me = this;
        if (me.ignore_rule_fetch) {
            me.ignore_rule_fetch = false;
            if (!isObjectEmpty(me.schemes)) return;
        }
        me.schemes = {};
        me.applied_schemes = {};
        await frappe.call({
            method: "pricing_scheme.utils.pricing_scheme.get_pricing_rules",
            args: {
                doc: me.frm.doc,
            },
            callback: function (r) {
                if (!r.exc && r.message) {
                    me.schemes = r.message;
                    me.applied_schemes = r.message.applied_schemes;
                }
            },
        });
    }
};
