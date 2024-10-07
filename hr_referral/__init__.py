# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, SUPERUSER_ID


def _update_stage(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for (stage_ref, points) in [
        ("hr_recruitment.stage_job1", 1),
        ("hr_recruitment.stage_job2", 20),
        ("hr_recruitment.stage_job3", 9),
        ("hr_recruitment.stage_job4", 5),
        ("hr_recruitment.stage_job5", 50),
    ]:
        stage = env.ref(stage_ref, raise_if_not_found=False)
        if stage:
            stage.points = points


from . import models
from . import report
from . import wizard
