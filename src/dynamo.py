from __future__ import absolute_import
import os
import sys
import time
import datetime
import itertools

dynamo_path = os.path.realpath(os.path.dirname(__file__))
dig_path = os.path.realpath(os.path.join(dynamo_path, '../deps/dig/src'))
sys.path.insert(0, dig_path)

import helpers.vcommon as dig_common_helpers
import alg as dig_alg


def run_dig(inp, seed, maxdeg, do_rmtmp):

    mlog.info("{}".format("get invs from DIG"))

    if inp.endswith(".java") or inp.endswith(".class"):
        dig = dig_alg.DigSymStates(inp)
    else:
        dig = dig_alg.DigTraces.from_tracefiles(inp)
    invs, traces, tmpdir = dig.start(seed, maxdeg)

    if do_rmtmp:
        import shutil
        print("clean up: rm -rf {}".format(tmpdir))
        shutil.rmtree(tmpdir)
    else:
        print("tmpdir: {}".format(tmpdir))


if __name__ == "__main__":
    import settings as dig_settings
    from helpers import src_java as dig_src_java
    from data import miscs as dig_miscs
    from utils import settings
    import argparse

    aparser = argparse.ArgumentParser("Dynamo")
    ag = aparser.add_argument
    ag("inp", help="inp")

    # Dynamo settings
    ag("--log_level", "-log_level",
       type=int,
       choices=range(5),
       default=3,
       help="set logger info")

    ag("--run_dig", "-run_dig",
        action="store_true",
        help="run DIG on the input")

    # DIG settings
    ag("--dig_log_level", "-dig_log_level",
       type=int,
       choices=range(5),
       default=2,
       help="DIG: set logger info")
    ag("--dig_seed", "-dig_seed",
       type=float,
       help="DIG: use this seed in DIG")
    ag("--dig_nomp", "-dig_nomp",
       action="store_true",
       help="DIG: don't use multiprocessing")

    args = aparser.parse_args()

    settings.run_dig = args.run_dig

    dig_settings.DO_MP = not args.dig_nomp

    # Set DIG's log level
    if 0 <= args.dig_log_level <= 4 and args.dig_log_level != dig_settings.logger_level:
        dig_settings.logger_level = args.dig_log_level
    dig_settings.logger_level = dig_common_helpers.getLogLevel(
        dig_settings.logger_level)

    if 0 <= args.log_level <= 4 and args.log_level != settings.logger_level:
        settings.logger_level = args.log_level
    settings.logger_level = dig_common_helpers.getLogLevel(
        settings.logger_level)

    mlog = dig_common_helpers.getLogger(__name__, settings.logger_level)

    mlog.info("{}: {}".format(datetime.datetime.now(), ' '.join(sys.argv)))

    inp = os.path.realpath(os.path.expanduser(args.inp))
    seed = round(time.time(), 2) if args.dig_seed is None else float(args.dig_seed)

    if settings.run_dig:
        run_dig(inp, seed, maxdeg=2, do_rmtmp=False)
    else:
        assert(inp.endswith(".java") or inp.endswith(".class"))
        import tempfile
        tmpdir = tempfile.mkdtemp(dir=dig_settings.tmpdir, prefix="Dig_")
        (inp_decls, inv_decls, clsname, mainQ_name, jpfdir, jpffile,
         tracedir, traceFile) = dig_src_java.parse(inp, tmpdir)
        exe_cmd = dig_settings.JAVA_RUN(tracedir=tracedir, clsname=clsname)
        prog = dig_miscs.Prog(exe_cmd, inp_decls, inv_decls)
        from data.traces import Inps, Trace, DTraces
        inps = Inps()
        rInps = prog.gen_rand_inps(100)
        mlog.debug("gen {} random inps".format(len(rInps)))
        rInps = inps.merge(rInps, inp_decls.names)
        traces = prog._get_traces_mp(rInps)
        itraces = {}
        for inp, lines in traces.items():
            # print inp
            # print lines
            dtraces = {}
            for l in lines:
                # vtrace1: 8460 16 0 1 16 8460
                parts = l.split(':')
                assert len(parts) == 2, parts
                loc, tracevals = parts[0], parts[1]
                loc = loc.strip()  # vtrace1
                ss = inv_decls[loc].names
                vs = tracevals.strip().split()
                mytrace = Trace.parse(ss, vs)
                # print mytrace
                if loc not in dtraces:
                    dtraces[loc] = [mytrace]
                else:
                    dtraces[loc].append(mytrace)
            # print dtraces.__str__(printDetails=True)
            itraces[inp] = dtraces
        # print itraces
        base_term_input = []
        term_input = []
        mayloop_input = []
        for inp, dtraces in itraces.items():
            print "{}: {}".format(inp, dtraces.keys())
            chains = dtraces.keys()
            if 'vtrace3' in chains:
                if 'vtrace2' in chains:
                    term_input.append(inp)
                else:
                    base_term_input.append(inp)
            else:
                mayloop_input.append(inp)
        # print "base_term: {}".format(base_term_input)
        # print "term: {}".format(term_input)
        # print "mayloop: {}".format(mayloop_input)

        def infer (tracename, inps, inv_decls):
            dtraces = DTraces()
            for inp in inps:
                for trace in itraces[inp][tracename]:
                    dtraces.add(tracename, trace)
            # print "dtraces: {}".format(dtraces.__str__(printDetails=True))
            dig = dig_alg.DigTraces.from_dtraces(inv_decls, dtraces)
            invs, traces, tmpdir = dig.start(seed, maxdeg=2)


        # BASE/LOOP CONDITION
        infer('vtrace1', base_term_input, inv_decls)
        infer('vtrace1', term_input + mayloop_input, inv_decls)
        infer('vtrace2', term_input + mayloop_input, inv_decls)
        infer('vtrace3', term_input, inv_decls)
        
        # infer('vtrace1', mayloop_input, inv_decls)

        # infer('vtrace1', term_input, inv_decls)
        # infer('vtrace1', mayloop_input, inv_decls)
        # infer('vtrace2', mayloop_input, inv_decls)


        # traces = prog.get_traces(rInps)
        # print traces.__str__(printDetails=True)
