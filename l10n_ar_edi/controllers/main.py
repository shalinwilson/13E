# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import http
from odoo.addons.web.controllers.main import content_disposition


class DownloadCertificateRequst(http.Controller):

    @http.route('/l10n_ar_edi/download_csr/', type='http', auth="user")
    def download_csr(self, **kw):
        """ Download the certificate request file to upload in AFIP """
        content = http.request.env.company._l10n_ar_create_certificate_request()
        if not content:
            return http.request.not_found()
        return http.request.make_response(content, headers=[('Content-Type', 'text/plain'), ('Content-Disposition', content_disposition('request.csr'))])
