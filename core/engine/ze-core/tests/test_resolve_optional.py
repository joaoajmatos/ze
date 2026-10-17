from ze_core.container import _resolve


class _Dep:
    pass


class _Consumer:
    def __init__(self, dep: _Dep | None) -> None:
        self.dep = dep


def test_optional_parameter_gets_the_dep_when_registered():
    dep = _Dep()
    assert _resolve(_Consumer, {_Dep: dep}).dep is dep


def test_optional_parameter_is_none_when_nothing_registers_it():
    assert _resolve(_Consumer, {}).dep is None
