from server.skills import list_skills_catalog, match_skills


def test_list_skills_catalog_not_empty():
    skills = list_skills_catalog()
    assert len(skills) >= 1
    ids = {s["id"] for s in skills}
    assert "music-pr-discovery" in ids or "web-research" in ids


def test_match_skills_music_pr():
    matched = match_skills("Find UK indie radio pluggers for a rock release")
    assert len(matched) >= 1
    assert any("music" in s.get("id", "").lower() or "pr" in s.get("name", "").lower() for s in matched)
