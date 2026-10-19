"""H2 entry point: additive registrations; the original lifecycle stays intact."""
from benchmark.manifest import ROOT
from benchmark.registry import REGISTRY, EpisodeRegistration, register_episode
from evaluator.suites import SUITES, EvaluationSuite


def register_h2():
    from benchmark.episodes.episode_d_v02 import build_episode_d_v02, FIXTURE_VERSION
    episode = EpisodeRegistration("D-V02", FIXTURE_VERSION, "episode_d_v02", "v02", ("v02",),
        build_episode_d_v02, (ROOT / "tests/public/test_episode_d_v02.py",
                            ROOT / "tests/public/dv02_inprocess_contract.py"),
        execution_strategy="shared-db-workers")
    suite = EvaluationSuite("episode_d_v02", "1.1.1",
        ROOT / "evaluator/hidden_tests/episode_d_v02", "D-V02",
        execution_strategy="shared-db-workers")
    if "D-V02" in REGISTRY:
        if REGISTRY["D-V02"] != episode:
            raise ValueError("D-v02 registration collision")
    else:
        register_episode(episode)
    if "episode_d_v02" in SUITES:
        if SUITES["episode_d_v02"] != suite:
            raise ValueError("D-v02 suite collision")
    else:
        SUITES[suite.id] = suite
    from evaluator.dv02_admission import install_admission
    install_admission()


def main():
    register_h2()
    from benchmark.cli import main as existing_main
    return existing_main()


if __name__ == "__main__":
    raise SystemExit(main())
