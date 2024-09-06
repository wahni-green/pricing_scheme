// Copyright (c) 2023, Wahni IT Solutions Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Sales Order", {
    before_submit: async (frm) => {
        if (frm.doc.__pricing_scheme_set) return;
        await new Promise((resolve) => {
            // eslint-disable-next-line
            let scheme_selector = new pricing_scheme.PricingScheme(frm);
            scheme_selector.get_pricing_scheme().then(() => {
                // eslint-disable-next-line
                if (pricing_scheme.isObjectEmpty(scheme_selector.schemes.rules)) {
                    resolve();
                } else {
                    scheme_selector.ignore_rule_fetch = true;
                    scheme_selector.init();
                    frappe.validated = false;
                    resolve();
                }
            });
        });
    },

    refresh(frm) {
        if (frm.doc.docstatus === 0) {
            if (!frm.doc.ignore_pricing_rule) {
                frm.doc.ignore_pricing_rule = 1;
            }
            frm.trigger("disable_scheme_form");
        }
    },

    onload: function (frm) {
        frm.trigger("disable_scheme_form");
    },

    disable_scheme_form: function (frm) {
        if (frm.doc.docstatus != 0) return;
        if (frm.doc.__onload && frm.doc.__onload.scheme_applied) {
            frm.dashboard.clear_headline();
            frm.dashboard.set_headline_alert(
                __("Be careful while editing the order as scheme as been applied.") +
                '<button class="btn btn-xs btn-primary pull-right" onclick="cur_frm.trigger(`init_scheme`)">' +
                __("View Scheme") +
                "</button>",
                "alert-warning"
            );
        }
    },

    init_scheme: function (frm) {
        // eslint-disable-next-line
        let scheme_selector = new pricing_scheme.PricingScheme(frm);
        scheme_selector.init();
    },
});
