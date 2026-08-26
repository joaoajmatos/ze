def test_contribution_reexports_are_identical_to_ze_plugin_originals() -> None:
    import ze_plugin.contribution as _plugin
    import ze_sdk.contribution as _sdk

    for name in (
        "Contribution",
        "EvidenceRef",
        "SourceFunction",
        "TargetFace",
        "validate_and_submit",
    ):
        assert getattr(_sdk, name) is getattr(_plugin, name)
