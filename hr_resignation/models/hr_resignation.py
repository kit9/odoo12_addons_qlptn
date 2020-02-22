# -*- coding: utf-8 -*-
import datetime
from datetime import datetime
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
date_format = "%Y-%m-%d"


class HrResignation(models.Model):
    _name = 'hr.resignation'
    _inherit = 'mail.thread'
    _rec_name = 'employee_id'

    def _get_employee_id(self):
        # assigning the related employee of the logged in user
        employee_rec = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
        return employee_rec.id

    name = fields.Char(string='Order Reference', required=True, copy=False, readonly=True, index=True,
                       default=lambda self: _('New'))
    employee_id = fields.Many2one('hr.employee', string="Nhân viên", default=_get_employee_id,
                                  help='Name of the employee for whom the request is creating')
    department_id = fields.Many2one('hr.department', string="Phòng ban", related='employee_id.department_id', store=True,
                                    help='Department of the employee')
    joined_date = fields.Date(string="Ngày vào làm", required=True,
                              help='Joining date of the employee')
    expected_revealing_date = fields.Date(string="Ngày từ chức", required=True,
                                          help='Date on which he is revealing from the company')
    resign_confirm_date = fields.Date(string="Từ chức ngày xác nhận", help='Date on which the request is confirmed')
    approved_revealing_date = fields.Date(string="Ngày phê duyệt", help='The date approved for the relieving')
    reason = fields.Text(string="Reason", help='Specify reason for leaving the company')
    notice_period = fields.Char(string="Notice Period", compute='_notice_period')
    state = fields.Selection([('draft', 'Bản nháp'), ('confirm', 'Xác nhận'), ('approved', 'Chấp thuận'), ('cancel', 'Hủy')],
                             string='Trạng thái', default='draft')
    type_reason = fields.Many2one('hr.resignation.reason', "Lý do", required=True)
    job = fields.Many2one('hr.job', 'Job position', related='employee_id.job_id', store=True)

    @api.onchange('employee_id')
    def set_join_date(self):
        self.joined_date = self.employee_id.joining_date if self.employee_id.joining_date else ''

    @api.model
    def create(self, vals):
        # assigning the sequence for the record
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('hr.resignation') or _('New')
        res = super(HrResignation, self).create(vals)
        return res

    @api.constrains('employee_id')
    def check_employee(self):
        # Checking whether the user is creating leave request of his/her own
        for rec in self:
            if not self.env.user.has_group('hr.group_hr_user'):
                if rec.employee_id.user_id.id and rec.employee_id.user_id.id != self.env.uid:
                    raise ValidationError(_('You cannot create request for other employees'))

    @api.onchange('employee_id')
    @api.depends('employee_id')
    def check_request_existence(self):
        # Check whether any resignation request already exists
        for rec in self:
            if rec.employee_id:
                resignation_request = self.env['hr.resignation'].search([('employee_id', '=', rec.employee_id.id),
                                                                         ('state', 'in', ['confirm', 'approved'])])
                if resignation_request:
                    raise ValidationError(_('There is a resignation request in confirmed or'
                                            ' approved state for this employee'))

    @api.multi
    def _notice_period(self):
        # calculating the notice period for the employee
        for rec in self:
            if rec.approved_revealing_date and rec.resign_confirm_date:
                approved_date = datetime.strptime(str(rec.approved_revealing_date), date_format)
                confirmed_date = datetime.strptime(str(rec.resign_confirm_date), date_format)
                notice_period = approved_date - confirmed_date
                rec.notice_period = notice_period.days

    @api.constrains('joined_date', 'expected_revealing_date')
    def _check_dates(self):
        # validating the entered dates
        for rec in self:
            resignation_request = self.env['hr.resignation'].search([('employee_id', '=', rec.employee_id.id),
                                                                     ('state', 'in', ['confirm', 'approved'])])
            if resignation_request:
                raise ValidationError(_('There is a resignation request in confirmed or'
                                        ' approved state for this employee'))
            if rec.joined_date >= rec.expected_revealing_date:
                raise ValidationError(_('Relieving date must be anterior to joining date'))

    @api.multi
    def confirm_resignation(self):
        for rec in self:
            rec.state = 'confirm'
            rec.resign_confirm_date = str(datetime.now())

    @api.multi
    def cancel_resignation(self):
        for rec in self:
            rec.state = 'cancel'

    @api.multi
    def reject_resignation(self):
        for rec in self:
            rec.state = 'rejected'

    @api.multi
    def approve_resignation(self):
        for rec in self:
            if not rec.approved_revealing_date:
                raise ValidationError(_('Enter Approved Relieving Date'))
            if rec.approved_revealing_date and rec.resign_confirm_date:
                if rec.approved_revealing_date < rec.resign_confirm_date:
                    raise ValidationError(_('Approved relieving date must be anterior to confirmed date'))
                rec.state = 'approved'

    @api.multi
    def update_employee_status(self):
        resignation = self.env['hr.resignation'].search([('state', '=', 'approved')])
        for rec in resignation:
            if rec.approved_revealing_date <= fields.Date.today() and rec.employee_id.active:
                rec.employee_id.active = False
                rec.employee_id.resign_date = rec.approved_revealing_date
                # if rec.employee_id.hr_point_kpi > 0 and rec.type_reason.point_kpi > 0:
                #     rec.employee_id.hr_point_kpi = rec.employee_id.hr_point_kpi - (rec.employee_id.hr_point_kpi /100 * rec.employee_id.hr_point_kpi)

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    resign_date = fields.Date('Ngày từ chức', readonly=True)

class RecruitmentDegree(models.Model):
    _name = "hr.resignation.reason"
    _description = "resignation reason"
    _sql_constraints = [
        ('name_uniq', 'unique (name)', 'Lý do đã tồn tại!')
    ]

    name = fields.Char("Lý do", required=True, translate=True)
    point_kpi = fields.Float('Hệ số điểm', digits=(16, 1), default=1)
    sequence = fields.Integer("Sequence", default=1, help="Gives the sequence order when displaying a list of degrees.")