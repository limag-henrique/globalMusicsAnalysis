from chart_observatory.pipeline_state import StageResult, StageRunner


def test_rerun_skips_unchanged_stage_but_changed_input_or_output_recomputes(tmp_path):
    source = tmp_path / "input.txt"
    source.write_text("one")
    runner = StageRunner(tmp_path / "state")
    calls = []
    def action(output, checkpoint):
        calls.append(1)
        path = output / "result.txt"
        path.write_text(source.read_text())
        return StageResult("completed", {"valid": 1}, {"done": 1}, [path])
    first = runner.run("select", {"source": source}, action)
    assert first["status"] == "completed"
    assert runner.run("select", {"source": source}, action)["cached"] is True
    assert len(calls) == 1
    source.write_text("two")
    second = runner.run("select", {"source": source}, action)
    assert second["cached"] is False
    output_path = next(path for path in second["outputs"] if path.endswith("result.txt"))
    from pathlib import Path
    Path(output_path).write_text("corrupted")
    assert runner.run("select", {"source": source}, action)["cached"] is False
    assert len(calls) == 3


def test_blocked_state_is_not_complete_and_unmet_requirements_are_cached(tmp_path):
    runner = StageRunner(tmp_path / "state")
    calls = []
    def blocked(output, checkpoint):
        calls.append(1)
        return StageResult("blocked", {"validated": 0}, reason="human validation pending")
    record = runner.run("pilot", {}, blocked)
    assert record["status"] == "blocked"
    assert record["counters"]["validated"] == 0
    assert runner.run("pilot", {}, blocked)["cached"] is True
    assert len(calls) == 1


def test_failure_retries_are_explicit_and_bounded_without_leaking_secrets(tmp_path):
    runner = StageRunner(tmp_path / "state")
    def failed(output, checkpoint):
        raise RuntimeError("credential-must-not-leak")
    record = runner.run("provider", {}, failed)
    assert "credential-must-not-leak" not in str(record)
    assert runner.run("provider", {}, failed)["attempt"] == 1
    assert runner.run("provider", {}, failed, retry_failed=True)["attempt"] == 2
    assert runner.run("provider", {}, failed, retry_failed=True)["attempt"] == 3
    assert runner.run("provider", {}, failed, retry_failed=True)["attempt"] == 3


def test_live_input_mutation_does_not_become_a_frozen_completed_stage(tmp_path):
    source = tmp_path / "live.txt"
    source.write_text("one")
    runner = StageRunner(tmp_path / "state")
    def mutate(output, checkpoint):
        source.write_text("new observation")
        return StageResult("completed", {"attempted": 1})
    record = runner.run("collect", {"live": source}, mutate)
    assert record["status"] == "running"
    assert record["inputs_changed_during_stage"] is True
