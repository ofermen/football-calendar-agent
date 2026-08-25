from datetime import datetime
from zoneinfo import ZoneInfo
from models import Match
from broadcast_sources import visible_text, fixture_on_page, enrich_broadcasts

TZ=ZoneInfo('Asia/Jerusalem')
ALIASES={
    "Beer Sheva [CL]": ["Hapoel Be'er Sheva", "Beer Sheva"],
    "H. Tel Aviv": ["Hapoel Tel Aviv"],
    "Atalanta [Conf]": ["Atalanta"],
    "West Ham United [LC]": ["West Ham United"],
}

def m(home, away):
    return Match('x',home,away,'x',datetime(2026,8,25,20,tzinfo=TZ),'id')

def test_fixture_matching():
    html='''<div>Tuesday, 25 August</div><div>12:45 | Sabah vs Hapoel Be\'er Sheva | UEFA Champions League</div>'''
    assert fixture_on_page(visible_text(html), m('Sabah','Beer Sheva [CL]'), ALIASES)

def test_fixture_not_matching_wrong_game():
    html='''<div>Liverpool vs Nottingham Forest</div>'''
    assert not fixture_on_page(visible_text(html), m('Liverpool','Arsenal'), ALIASES)

def test_suffix_alias():
    html='''<div>Southampton vs West Ham United | League Cup</div>'''
    assert fixture_on_page(visible_text(html), m('Southampton','West Ham United [LC]'), ALIASES)


def test_ambiguous_channels_are_not_published(monkeypatch):
    match = m('Liverpool','Nottingham Forest')
    cfg = {
        'broadcast': {
            'sources': [
                {'channel':'Sport 1','url':'https://one'},
                {'channel':'Sport 2','url':'https://two'},
            ],
            'team_aliases': {},
        }
    }
    monkeypatch.setattr(
        'broadcast_sources.fetch_text',
        lambda url, timeout=20: '<div>Liverpool vs Nottingham Forest</div>'
    )
    warnings = enrich_broadcasts([match], cfg)
    assert match.channel is None
    assert any('ambiguous broadcast' in w for w in warnings)


def test_unique_channel_is_published(monkeypatch):
    match = m('Sabah','Beer Sheva [CL]')
    cfg = {
        'broadcast': {
            'sources': [
                {'channel':'5Sport','url':'https://five'},
                {'channel':'Sport 1','url':'https://one'},
            ],
            'team_aliases': ALIASES,
        }
    }
    def fake_fetch(url, timeout=20):
        if url.endswith('five'):
            return "<div>Sabah vs Hapoel Be'er Sheva</div>"
        return '<div>Other Team vs Another Team</div>'
    monkeypatch.setattr('broadcast_sources.fetch_text', fake_fetch)
    warnings = enrich_broadcasts([match], cfg)
    assert match.channel == '5Sport'
    assert warnings == []

def test_far_future_channel_is_not_published(monkeypatch):
    from datetime import timedelta
    from broadcast_sources import datetime as broadcast_datetime
    match = Match('x','Liverpool','Arsenal','Premier League',datetime.now(TZ)+timedelta(days=20),'far-id')
    cfg = {
        'broadcast': {
            'max_days_ahead': 14,
            'sources': [{'channel':'Sport 1','url':'https://one'}],
            'team_aliases': {},
        }
    }
    monkeypatch.setattr(
        'broadcast_sources.fetch_text',
        lambda url, timeout=20: '<div>Liverpool vs Arsenal</div>'
    )
    enrich_broadcasts([match], cfg)
    assert match.channel is None
