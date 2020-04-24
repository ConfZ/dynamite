import tempfile
import copy
import random
import itertools
import math
from pathlib import Path
from collections import defaultdict 
# from numba import njit 
# import numpy as np

import settings as dig_settings
import helpers.vcommon as dig_common_helpers
import helpers.src as dig_src
import data.prog as dig_prog
from data.prog import Symb, Symbs
from data.traces import Traces
from helpers.miscs import Z3, Miscs
# from bin import Bin

from utils import settings
from utils.logic import *
from utils.loop import *
from lib import *

mlog = dig_common_helpers.getLogger(__name__, settings.logger_level)

class Setup(object):
    def __init__(self, seed, inp):
        self.seed = seed
        self.inp = inp
        self.is_java_inp = inp.endswith(".java") or inp.endswith(".class")
        self.is_c_inp = inp.endswith(".c")
        self.is_binary_inp = self.is_binary(inp)
        assert (self.is_java_inp or self.is_c_inp or self.is_binary_inp), inp

        # Dig's settings
        dig_settings.DO_MINMAXPLUS = False
        dig_settings.DO_MINMAXPLUS = False

        self.n_inps = settings.n_inps
        self.preloop_loc = dig_settings.TRACE_INDICATOR + '1' # vtrace1
        self.inloop_loc = dig_settings.TRACE_INDICATOR + '2' # vtrace2
        self.postloop_loc = dig_settings.TRACE_INDICATOR + '3' # vtrace3
        self.transrel_loc = dig_settings.TRACE_INDICATOR + '4' # vtrace4
        # self.refinement_depth = 1
        self.tmpdir = Path(tempfile.mkdtemp(dir=dig_settings.tmpdir, prefix="Dig_"))
        self.symstates = None
        self.solver = Solver(self.tmpdir)
        
        if self.is_binary_inp:
            from bin import Bin
            prog = Bin(self.inloop_loc, inp)
            inp_decls, inv_decls, mainQ_name = prog.parse()
        else:
            if self.is_java_inp:
                from helpers.src import Java as java_src
                src = java_src(Path(inp), self.tmpdir)
                exe_cmd = dig_settings.Java.JAVA_RUN(tracedir=src.tracedir, funname=src.funname)
            else:
                from helpers.src import C as c_src
                # import alg
                mlog.debug("Create C source for mainQ: {}".format(self.tmpdir))
                src = c_src(Path(inp), self.tmpdir)
                exe_cmd = dig_settings.C.C_RUN(exe=src.traceexe)
                if settings.prove_nonterm:
                    try:
                        mlog.debug("Get symstates for proving NonTerm (prove_nonterm={})".format(settings.prove_nonterm))
                        self.symstates = self._get_c_symstates_from_src(src)
                    except Exception as e:
                        mlog.debug("Get symstates for proving NonTerm: {}".format(e))
                        raise e
                    # ss = self.symstates.ss
                    # for loc in ss:
                        # for depth in ss[loc]:
                            # pcs = ss[loc][depth]
                            # mlog.debug("DEPTH {}".format(depth))
                            # mlog.debug("pcs ({}):\n{}".format(len(pcs.lst), pcs))
                else:
                    pass
                
            inp_decls, inv_decls, mainQ_name = src.inp_decls, src.inv_decls, src.mainQ_name
            prog = dig_prog.Prog(exe_cmd, inp_decls, inv_decls)

        mlog.debug("inp_decls ({}): {}".format(type(inp_decls), inp_decls))
        mlog.debug("inv_decls ({}): {}".format(type(inv_decls), inv_decls))

        self.inp_decls = inp_decls
        self.inv_decls = inv_decls
        self.mainQ_name = mainQ_name

        self.transrel_pre_inv_decls, self.transrel_pre_sst, \
            self.transrel_post_sst, transrel_inv_decls = self.gen_transrel_sst()
        self.inv_decls[self.transrel_loc] = transrel_inv_decls
        mlog.debug("transrel_pre_inv_decls: {}".format(self.transrel_pre_inv_decls))
        mlog.debug("transrel_pre_sst: {}".format(self.transrel_pre_sst))
        mlog.debug("transrel_post_sst: {}".format(self.transrel_post_sst))

        self.exe = Execution(prog)
        self.dig = Inference(self.inv_decls, self.seed, self.tmpdir)
        self.cl = Classification(self.preloop_loc, self.inloop_loc, self.postloop_loc)

        mlog.debug("generate random inputs")
        rand_inps = self.exe.gen_rand_inps(self.n_inps)
        mlog.debug("get traces from random inputs")
        self.rand_itraces = self.exe.get_traces_from_inps(rand_inps)  # itraces: input to dtraces

    def _get_c_symstates_from_src(self, src):
        from data.symstates import SymStatesC
        
        exe_cmd = dig_settings.C.C_RUN(exe=src.traceexe)
        inp_decls, inv_decls, mainQ_name = src.inp_decls, src.inv_decls, src.mainQ_name

        symstates = SymStatesC(inp_decls, inv_decls)
        symstates.compute(src.symexefile, src.mainQ_name,
                          src.funname, src.symexedir)
        # mlog.debug("symstates: {}".format(symstates.ss))
        return symstates

    def _get_loopinfo_symstates(self):
        stem = self._get_stem_symstates()
        loop = self._get_loop_symstates()
        return LoopInfo(stem, loop)

    def _get_stem_symstates(self):
        assert self.symstates, self.symstates

        ss = self.symstates.ss
        if self.preloop_loc in ss:
            preloop_symstates = ss[self.preloop_loc]
            preloop_ss_depths = sorted(preloop_symstates.keys())
            preloop_fst_symstate = None
            while preloop_fst_symstate is None and preloop_ss_depths:
                depth = preloop_ss_depths.pop()
                symstates = preloop_symstates[depth]
                if symstates.lst:
                    preloop_fst_symstate = symstates.lst[0]
            mlog.debug("preloop_fst_symstate: {}".format(preloop_fst_symstate))

            if preloop_fst_symstate:
                mlog.debug("mainQ init_symvars: {}".format(self.symstates.init_symvars))
                stem_cond = preloop_fst_symstate.pc
                stem_transrel = preloop_fst_symstate.slocal
                mlog.debug("stem_cond ({}): {}".format(type(stem_cond), stem_cond))
                mlog.debug("stem_transrel ({}): {}".format(type(stem_transrel), stem_transrel))
                stem = Stem(self.inp_decls, stem_cond, stem_transrel)
                return stem
        return None

    def _get_loop_symstates(self):
        if self.is_c_inp:
            from helpers.src import C as c_src
        
            tmpdir = Path(tempfile.mkdtemp(dir=dig_settings.tmpdir, prefix="Dig_"))
            mlog.debug("Create C source for vloop: {}".format(tmpdir))
            src = c_src(Path(self.inp), tmpdir, mainQ="vloop")
            symstates = self._get_c_symstates_from_src(src)
            ss = symstates.ss
        else:
            raise NotImplementedError

        inp_decls, inv_decls = src.inp_decls, src.inv_decls
        loop_init_symvars = symstates.init_symvars
        mlog.debug("vloop inp_decls: {}".format(inp_decls))
        mlog.debug("vloop inv_decls: {}".format(inv_decls))
        mlog.debug("vloop init_symvars: {}".format(loop_init_symvars))
        
        if self.inloop_loc in ss:
            inloop_symstates = ss[self.inloop_loc]
            inloop_ss_depths = sorted(inloop_symstates.keys())
            inloop_fst_symstate = None
            inloop_snd_symstate = None
            while (inloop_fst_symstate is None or inloop_snd_symstate is None) and inloop_ss_depths:
                depth = inloop_ss_depths.pop()
                symstates = inloop_symstates[depth]
                # mlog.debug("DEPTH {}".format(depth))
                # mlog.debug("symstates ({}):\n{}".format(len(symstates.lst), symstates))
                if len(symstates.lst) >= 2:
                    inloop_fst_symstate = symstates.lst[0]
                    inloop_snd_symstate = symstates.lst[1]
            
            if inloop_fst_symstate and inloop_snd_symstate:
                # Get loop's condition and transition relation
                inloop_fst_slocal = z3.substitute(inloop_fst_symstate.slocal, self.transrel_pre_sst)
                inloop_snd_slocal = z3.substitute(inloop_snd_symstate.slocal, self.transrel_post_sst)
                mlog.debug("inloop_fst_slocal: {}".format(inloop_fst_slocal))
                mlog.debug("inloop_snd_slocal: {}".format(inloop_snd_slocal))
                inloop_vars = Z3.get_vars(inloop_fst_symstate.slocal).union(Z3.get_vars(inloop_snd_symstate.slocal))
                inloop_inv_vars = inv_decls[self.inloop_loc].exprs(settings.use_reals)
                inloop_ex_vars = inloop_vars.difference(inloop_inv_vars)
                # mlog.debug("inloop_ex_vars: {}".format(inloop_ex_vars))
                # inloop_trans_f = z3.Exists(list(inloop_ex_vars), z3.And(inloop_fst_slocal, inloop_snd_slocal))
                # loop_transrel = Z3.qe(inloop_trans_f)
                # X_x, X_y -> x, y
                init_sst = list(zip(loop_init_symvars.exprs(settings.use_reals),
                                    inp_decls.exprs(settings.use_reals)))
                loop_transrel = z3.And(inloop_fst_slocal, inloop_snd_slocal)
                loop_transrel = z3.substitute(loop_transrel, init_sst)
                mlog.debug("loop_transrel: {}".format(loop_transrel))

                mlog.debug("inloop_fst_symstate: pc: {}".format(inloop_fst_symstate.pc))
                mlog.debug("inloop_fst_symstate: slocal: {}".format(inloop_fst_symstate.slocal))
                # loop_cond = Z3.qe(z3.Exists(list(inloop_ex_vars), 
                #                                   z3.And(inloop_fst_symstate.pc, inloop_fst_symstate.slocal)))
                loop_cond = z3.substitute(inloop_fst_symstate.pc, init_sst)
                mlog.debug("loop_cond: {}".format(loop_cond))
                terms = Solver.get_mul_terms(loop_cond)
                nonlinear_terms = list(itertools.filterfalse(lambda t: not Solver.is_nonlinear_mul_term(t), terms))
                mlog.debug("terms: {}".format(terms))
                mlog.debug("nonlinear_terms: {}".format(nonlinear_terms))

                return Loop(inp_decls, loop_cond, loop_transrel)
        return None

    def _get_loopinfo_traces(self):
        raise NotImplementedError
        # old_do_ieqs = dig_settings.DO_IEQS
        # # dig_settings.DO_IEQS = False
        # transrel_itraces = {}
        # inloop_loc = self.inloop_loc
        # postloop_loc = self.postloop_loc
        # for inp, dtraces in self.rand_itraces.items():
        #     if inloop_loc in dtraces:
        #         inloop_traces = dtraces[inloop_loc]
        #         transrel_traces = []
        #         if len(inloop_traces) >= 1:
        #             if postloop_loc in dtraces:
        #                 inloop_zip_traces = zip(inloop_traces, inloop_traces[1:] + [dtraces[postloop_loc][0]])
        #             else:
        #                 inloop_zip_traces = zip(inloop_traces[:-1], inloop_traces[1:])
        #         else:
        #             inloop_zip_traces = []
        #         for transrel_pre, transrel_post in inloop_zip_traces:
        #             ss = tuple(list(map(lambda s: s + '0', transrel_pre.ss)) + 
        #                        list(map(lambda s: s + '1', transrel_post.ss)))
        #             vs = transrel_pre.vs + transrel_post.vs
        #             transrel_traces.append(Trace.parse(ss, vs))
        #         transrel_itraces[inp] = {self.transrel_loc: transrel_traces}
        # # mlog.debug("transrel_itraces: {}".format(transrel_itraces))
        # transrel_invs = self.dig.infer_from_traces(transrel_itraces, self.transrel_loc)
        # # transrel_invs = self.dig.infer_from_traces(self.rand_itraces, self.transrel_loc)
        # mlog.debug("transrel_invs: {}".format(transrel_invs))
        # dig_settings.DO_IEQS = old_do_ieqs

        # transrel_invs = ZConj(transrel_invs)
        # if transrel_invs.is_unsat():
        #     return None
        # transrel_expr = transrel_invs.expr()
        # return transrel_expr

    def get_loopinfo(self):
        loopinfo = self._get_loopinfo_symstates()
        if loopinfo is None:
            loopinfo = self._get_loopinfo_traces()
        return loopinfo

    def infer_precond(self):
        if not self.symstates:
            return None
        else:
            ss = self.symstates
            preloop_symstates = ss[self.preloop_loc]
            preloop_ss_depths = sorted(preloop_symstates.keys())
            for depth in preloop_ss_depths:
                symstates = preloop_symstates[depth]
                return symstates.myexpr

    def infer_loop_cond(self):
        if self.is_c_inp:
            from helpers.src import C as c_src
            from data.symstates import SymStatesC
            import alg
            tmpdir = Path(tempfile.mkdtemp(dir=dig_settings.tmpdir, prefix="Dig_"))
            mlog.debug("Create C source for vloop")
            src = c_src(Path(self.inp), tmpdir, mainQ="vloop")
            exe_cmd = dig_settings.C.C_RUN(exe=src.traceexe)
            inp_decls, inv_decls, mainQ_name = src.inp_decls, src.inv_decls, src.mainQ_name
            prog = dig_prog.Prog(exe_cmd, inp_decls, inv_decls)
            exe = Execution(prog)
            dig = Inference(inv_decls, self.seed)

            symstates = SymStatesC(inp_decls, inv_decls)
            symstates.compute(
                src.symexefile, src.mainQ_name,
                src.funname, src.symexedir)
            ss = symstates.ss
            # mlog.debug("SymStates ({}): {}".format(type(ss), ss))
            # for loc, depthss in ss.items():
            #     for depth, states in depthss.items():
            #         for s in states.lst:
            #             mlog.debug("SymState ({}, {}):\n{}\n{}".format(type(s), s in states, s, s.expr))

            # rand_inps = exe.gen_rand_inps(self.n_inps)
            # rand_itraces = exe.get_traces_from_inps(rand_inps)
            # loop_cond = None
            # no_inloop_invs = False
            # no_postloop_invs = False

            # while loop_cond is None:
            #     postloop_invs = ZConj(dig.infer_from_traces(rand_itraces, self.postloop_loc))
            #     inloop_invs = ZConj(dig.infer_from_traces(rand_itraces, self.inloop_loc))
            #     mlog.debug("postloop_invs: {}".format(postloop_invs))
            #     mlog.debug("inloop_invs: {}".format(inloop_invs))
            #     if not inloop_invs and no_inloop_invs:
            #         loop_cond = postloop_invs.negate()
            #     else:
            #         if not inloop_invs:
            #             no_inloop_invs = True
            #         covered_f = z3.Or(postloop_invs.expr(), inloop_invs.expr())
            #         uncovered_f = z3.Not(covered_f)
            #         models, _ = Solver.get_models(uncovered_f, 
            #                                       self.n_inps, self.tmpdir, 
            #                                       settings.use_random_seed)
            #         mlog.debug("uncovered models: {}".format(models))
            #         if isinstance(models, list) and models:
            #             n_inps = Solver.mk_inps_from_models(models, self.inp_decls.exprs((settings.use_reals)), exe)
            #             mlog.debug("uncovered inps: {}".format(n_inps))
            #             mlog.debug("Starting get_traces")
            #             nitraces = exe.get_traces_from_inps(n_inps)
            #             mlog.debug("get_traces stopped")
            #             # mlog.debug("uncovered rand_itraces: {}".format(nitraces))
            #             rand_itraces.update(nitraces)
            #         else:
            #             loop_cond = inloop_invs
            
            # mlog.debug("loop_cond: {}".format(loop_cond))
            # return loop_cond

    def gen_transrel_sst(self):
        inloop_inv_decls = self.inv_decls[self.inloop_loc]
        inloop_inv_exprs = inloop_inv_decls.exprs(settings.use_reals)
        transrel_pre_inv_decls = [dig_prog.Symb(s.name + '0', s.typ) for s in inloop_inv_decls]
        transrel_pre_inv_exprs = dig_prog.Symbs(transrel_pre_inv_decls).exprs(settings.use_reals)
        transrel_post_inv_decls = [dig_prog.Symb(s.name + '1', s.typ) for s in inloop_inv_decls]
        transrel_post_inv_exprs = dig_prog.Symbs(transrel_post_inv_decls).exprs(settings.use_reals)

        transrel_inv_decls = dig_prog.Symbs(transrel_pre_inv_decls + transrel_post_inv_decls)

        return transrel_pre_inv_exprs, \
               list(zip(inloop_inv_exprs, transrel_pre_inv_exprs)), \
               list(zip(inloop_inv_exprs, transrel_post_inv_exprs)), \
               transrel_inv_decls

    def is_binary(self, fn):
        import subprocess
        mime = subprocess.Popen(["file", "--mime", fn], stdout=subprocess.PIPE).communicate()[0]
        return b"application/x-executable" in mime

class NonTerm(object):
    def __init__(self, config):
        self._config = config
        loopinfo = config.get_loopinfo()
        self.stem = loopinfo.stem
        self.loop = loopinfo.loop
        self.tCexs = []

    def verify(self, rcs):
        assert isinstance(rcs, ZFormula), rcs
        assert not rcs.is_unsat(), rcs
        _config = self._config

        if not rcs:
            return True, None 
        else:
            # assert rcs, rcs
            if _config.is_c_inp:
                init_symvars_prefix = dig_settings.C.CIVL_INIT_SYMVARS_PREFIX

            loop_transrel = self.loop.transrel
            loop_cond = self.loop.cond

            mlog.debug("loop_transrel: {}".format(loop_transrel))
            mlog.debug("loop_cond: {}".format(loop_cond))
            mlog.debug("rcs: {}".format(rcs))

            if not rcs.implies(ZFormula([loop_cond])):
                mlog.debug("rcs_cond =/=> loop_cond")
                rcs.add(loop_cond)

            rcs_lst = list(rcs)
            def mk_label(e):
                if e in rcs_lst:
                    return 'c_' + str(rcs_lst.index(e))
                else:
                    return None
            labeled_rcs, label_d = ZFormula.label(rcs, mk_label)
            mlog.debug("labeled_rcs: {}".format(labeled_rcs))

            # R /\ T => R'
            # rcs_l = z3.substitute(rcs.expr(), _config.transrel_pre_sst)
            # mlog.debug("rcs_l: {}".format(rcs_l))
            init_transrel_rcs = ZFormula.substitue(labeled_rcs, _config.transrel_pre_sst)
            init_transrel_rcs.add(loop_transrel)
            init_transrel_rcs.add(self.stem.cond)
            init_transrel_rcs.add(self.stem.transrel)
            mlog.debug("init_transrel_rcs: {}".format(init_transrel_rcs))

            # Unreachable recurrent set
            if init_transrel_rcs.is_unsat():
                return False, None

            dg = defaultdict(list)
            def _check(rc):
                rc_label = label_d[rc]
                mlog.debug("rc: {}:{}".format(rc, rc_label))
                # init_transrel_rcs is sat
                init_f = copy.deepcopy(init_transrel_rcs)
                rc_r = z3.substitute(rc, _config.transrel_post_sst)
                init_f.add(z3.Not(rc_r))
                mlog.debug("rc_r: {}".format(rc_r))
                mlog.debug("init_f: {}".format(init_f))
                init_inp_decls = Symbs([Symb(init_symvars_prefix + s.name, s.typ) for s in _config.inp_decls])
                
                rs, _, unsat_core = _config.solver.get_models(init_f, _config.n_inps, init_inp_decls, settings.use_random_seed)
                if rs is None:
                    mlog.debug("rs: unknown")
                elif rs is False:
                    mlog.debug("rs: unsat")
                    mlog.debug("unsat_core: {}".format(unsat_core))
                    # assert unsat_core is not None, unsat_core
                    # dg[rc_label] = unsat_core
                else:
                    # isinstance(rs, list) and rs:
                    init_rs = []
                    init_symvars_prefix_len = len(init_symvars_prefix)
                    for r in rs:
                        init_r = []
                        for (x, v) in r:
                            if x.startswith(init_symvars_prefix):
                                init_r.append((x[init_symvars_prefix_len:], v))
                        if init_r:
                            init_rs.append(init_r)

                    mlog.debug("init_rs: sat ({} models)".format(len(init_rs)))
                    rs = _config.solver.mk_inps_from_models(
                                init_rs, _config.inp_decls.exprs(settings.use_reals), _config.exe)
                return rs

            chks = [(rc, _check(rc)) for rc in rcs]

            mlog.debug("dg: {}".format(dg))
            mlog.debug("label_d: {}".format(label_d))

            if all(rs is False for _, rs in chks):
                return True, None  # valid
            else:
                sCexs = []
                for rc, rs in chks:
                    if rs is None:
                        return False, None  # unknown
                    elif rs:  # sat
                        assert isinstance(rs, Inps), rs
                        assert len(rs) > 0
                        itraces = _config.exe.get_traces_from_inps(rs)
                        sCexs.append((rc, itraces))
                return False, sCexs  # invalid with a set of new Inps

    def strengthen(self, rcs, invalid_rc, itraces):
        _config = self._config
        base_term_inps, term_inps, mayloop_inps = _config.cl.classify_inps(itraces)
        mlog.debug("base_term_inps: {}".format(len(base_term_inps)))
        mlog.debug("term_inps: {}".format(len(term_inps)))
        mlog.debug("mayloop_inps: {}".format(len(mayloop_inps)))
        mlog.debug("rcs: {}".format(rcs))

        mayloop_invs = ZConj(_config.dig.infer_from_traces(
                                itraces, _config.inloop_loc, mayloop_inps))
        mlog.debug("mayloop_invs: {}".format(mayloop_invs))

        term_invs = ZConj(_config.dig.infer_from_traces(
                            itraces, _config.inloop_loc, term_inps, maxdeg=1))
        mlog.debug("term_invs: {}".format(term_invs))

        term_traces = []
        for term_inp in term_inps:
            term_traces.append(itraces[term_inp])
        self.tCexs.append((term_invs, term_traces))
        
        # term_cond = z3.Or(base_term_pre.expr(), term_invs.expr())
        # term_cond = term_invs.expr()
        # simplified_term_cond = Z3.simplify(term_cond)
        # cnf_term_cond = Z3.to_cnf(simplified_term_cond)
        # mlog.debug("simplified_term_cond: {}".format(simplified_term_cond))
        # mlog.debug("cnf_term_cond: {}".format(cnf_term_cond))
        # dnf_neg_term_cond = Z3.to_nnf(z3.Not(cnf_term_cond))
        # mlog.debug("dnf_neg_term_cond: {}".format(dnf_neg_term_cond))

        candidate_nrcs = []

        for term_inv in term_invs:
            # mlog.debug("term_inv: {}".format(term_inv))
            nrcs = copy.deepcopy(rcs)
            nrcs.add(z3.Not(term_inv))
            candidate_nrcs.append(nrcs)
        
        # if invalid_rc is not None:
        #     nrcs = copy.deepcopy(rcs)
        #     nrcs.remove(invalid_rc)
        #     mlog.debug("invalid_rc: {}".format(invalid_rc))
        #     mlog.debug("nrcs: {}".format(nrcs))
        #     if nrcs:
        #         candidate_nrcs.append(nrcs)
        
        return candidate_nrcs

    def _stat_candidate_rcs(self, rcs):
        stat = defaultdict(int)
        for (_, d, _) in rcs:
            stat[d] += 1
        mlog.debug("stat ({} total): {}".format(len(rcs), stat))

    def prove(self):
        _config = self._config
        validRCS = []

        if self.stem is None or self.loop is None:
            mlog.debug("No loop information: stem={}, loop={}".format(self.stem, self.loop))
            return []
        else:
            # candidate rcs, depth, ancestors
            candidateRCS = [(ZConj([self.loop.cond]), 0, [])]
            while candidateRCS:
                # mlog.debug("candidateRCS: {}".format(len(candidateRCS)))
                self._stat_candidate_rcs(candidateRCS)
                # use 0 for queue
                rcs, depth, ancestors = candidateRCS.pop(0)
                mlog.debug("PROVE_NT DEPTH {}: {}".format(depth, rcs))
                if rcs.is_unsat():
                    continue

                if depth < settings.max_nonterm_refinement_depth:
                    chk, sCexs = self.verify(rcs)
                    # mlog.debug("sCexs: {}".format(sCexs))
                    if chk:
                        validRCS.append((rcs, ancestors))
                        # return the first valid rcs
                        # return validRCS
                    elif sCexs is not None:
                        for invalid_rc, cexs in sCexs:
                            nrcs = self.strengthen(rcs, invalid_rc, cexs)
                            # assert nrcs, nrcs
                            for nrc in nrcs:
                                nancestors = copy.deepcopy(ancestors)
                                nancestors.append((depth, rcs))
                                candidateRCS.append((nrc, depth+1, nancestors))
            for (tInvs, tTraces) in self.tCexs:
                mlog.debug("tCex: {}".format(tInvs))
            return validRCS

class Term(object):
    def __init__(self, config):
        self._config = config
        self.ntCexs = []
        self.MAX_TRANS_NUM = 50

    def infer_ranking_function(self, vs, term_itraces):
        _config = self._config
        terms = Miscs.get_terms([sage.all.var(v) for v in vs.names], 1)
        rnk_template, uks = Miscs.mk_template(terms, None, retCoefVars=True)
        mlog.debug("rnk_template: {}".format(rnk_template))
        mlog.debug("uks: {}".format(uks))

        zuks = []
        for uk in uks:
            suk = str(uk)
            zuk = z3.Int(suk)
            globals()[suk] = zuk
            zuks.append(zuk)

        def zabs(x):
            return z3.If(x >= 0, x, -x)

        opt = z3.Optimize()
        zabs_sum = functools.reduce(lambda u, v: u + v, [zabs(u) for u in zuks])
        opt.minimize(zabs_sum)
        for zuk in zuks:
            opt.minimize(zabs(zuk))

        train_rand_trans = []
        test_rand_trans = []
        for term_inp in term_itraces:
            term_traces = term_itraces[term_inp]
            inloop_term_traces = term_traces[_config.inloop_loc]
            postloop_term_traces = term_traces[_config.postloop_loc]

            assert inloop_term_traces, inloop_term_traces
            assert postloop_term_traces, postloop_term_traces

            inloop_rnk_terms = [self._to_Z3(rnk_template.subs(t.mydict)) for t in inloop_term_traces]
            postloop_rnk_terms = [self._to_Z3(rnk_template.subs(t.mydict)) for t in postloop_term_traces]

            rnk_terms = inloop_rnk_terms + postloop_rnk_terms[:1]

            rnk_trans_idx = list(itertools.combinations(range(len(rnk_terms)), 2))
            random.shuffle(rnk_trans_idx)
            rnk_trans_idx_len = len(rnk_trans_idx)
            splitter_idx = min(self.MAX_TRANS_NUM, rnk_trans_idx_len)
            # mlog.debug("splitter_idx: {}".format(splitter_idx))
            # splitter_idx = rnk_trans_idx_len
            for (i1, i2) in rnk_trans_idx[:splitter_idx]:
                assert i1 < i2, (i1, i2)
                rand_trans = (rnk_terms[i1], rnk_terms[i2])
                # mlog.debug("rand_trans: {} -> {}: {}".format(i1, i2, rand_trans))
                train_rand_trans.append(rand_trans)

        mlog.debug("train_rand_trans: {}".format(len(train_rand_trans)))
        # random.shuffle(train_rand_trans)

        # import timeit

        # arr_train_rand_trans = np.asarray(train_rand_trans)
        # mlog.debug("arr_train_rand_trans: {}".format(arr_train_rand_trans.size / 2))
        # while arr_train_rand_trans.size != 0:
        #     (t1, t2) = arr_train_rand_trans[0]
        #     model = self._infer_ranking_function_trans(t1, t2, opt)
        #     mlog.debug("model: {}".format(model))
        #     if model:
        #         mlog.debug("t1: {}".format(t1))
        #         mlog.debug("t2: {}".format(t2))

        #         start_time = timeit.default_timer()
        #         f_check = lambda t: not (self._check_ranking_function_trans(*t, model))
        #         bool_index = np.apply_along_axis(f_check, 1, arr_train_rand_trans)
        #         arr_train_rand_trans = arr_train_rand_trans[bool_index]
        #         elapsed = timeit.default_timer() - start_time
        #         mlog.debug("a_train_rand_trans: {}".format(elapsed * 1000000))
        #     else:
        #         arr_train_rand_trans = np.delete(arr_train_rand_trans, [0])
        #     mlog.debug("arr_train_rand_trans: {}".format(arr_train_rand_trans.size / 2))
            
        while train_rand_trans:
            (t1, t2) = train_rand_trans.pop()
            model = self._infer_ranking_function_trans(t1, t2, opt)
            mlog.debug("model: {}".format(model))
            if model:
                mlog.debug("t1: {}".format(t1))
                mlog.debug("t2: {}".format(t2))

                # start_time = timeit.default_timer()
                # l_train_rand_trans = [(t1, t2) for (t1, t2) in train_rand_trans 
                #                               if not (self._check_ranking_function_trans(t1, t2, model))]
                # elapsed = timeit.default_timer() - start_time
                # mlog.debug("l_train_rand_trans: {}".format(elapsed * 1000000))
                
                # start_time = timeit.default_timer()
                i_train_rand_trans = itertools.filterfalse(lambda t: (self._check_ranking_function_trans(*t, model)),
                                                           train_rand_trans)
                # elapsed = timeit.default_timer() - start_time
                # mlog.debug("i_train_rand_trans: {}".format(elapsed * 1000000))

                # arr_train_rand_trans = np.asarray(train_rand_trans)
                # start_time = timeit.default_timer()
                # f_check = lambda t: not (self._check_ranking_function_trans(*t, model))
                # bool_index = np.apply_along_axis(f_check, 1, arr_train_rand_trans)
                # arr_train_rand_trans = arr_train_rand_trans[bool_index]
                # elapsed = timeit.default_timer() - start_time
                # mlog.debug("a_train_rand_trans: {}".format(elapsed * 1000000))

                train_rand_trans = list(i_train_rand_trans)
            mlog.debug("train_rand_trans: {}".format(len(train_rand_trans)))

    def _check_ranking_function_trans(self, t1, t2, model):
        # import timeit
        # start_time = timeit.default_timer()
        # s = z3.Solver()
        # s.add(t1 > t2)
        # s.add(t1 >= 0)
        # for d in model.decls():
        #     zuk = globals()[d.name()]
        #     s.add(zuk == model[d])
        # if s.check() == z3.sat:
        #     r = True
        # else:
        #     r = False
        # elapsed = timeit.default_timer() - start_time
        # mlog.debug("z3: {}".format(elapsed * 1000000))
        
        # start_time = timeit.default_timer()
        st1 = str(t1)
        st2 = str(t2)
        for d in model.decls():
            v = model[d]
            sv = v.as_string()
            dn = d.name()
            st1 = st1.replace(dn, sv)
            st2 = st2.replace(dn, sv)
        vt1 = eval(st1)
        vt2 = eval(st2)
        r = (vt1 > vt2) and (vt1 >= 0)
        # elapsed = timeit.default_timer() - start_time
        # mlog.debug("py: {}".format(elapsed * 1000000))

        return r

    def _infer_ranking_function_trans(self, t1, t2, opt):
        opt.push()
        # desc_scond = str(sage.all.operator.gt(t1, t2))
        # bnd_scond = str(sage.all.operator.ge(t1, 0))
        # desc_zcond = eval(desc_scond)
        # bnd_zcond = eval(bnd_scond)
        # desc_zcond = Z3.parse(desc_scond, False)
        # bnd_zcond = Z3.parse(bnd_scond, False)
        opt.add(t1 > t2)
        opt.add(t1 >= 0)

        model = None
        if opt.check() == z3.sat:
            model = opt.model()
            # mlog.debug("model: {}".format(model))
        opt.pop()
        return model

    def _to_Z3(self, f):
        return Z3.parse(str(f), False)

    def prove(self):
        _config = self._config
        itraces = _config.rand_itraces
        preloop_term_invs = None
        while preloop_term_invs is None:
            base_term_inps, term_inps, mayloop_inps = _config.cl.classify_inps(itraces)
            mlog.debug("base_term_inps: {}".format(len(base_term_inps)))
            mlog.debug("term_inps: {}".format(len(term_inps)))
            mlog.debug("mayloop_inps: {}".format(len(mayloop_inps)))

            preloop_term_invs = _config.dig.infer_from_traces(
                                    itraces, _config.preloop_loc, term_inps, maxdeg=2)
            if preloop_term_invs is None:
                rand_inps = _config.exe.gen_rand_inps(_config.n_inps)
                rand_itraces = _config.exe.get_traces_from_inps(rand_inps)
                old_itraces_len = len(itraces)
                old_itraces_keys = set(itraces.keys())
                itraces.update(rand_itraces)
                new_itraces_len = len(itraces)
                new_itraces_keys = set(itraces.keys())
                mlog.debug("new rand inps: {}".format(new_itraces_keys.difference(old_itraces_keys)))
                if new_itraces_len <= old_itraces_len:
                    break
                    
        mlog.debug("preloop_term_invs: {}".format(preloop_term_invs))
        mlog.debug("itraces: {}".format(len(itraces)))
        mlog.debug("term_inps: {}".format(len(term_inps)))
        inloop_term_invs = ZConj(_config.dig.infer_from_traces(
                            itraces, _config.inloop_loc, term_inps,
                            maxdeg=2))
        
        mlog.debug("inloop_term_invs: {}".format(inloop_term_invs))

        # Generate ranking function template
        vs = _config.inv_decls[_config.inloop_loc]
        term_itraces = dict((term_inp, itraces[term_inp]) for term_inp in term_inps)
        self.infer_ranking_function(vs, term_itraces)