// Copyright (c) 2022, Wahni Green Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Sales Order', {
    refresh: function (frm) {
        let args = {}
        const std_fields = ['qty', 'model', 'top_width', 'bottom_width', 'height', 'hinge', "door_only", 'frame', 'remarks']
        if (frm.doc.docstatus === 0) {
            frm.fields_dict.items.grid.add_custom_button(__('Add Door'), function () {
                let d = new frappe.ui.Dialog({
                    title: 'Item Details',
                    fields: [
                        {
                            label: 'Model',
                            fieldname: 'model',
                            fieldtype: 'Link',
                            options: 'Item',
                            reqd: 1,
                            get_query: function () {
                                return {
                                    filters: {
                                        is_frame: 0,
                                        has_variants: 1,
                                        disabled: 0
                                    }
                                }
                            },
                            onchange: function () {
                                args = {}
                                let all_fields = Object.keys(d.fields_dict);
                                for (let x in all_fields) {
                                    if (
                                        !(std_fields.includes(all_fields[x]))
                                        && d.fields_dict[all_fields[x]].df.fieldtype != "Section Break"
                                    ) {
                                        d.fields_dict[all_fields[x]].df.hidden = 1;
                                        d.fields_dict[all_fields[x]].df.reqd = 0;
                                    }
                                }
                                frappe.call({
                                    method: "pricing_scheme.utils.variant.get_model_attributes",
                                    args: {
                                        model: d.get_value("model"),
                                    },
                                    callback: function (r) {
                                        for (const [key, value] of Object.entries(r.message)) {
                                            d.fields_dict[key].df.hidden = 0;
                                            d.fields_dict[key].df.reqd = 1;
                                            args[value] = key;
                                        }
                                        d.fields_dict['frame'].df.hidden = 0
                                        d.refresh();
                                    }
                                });
                            }
                        },
                        {
                            fieldname: 'col_break1',
                            fieldtype: 'Column Break'
                        },
                        {
                            label: 'Quantity',
                            fieldname: 'qty',
                            fieldtype: 'Int',
                            default: 1,
                            read_only: 1
                        },
                        {
                            label: 'Door Only',
                            fieldname: 'door_only',
                            fieldtype: 'Check',
                            default: 0,
                            onchange: function () {
                                d.set_value('frame', '');
                                if (d.get_value('door_only')) {
                                    d.fields_dict['frame'].df.hidden = 1
                                    d.fields_dict['frame'].df.reqd = 0
                                }
                                else {
                                    d.fields_dict['frame'].df.hidden = 0
                                    d.fields_dict['frame'].df.reqd = 1
                                }
                            }
                        },
                    ],
                    primary_action_label: __('Add Item'),
                    primary_action: function () {
                        let new_args = {};
                        for (const [key, value] of Object.entries(args)) {
                            new_args[key] = d.get_value(value);
                        }
                        frappe.call({
                            method: "pricing_scheme.utils.variant.get_door_variant",
                            args: {
                                model: d.get_value("model"),
                                attributes: new_args,
                            },
                            freeze: true,
                            callback: function (r) {
                                let remarks = d.get_value('remarks');
                                if (d.get_value('frame') == "10cm") { remarks.concat(' as 32 mm door shutter') }
                                let row = frm.add_child('items', {
                                    'variant': d.get_value('model'),
                                    'item_code': r.message,
                                    'qty': d.get_value('qty'),
                                    'top_width': d.get_value('top_width'),
                                    'bottom_width': d.get_value('bottom_width'),
                                    'height': d.get_value('height'),
                                    'hinge': d.get_value('hinge'),
                                    'door_only': d.get_value('door_only'),
                                    'frame': d.get_value('frame'),
                                    'remarks': d.get_value('remarks')
                                });
                                frm.script_manager.trigger("item_code", row.doctype, row.name);
                                frm.script_manager.trigger("door_only", row.doctype, row.name);
                                frappe.show_alert({
                                    message: __('Item added successfully.'),
                                    indicator: 'green'
                                }, 3);
                            }
                        });
                    },
                });
                frappe.call({
                    method: "pricing_scheme.utils.variant.get_door_attributes",
                    callback: function (r) {
                        d.add_fields(r.message)
                        d.add_fields([
                            {
                                label: 'Top Width',
                                fieldname: 'top_width',
                                fieldtype: 'Float',
                                reqd: 1
                            },
                            {
                                label: 'Bottom Width',
                                fieldname: 'bottom_width',
                                fieldtype: 'Float',
                                reqd: 1
                            },
                            {
                                label: 'Height',
                                fieldname: 'height',
                                fieldtype: 'Float',
                                reqd: 1
                            },
                            {
                                label: 'Hinge',
                                fieldname: 'hinge',
                                fieldtype: 'Select',
                                options: ['Left', 'Right'],
                                reqd: 1
                            },
                            {
                                fieldname: 'col_break3',
                                fieldtype: 'Column Break'
                            },
                            {
                                label: 'Frame',
                                fieldname: 'frame',
                                fieldtype: 'Link',
                                options: "Item",
                                read_only_depends_on: 'door_only',
                                get_query: function () {
                                    return {
                                        filters: {
                                            is_frame: 1,
                                            disabled: 0
                                        }
                                    }
                                },
                                reqd: 1
                            },
                            {
                                label: 'Remarks',
                                fieldname: 'remarks',
                                fieldtype: 'Small Text',
                                reqd: 0
                            }
                        ]);
                        erpnext.utils.remove_empty_first_row(frm, "items");
                        d.show();
                    }
                });
            });
            frm.fields_dict.items.grid.grid_buttons.find('.btn-custom').removeClass('btn-default').addClass('btn-info').addClass('mr-1');
        }

        if (frm.doc.docstatus == 1 && frm.doc.in_production == "No") {
            frm.remove_custom_button(__('Work Order'), __('Create'));
            frm.add_custom_button(__("Production Order"), function () {
                frappe.model.open_mapped_doc({
                    method: "pricing_scheme.utils.variant.create_production_order",
                    frm: frm
                });
            }, __("Create"));
        }
    },
});
