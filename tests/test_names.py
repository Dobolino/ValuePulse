from valuepulse.names import canonical, names_match


def test_bayern_und_arsenal_werden_erkannt():
    assert names_match("FC Bayern München", "Bayern Munich")
    assert names_match("Arsenal FC", "Arsenal")
    assert names_match("1. FSV Mainz 05", "Mainz 05")
    assert names_match("Wolverhampton Wanderers", "Wolves")
    assert names_match("FC Internazionale Milano", "Inter Milan")


def test_unterschiedliche_teams_bleiben_getrennt():
    assert not names_match("Arsenal FC", "Aston Villa")
    assert canonical("Manchester United") != canonical("Manchester City")
