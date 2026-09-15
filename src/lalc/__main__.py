from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) == 2 and args[0] == "--candidate-runner":
        from .candidate_runner import run_candidate

        return run_candidate(args[1])
    if len(args) == 3 and args[0] == "--packaging-probe":
        from .packaging_probe import run_probe

        return run_probe(args[1], args[2])
    if args:
        print("usage: lalc [--candidate-runner REQUEST | --packaging-probe SOURCE RESULT]", file=sys.stderr)
        return 2
    from .gui import run_gui

    return run_gui()


if __name__ == "__main__":
    raise SystemExit(main())
