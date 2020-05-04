import os
import traceback
from pathlib import Path
from functools import partial
import helpers.vcommon as CM
from utils import settings

mlog = CM.getLogger(__name__, settings.logger_level)

class Validator(object):
    def __init__(self, tmpdir):
        mytempdir = tmpdir / self.short_name
        if not mytempdir.exists():
            mytempdir.mkdir()
        self.tmpdir = mytempdir
        self.witness_name = 'witness.graphml'
        self.witness = self.tmpdir / self.witness_name

    def prove_reach(self, input):
        cwd = os.getcwd()
        try:
            os.chdir(self.tmpdir)
            assert input.is_file(), input
            pcmd = self.prove_reach_cmd(input=input)
            mlog.debug("pcmd: {}".format(pcmd))
            rmsg, errmsg = CM.vcmd(pcmd)
            # assert not errmsg, "'{}': {}".format(pcmd, errmsg)
            mlog.debug("rmsg: {}".format(rmsg))
            res = self.parse_rmsg(rmsg)
            mlog.debug("res: {}".format(res))
            if res is False:
                assert self.witness.is_file(), self.witness
                vcmd = self.validate_witness_cmd(input=input)
                mlog.debug("vcmd: {}".format(vcmd))
                v_rmsg, v_errmsg = CM.vcmd(vcmd)
                # assert not v_errmsg, "'{}': {}".format(vcmd, v_errmsg)
                mlog.debug("v_rmsg: {}".format(v_rmsg))
                # mlog.debug("v_errmsg: {}".format(v_errmsg))
                v_res = self.parse_rmsg(v_rmsg)
                cex = self.tmpdir / self.cex_name
                assert v_res is False, v_res
                assert cex.is_file(), cex
                cex_model = self.parse_cex(cex)

        except Exception as ex:
            mlog.debug("Exception: {}".format(ex))
            mlog.debug(traceback.format_exc())
            res = None
        finally:
            os.chdir(cwd)
            return res

    def parse_rmsg(self, rmsg):
        res_index = rmsg.find(self.res_keyword)
        if res_index != -1:
            res = rmsg[(res_index + len(self.res_keyword)):]
            if 'TRUE' in res:
                return True
            elif 'FALSE' in res:
                return False
            else:
                return None
        else:
            return None

class CPAchecker(Validator):
    @property
    def short_name(self):
        return "cpa"

    @property
    def prove_reach_cmd(self):
        return partial(settings.CPAchecker.CPA_RUN, 
                       cpa_task_opts=settings.CPAchecker.CPA_REACH_OPTS)

    @property
    def validate_witness_cmd(self):
        return partial(settings.CPAchecker.CPA_RUN, 
                       cpa_task_opts=settings.CPAchecker.CPA_VALIDATE_OPTS(witness=self.witness))

    @property
    def res_keyword(self):
        return 'Verification result:'

    @property
    def cex_name(self):
        return 'UltimateCounterExample.errorpath'

    def parse_cex(self, cex):
        model_lines = [l for l in CM.iread(cex) if 'VAL' in l]
        last_model_line = model_lines[-1]
        mlog.debug("last_model_line: {}".format(last_model_line))

class Ultimate(Validator):
    @property
    def prove_reach_cmd(self):
        return partial(settings.Ultimate.ULT_RUN, 
                       variant=self.name,
                       task=settings.Ultimate.ULT_REACH_TASK,
                       witness_dir=self.tmpdir,
                       witness_name=self.witness_name)

    @property
    def validate_witness_cmd(self):
        return partial(settings.Ultimate.ULT_RUN, 
                       variant=self.name, 
                       task=settings.Ultimate.ULT_VALIDATE_TASK,
                       witness_dir=self.tmpdir,
                       witness_name=self.witness_name)

    @property
    def res_keyword(self):
        return 'Result:'

    @property
    def cex_name(self):
        return 'UltimateCounterExample.errorpath'

    def parse_cex(self, cex):
        model_lines = [l for l in CM.iread(cex) if 'VAL' in l]
        last_model_line = model_lines[-1]
        mlog.debug("last_model_line: {}".format(last_model_line))

class UAutomizer(Ultimate):
    @property
    def short_name(self):
        return "ult"

    @property
    def name(self):
        return 'UAutomizer'
        