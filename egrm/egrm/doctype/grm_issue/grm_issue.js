frappe.ui.form.on('GRM Issue', {
    refresh: function(frm) {
        // Add custom buttons based on state
        if (frm.doc.docstatus === 1) { // Submitted
            // Add resolution actions
            let statuses = frm.doc.__onload?.allowed_statuses || [];
            
            if (statuses.length > 0) {
                frm.add_custom_button(__('Change Status'), function() {
                    frappe.prompt([
                        {
                            fieldname: 'status',
                            label: __('New Status'),
                            fieldtype: 'Select',
                            options: statuses.join('\n'),
                            reqd: 1
                        },
                        {
                            fieldname: 'comment',
                            label: __('Comment'),
                            fieldtype: 'Small Text',
                            reqd: 1
                        }
                    ],
                    function(values) {
                        frappe.call({
                            method: 'egrm.server_scripts.issue_actions.change_status',
                            args: {
                                issue: frm.doc.name,
                                status: values.status,
                                comment: values.comment
                            },
                            callback: function(r) {
                                if (r.message) {
                                    frm.reload_doc();
                                    frappe.show_alert({
                                        message: __('Status updated successfully'),
                                        indicator: 'green'
                                    });
                                }
                            }
                        });
                    },
                    __('Change Issue Status'),
                    __('Update')
                    );
                }, __('Actions'));
            }
            
            // Add escalation button
            if (!frm.doc.escalate_flag) {
                frm.add_custom_button(__('Escalate Issue'), function() {
                    frappe.prompt([
                        {
                            fieldname: 'comment',
                            label: __('Escalation Reason'),
                            fieldtype: 'Small Text',
                            reqd: 1
                        },
                        {
                            fieldname: 'due_at',
                            label: __('Due Date'),
                            fieldtype: 'Datetime',
                            reqd: 1
                        }
                    ],
                    function(values) {
                        frappe.call({
                            method: 'egrm.server_scripts.issue_actions.escalate_issue',
                            args: {
                                issue: frm.doc.name,
                                reason: values.comment,
                                due_at: values.due_at
                            },
                            callback: function(r) {
                                if (r.message) {
                                    frm.reload_doc();
                                    frappe.show_alert({
                                        message: __('Issue escalated successfully'),
                                        indicator: 'green'
                                    });
                                }
                            }
                        });
                    },
                    __('Escalate Issue'),
                    __('Escalate')
                    );
                }, __('Actions'));
            }
            
            // Add reassign button
            frm.add_custom_button(__('Reassign Issue'), function() {
                frappe.prompt([
                    {
                        fieldname: 'assignee',
                        label: __('New Assignee'),
                        fieldtype: 'Link',
                        options: 'User',
                        reqd: 1,
                        get_query: function() {
                            return {
                                query: 'egrm.server_scripts.queries.get_project_users',
                                filters: {
                                    project: frm.doc.project
                                }
                            };
                        }
                    },
                    {
                        fieldname: 'comment',
                        label: __('Reason'),
                        fieldtype: 'Small Text',
                        reqd: 1
                    }
                ],
                function(values) {
                    frappe.call({
                        method: 'egrm.server_scripts.issue_actions.reassign_issue',
                        args: {
                            issue: frm.doc.name,
                            assignee: values.assignee,
                            comment: values.comment
                        },
                        callback: function(r) {
                            if (r.message) {
                                frm.reload_doc();
                                frappe.show_alert({
                                    message: __('Issue reassigned successfully'),
                                    indicator: 'green'
                                });
                            }
                        }
                    });
                },
                __('Reassign Issue'),
                __('Reassign')
                );
            }, __('Actions'));
            
            // Add feedback collection button
            if (!frm.doc.resolution_accepted) {
                frm.add_custom_button(__('Collect Feedback'), function() {
                    frappe.prompt([
                        {
                            fieldname: 'resolution_accepted',
                            label: __('Resolution Accepted'),
                            fieldtype: 'Select',
                            options: '1=Accepted\n2=Rejected',
                            reqd: 1
                        },
                        {
                            fieldname: 'rating',
                            label: __('Rating (0-5)'),
                            fieldtype: 'Int',
                            reqd: 1
                        },
                        {
                            fieldname: 'comment',
                            label: __('Feedback'),
                            fieldtype: 'Small Text',
                            reqd: 1
                        }
                    ],
                    function(values) {
                        frappe.call({
                            method: 'egrm.server_scripts.issue_actions.collect_feedback',
                            args: {
                                issue: frm.doc.name,
                                resolution_accepted: values.resolution_accepted,
                                rating: values.rating,
                                comment: values.comment
                            },
                            callback: function(r) {
                                if (r.message) {
                                    frm.reload_doc();
                                    frappe.show_alert({
                                        message: __('Feedback collected successfully'),
                                        indicator: 'green'
                                    });
                                }
                            }
                        });
                    },
                    __('Collect Citizen Feedback'),
                    __('Submit')
                    );
                }, __('Actions'));
            }
        } else if (frm.doc.docstatus === 0) { // Draft
            // Add track issue button for public access
            if (frm.doc.tracking_code) {
                frm.add_custom_button(__('Public Tracking URL'), function() {
                    let tracking_url = window.location.origin + '/issue-tracker?code=' + frm.doc.tracking_code;
                    frappe.prompt({
                        fieldname: 'url',
                        label: __('Tracking URL'),
                        fieldtype: 'Small Text',
                        read_only: 1,
                        default: tracking_url
                    });
                });
            }
        }
        
        // Add comment button for all states
        frm.add_custom_button(__('Add Comment'), function() {
            frappe.prompt([
                {
                    fieldname: 'comment',
                    label: __('Comment'),
                    fieldtype: 'Small Text',
                    reqd: 1
                },
                {
                    fieldname: 'due_at',
                    label: __('Follow-up Date (Optional)'),
                    fieldtype: 'Datetime'
                }
            ],
            function(values) {
                // Add a row to the comments table
                let comment = frm.add_child('grm_issue_comment');
                comment.user = frappe.session.user;
                comment.comment = values.comment;
                comment.due_at = values.due_at;
                
                frm.save();
                frappe.show_alert({
                    message: __('Comment added successfully'),
                    indicator: 'green'
                });
            },
            __('Add Comment'),
            __('Add')
            );
        });
        
        // Add button to view confidential information
        if (frm.doc.citizen_type === "1") { // Confidential
            frm.add_custom_button(__('View Confidential Info'), function() {
                // Call server methods to get confidential data
                frappe.call({
                    method: "get_citizen_name",
                    doc: frm.doc,
                    callback: function(r) {
                        if(r.message) {
                            let citizen = r.message;
                            
                            // Also get contact info if available
                            frappe.call({
                                method: "get_contact_info",
                                doc: frm.doc,
                                callback: function(r2) {
                                    let contact = r2.message || "None";
                                    
                                    frappe.msgprint({
                                        title: __('Confidential Information'),
                                        indicator: 'blue',
                                        message: __('Citizen: {0}<br>Contact: {1}', [
                                            citizen,
                                            contact
                                        ])
                                    });
                                }
                            });
                        }
                    }
                });
            }).addClass('btn-primary');
            
            frm.set_intro(__('This issue contains confidential citizen data that is securely stored using Frappe\'s Password field type.'), 'yellow');
        }
        
        // Highlight escalated issues
        if (frm.doc.escalate_flag) {
            frm.get_field('escalate_flag').$input.css('background-color', '#ffccc7');
            frm.set_intro(__('This issue has been escalated and requires attention.'), 'red');
        }
        
        // Load allowed statuses for this issue
        if (frm.doc.docstatus === 1) { // Submitted
            frappe.call({
                method: 'egrm.server_scripts.queries.get_allowed_statuses',
                args: {
                    issue: frm.doc.name
                },
                callback: function(r) {
                    if (r.message) {
                        frm.doc.__onload = frm.doc.__onload || {};
                        frm.doc.__onload.allowed_statuses = r.message;
                    }
                }
            });
        }
    },
    
    setup: function(frm) {
        // Set up field filters
        
        // Filter status based on project
        frm.set_query('status', function() {
            return {
                query: 'egrm.server_scripts.queries.get_status_by_project',
                filters: {
                    project: frm.doc.project || ''
                }
            };
        });
        
        // Filter category based on project
        frm.set_query('category', function() {
            return {
                query: 'egrm.server_scripts.queries.get_category_by_project',
                filters: {
                    project: frm.doc.project || ''
                }
            };
        });
        
        // Filter issue type based on project
        frm.set_query('issue_type', function() {
            return {
                query: 'egrm.server_scripts.queries.get_issue_type_by_project',
                filters: {
                    project: frm.doc.project || ''
                }
            };
        });
        
        // Filter administrative region based on project
        frm.set_query('administrative_region', function() {
            return {
                filters: {
                    project: frm.doc.project || ''
                }
            };
        });
        
        // Filter citizen groups based on project
        frm.set_query('citizen_age_group', function() {
            return {
                query: 'egrm.server_scripts.queries.get_age_group_by_project',
                filters: {
                    project: frm.doc.project || ''
                }
            };
        });
        
        frm.set_query('citizen_group_1', function() {
            return {
                query: 'egrm.server_scripts.queries.get_citizen_group_by_project',
                filters: {
                    project: frm.doc.project || '',
                    group_type: '1'
                }
            };
        });
        
        frm.set_query('citizen_group_2', function() {
            return {
                query: 'egrm.server_scripts.queries.get_citizen_group_by_project',
                filters: {
                    project: frm.doc.project || '',
                    group_type: '2'
                }
            };
        });
        
        // Filter assignee based on project
        frm.set_query('assignee', function() {
            return {
                query: 'egrm.server_scripts.queries.get_project_users',
                filters: {
                    project: frm.doc.project || ''
                }
            };
        });
    },
    
    onload: function(frm) {
        // Set default status for new issues
        if (frm.is_new()) {
            // Find initial status for the selected project
            if (frm.doc.project) {
                frappe.call({
                    method: 'egrm.server_scripts.queries.get_initial_status',
                    args: {
                        project: frm.doc.project
                    },
                    callback: function(r) {
                        if (r.message) {
                            frm.set_value('status', r.message);
                        }
                    }
                });
            }
            
            // Set reporter to current user if empty
            if (!frm.doc.reporter) {
                frm.set_value('reporter', frappe.session.user);
            }
        }
    },
    
    project: function(frm) {
        // When project changes, clear dependent fields
        frm.set_value('status', '');
        frm.set_value('category', '');
        frm.set_value('issue_type', '');
        frm.set_value('administrative_region', '');
        frm.set_value('citizen_age_group', '');
        frm.set_value('citizen_group_1', '');
        frm.set_value('citizen_group_2', '');
        frm.set_value('assignee', '');
        
        // Find initial status for the selected project
        if (frm.doc.project) {
            frappe.call({
                method: 'egrm.server_scripts.queries.get_initial_status',
                args: {
                    project: frm.doc.project
                },
                callback: function(r) {
                    if (r.message) {
                        frm.set_value('status', r.message);
                    }
                }
            });
        }
    },
    
    category: function(frm) {
        // When category changes, suggest assignee based on department
        if (frm.doc.category && frm.doc.project) {
            frappe.call({
                method: 'egrm.server_scripts.queries.get_department_for_category',
                args: {
                    category: frm.doc.category
                },
                callback: function(r) {
                    if (r.message) {
                        let department = r.message.department;
                        let redirection = r.message.redirection;
                        
                        if (department) {
                            if (redirection === "0") { // Assign to head
                                frappe.call({
                                    method: 'frappe.client.get_value',
                                    args: {
                                        doctype: 'GRM Issue Department',
                                        filters: {
                                            name: department
                                        },
                                        fieldname: 'head'
                                    },
                                    callback: function(r2) {
                                        if (r2.message && r2.message.head) {
                                            frm.set_value('assignee', r2.message.head);
                                        }
                                    }
                                });
                            } else if (redirection === "1") { // Assign to least loaded
                                frappe.call({
                                    method: 'egrm.server_scripts.queries.get_least_loaded_user',
                                    args: {
                                        department: department,
                                        project: frm.doc.project
                                    },
                                    callback: function(r2) {
                                        if (r2.message) {
                                            frm.set_value('assignee', r2.message);
                                        }
                                    }
                                });
                            }
                        }
                    }
                }
            });
        }
    },
    
    citizen_type: function(frm) {
        // When citizen type changes
        if(frm.doc.citizen_type === "1") {
            // Clear the non-confidential field
            frm.set_value('citizen', '');
            frm.set_value('contact_information', '');
            
            // Show message about confidential data
            frappe.show_alert({
                message: __('Please enter confidential citizen information'),
                indicator: 'blue'
            }, 5);
        } else {
            // Clear the confidential fields
            frm.set_value('citizen_confidential', '');
            frm.set_value('contact_info_confidential', '');
        }
        
        frm.refresh_fields();
    },
    
    contact_medium: function(frm) {
        // When contact medium changes
        frm.refresh_fields();
        
        // Require contact information for non-anonymous contacts
        if (frm.doc.contact_medium === "contact") {
            if (frm.doc.citizen_type === "1") {
                frm.toggle_reqd('contact_info_confidential', true);
                frm.toggle_reqd('contact_information', false);
            } else {
                frm.toggle_reqd('contact_information', true);
                frm.toggle_reqd('contact_info_confidential', false);
            }
        } else {
            frm.toggle_reqd('contact_information', false);
            frm.toggle_reqd('contact_info_confidential', false);
        }
    },
    
    validate: function(frm) {
        // Validate contact information based on citizen type
        if (frm.doc.contact_medium === "contact") {
            if (frm.doc.citizen_type === "1") {
                if (!frm.doc.contact_info_confidential) {
                    frappe.msgprint({
                        title: __('Validation Error'),
                        indicator: 'red',
                        message: __('Confidential Contact Information is required when Contact Medium is "contact" and Citizen Type is "Confidential".')
                    });
                    validated = false;
                }
            } else {
                if (!frm.doc.contact_information) {
                    frappe.msgprint({
                        title: __('Validation Error'),
                        indicator: 'red',
                        message: __('Contact Information is required when Contact Medium is "contact".')
                    });
                    validated = false;
                }
            }
        }
        
        // Validate citizen information based on type
        if (frm.doc.citizen_type === "1") {
            if (!frm.doc.citizen_confidential) {
                frappe.msgprint({
                    title: __('Validation Error'),
                    indicator: 'red',
                    message: __('Confidential Citizen information is required when Citizen Type is "Confidential".')
                });
                validated = false;
            }
        } else {
            if (!frm.doc.citizen) {
                frappe.msgprint({
                    title: __('Validation Error'),
                    indicator: 'red',
                    message: __('Citizen information is required.')
                });
                validated = false;
            }
        }
    }
});