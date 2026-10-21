from conftest import load_process_module

handoff = load_process_module("handoff")


def test_note_text_strips_header_and_line_numbers():
    raw = "[3 lines total]\n1\t# Title\n2\t\n3\tentry\twith tab\n"
    assert handoff.note_text(raw) == "# Title\n\nentry\twith tab"


def test_note_text_of_an_empty_note_is_empty_not_failed():
    assert handoff.note_text("[0 lines total]\n") == ""


def test_a_read_without_the_header_is_a_failed_read():
    assert handoff.note_text("") is None
    assert handoff.note_text("timeout") is None


def test_append_never_writes_after_a_failed_read(tmp_path, monkeypatch):
    calls = []

    def fake(*args, timeout=None):
        calls.append(args)
        return handoff.subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(handoff, "maestri", fake)
    handoff.append_handoff(tmp_path, "Some Handoffs", "TO X: hello")
    assert [c[:2] for c in calls] == [("note", "read")]
    assert "TO X: hello" in (tmp_path / ".process" / "handoffs.log").read_text()


def test_append_writes_back_clean_text(tmp_path, monkeypatch):
    calls = []

    def fake(*args, timeout=None):
        calls.append(args)
        out = "[2 lines total]\n1\t# H\n2\told\n" if args[1] == "read" else ""
        return handoff.subprocess.CompletedProcess(args, 0, out, "")

    monkeypatch.setattr(handoff, "maestri", fake)
    handoff.append_handoff(tmp_path, "Some Handoffs", "TO X: new")
    written = calls[-1][3]
    assert written.startswith("# H\nold\n") and written.rstrip().endswith("TO X: new")
    assert "\t" not in written.split("\n")[0]
