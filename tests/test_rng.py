import pytest

from sinfony.rng import Rng


def test_same_seed_same_draws():
    assert Rng(42).random(5).tolist() == Rng(42).random(5).tolist()


def test_different_seeds_differ():
    assert Rng(1).random(5).tolist() != Rng(2).random(5).tolist()


def test_child_is_independent_of_parent_draws():
    a = Rng(7)
    b = Rng(7)
    b.random(100)  # consuming the parent must not shift its children
    assert a.child("melody").random(5).tolist() == b.child("melody").random(5).tolist()


def test_children_with_different_names_differ():
    r = Rng(7)
    assert r.child("a").random(5).tolist() != r.child("b").random(5).tolist()


def test_child_depends_on_parent_seed():
    assert Rng(1).child("x").random(3).tolist() != Rng(2).child("x").random(3).tolist()


def test_string_seeds_work():
    assert Rng("hello").random() == Rng("hello").random()


def test_choice_returns_an_item():
    assert Rng(0).choice(["a", "b", "c"]) in {"a", "b", "c"}


def test_choice_respects_probabilities():
    assert Rng(0).choice(["a", "b"], p=[0.0, 1.0]) == "b"


def test_choice_on_empty_raises():
    with pytest.raises(ValueError):
        Rng(0).choice([])
