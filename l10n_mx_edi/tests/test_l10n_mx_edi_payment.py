# -*- coding: utf-8 -*-

from datetime import timedelta
from os.path import join
from lxml import objectify
from odoo.tools import misc
from odoo.tests.common import Form
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
from . import common


class TestL10nMxEdiPayment(common.InvoiceTransactionCase):
    def setUp(self):
        super(TestL10nMxEdiPayment, self).setUp()
        self.config_parameter = self.env.ref(
            'l10n_mx_edi.l10n_mx_edi_version_cfdi')
        self.config_parameter.value = '3.3'
        self.tax_positive.l10n_mx_cfdi_tax_type = 'Tasa'
        self.tax_negative.l10n_mx_cfdi_tax_type = 'Tasa'
        isr_tag = self.env['account.account.tag'].search(
            [('name', '=', 'ISR')])
        for rep_line in self.tax_negative.invoice_repartition_line_ids:
            rep_line.tag_ids |= isr_tag
        self.product.l10n_mx_edi_code_sat_id = self.ref(
            'l10n_mx_edi.prod_code_sat_01010101')
        self.payment_method_manual_out = self.env.ref(
            "account.account_payment_method_manual_out")
        self.bank = self.env.ref('base.bank_ing')
        self.bank.l10n_mx_edi_vat = 'BBA830831LJ2'
        self.company_bank = self.env['res.partner.bank'].create({
            'acc_number': '1234567890',
            'bank_id': self.bank.id,
            'partner_id': self.company.id,
        })
        self.account_payment.bank_id = self.bank.id
        self.account_payment.acc_number = '0123456789'
        self.transfer = self.browse_ref('l10n_mx_edi.payment_method_transferencia')
        self.xml_expected_str = misc.file_open(join(
            'l10n_mx_edi', 'tests', 'expected_payment.xml')).read().encode('UTF-8')
        self.xml_expected = objectify.fromstring(self.xml_expected_str)
        self.set_currency_rates(mxn_rate=12.21, usd_rate=1)

        self.company.partner_id.write({
            'property_account_position_id': self.fiscal_position.id,
        })
        self.bank_journal = self.env['account.journal'].search([
            ('type', '=', 'bank')], limit=1)

    def test_l10n_mx_edi_payment_bank(self):
        journal = self.env['account.journal'].search(
            [('type', '=', 'bank')], limit=1)
        journal.bank_account_id = self.company_bank
        invoice = self.create_invoice()
        invoice.move_name = 'INV/2017/999'
        invoice.post()
        invoice.refresh()
        self.assertEqual(invoice.l10n_mx_edi_pac_status, "signed",
                         invoice.message_ids.mapped("body"))
        payment_register = Form(self.env['account.payment'].with_context(active_model='account.move', active_ids=invoice.ids))
        payment_register.payment_date = invoice.date
        payment_register.l10n_mx_edi_payment_method_id = self.transfer
        payment_register.payment_method_id = self.payment_method_manual_out
        payment_register.journal_id = journal
        payment_register.communication = invoice.name
        payment_register.amount = invoice.amount_total
        payment_register.l10n_mx_edi_partner_bank_id = self.account_payment
        payment_register.save().post()
        payment = invoice.payment_ids
        self.assertEqual(
            payment.l10n_mx_edi_pac_status, 'signed',
            payment.message_ids.mapped('body'))
        cfdi = payment.l10n_mx_edi_get_xml_etree()
        attribute = '//pago10:Pagos'
        namespace = {'pago10': 'http://www.sat.gob.mx/Pagos'}
        payment_xml = cfdi.Complemento.xpath(
            attribute, namespaces=namespace)[0]
        expected_xml = self.xml_expected.Complemento.xpath(
            attribute, namespaces=namespace)[0]
        expected_xml.Pago.attrib['FechaPago'] = payment_xml.Pago.get(
            'FechaPago')
        expected_xml.Pago.DoctoRelacionado.attrib[
            'IdDocumento'] = invoice.l10n_mx_edi_cfdi_uuid
        self.assertEqualXML(payment_xml, expected_xml)

    def test_invoice_multicurrency(self):
        """Create the next case, to check that payment complement is correct
            Invoice 1 - USD
            Invoice 2 - MXN
            Payment --- USD"""
        self.set_currency_rates(mxn_rate=1, usd_rate=0.05)
        invoices = self.create_invoice()
        invoices |= self.create_invoice(currency_id=self.mxn.id)
        invoices.action_invoice_open()
        self.bank_journal.currency_id = self.usd
        bank_statement = self.env['account.bank.statement'].create({
            'journal_id': self.bank_journal.id,
            'line_ids': [(0, 0, {
                'name': 'Payment',
                'partner_id': invoices[0].partner_id.id,
                'amount': invoices[0].amount_total + self.mxn.compute(
                    invoices[1].amount_total, self.usd),
                'currency_id': self.usd.id,
                'l10n_mx_edi_payment_method_id': self.payment_method_cash.id,
            })],
        })
        values = []
        lines = invoices.mapped('move_id.line_ids').filtered(
            lambda l: l.account_id.user_type_id.type == 'receivable')
        for line in lines:
            values.append({
                'credit': line.debit,
                'debit': 0,
                'name': line.name,
                'move_line': line,
            })
        bank_statement.line_ids.process_reconciliation(values)
        self.assertEquals(
            invoices.mapped('payment_ids').l10n_mx_edi_pac_status, 'signed',
            'The payment was not signed')

    def test_payment_multicurrency_writeoff(self):
        """Create a payment in USD to invoice in MXN with writeoff"""
        self.set_currency_rates(mxn_rate=1, usd_rate=0.055556)
        date_mx = self.env[
            'l10n_mx_edi.certificate'].sudo().get_mx_current_datetime()
        date = (date_mx - timedelta(days=1)).strftime(
            DEFAULT_SERVER_DATE_FORMAT)
        self.usd.rate_ids = self.rate_model.create({
            'rate': 0.05, 'name': date})
        invoice = self.create_invoice()
        invoice.date_invoice = date
        invoice.action_invoice_open()
        ctx = {'active_model': 'account.invoice', 'active_ids': [invoice.id]}
        register_payments = self.env['account.register.payments'].with_context(
            ctx).create({
                'payment_date': date_mx,
                'l10n_mx_edi_payment_method_id': self.env.ref(
                    'l10n_mx_edi.payment_method_efectivo').id,
                'payment_method_id': self.env.ref(
                    "account.account_payment_method_manual_in").id,
                'journal_id': self.bank_journal.id,
                'communication': invoice.number,
                'amount': invoice.amount_total, })
        payment = register_payments.create_payments()
        payment = self.env['account.payment'].search(payment.get('domain', []))
        self.assertEqual(payment.l10n_mx_edi_pac_status, "signed",
                         payment.message_ids.mapped('body'))
        cfdi = payment.l10n_mx_edi_get_xml_etree()
        self.asertEquals(
            payment.l10n_mx_edi_get_payment_etree(cfdi)[0].get('ImpSaldoInsoluto'), '0.00',
            'The invoice was not marked as fully paid in the payment complement.')
