from stock_advisor.allocation import Allocation, allocate


def test_allocate_whole_shares_and_cash():
    allocs, cash = allocate({"A": 0.5, "B": 0.5}, {"A": 333.0, "B": 1000.0}, 100_000)
    assert allocs[0] == Allocation("A", 0.5, 150, 49_950, round(49_950 / 99_950, 6))
    assert allocs[1] == Allocation("B", 0.5, 50, 50_000, round(50_000 / 99_950, 6))
    assert cash == 50
    assert [x.ticker for x in allocs] == ["A", "B"]


def test_unaffordable_pick_gets_zero_shares():
    allocs, cash = allocate({"A": 0.1, "B": 0.9}, {"A": 50_000.0, "B": 100.0}, 10_000)
    assert allocs[0].shares == 0 and allocs[0].amount_inr == 0 and allocs[0].weight == 0.0
    assert allocs[1].shares == 90 and allocs[1].weight == 1.0
    assert cash == 1_000


def test_nothing_invested():
    allocs, cash = allocate({"A": 1.0}, {"A": 1_000_000.0}, 10_000)
    assert allocs[0].weight == 0.0
    assert cash == 10_000
