"""Whole-layout reference validation, hidden-item preservation and safe commits."""
from copy import deepcopy
import json
import os
from unittest.mock import patch

import pytest

from openpowermenu.core import DEFAULT_CONFIG, load_config
from openpowermenu.layout_edit import LayoutEdits, LayoutEditError, reply
from openpowermenu.recovery import MAX_CONFIG_BYTES


def references(entries):
    return [dict(id=e['id'], **({'items': references(e['items'])} if e['kind'] == 'submenu' else {})) for e in entries]


@pytest.fixture
def layout(tmp_path):
    target = tmp_path / 'menu.json'
    config = {**deepcopy(DEFAULT_CONFIG), 'appearance': 'aero', 'custom': {'keep': [1, 2]},
              'menu': [{'separator': True, 'custom': 'leading'},
                       {'label': 'Unavailable', 'command': ['/missing-opm-tool', 'private-argument'], 'id': 'user-id'},
                       {'submenu': 'Work', 'icon': 'folder', 'custom': {'keep': True}, 'items': [
                           {'label': 'Literal', 'command': ['echo', 'two words', ';'], 'requires': ['not-installed']},
                           {'separator': True}]},
                       {'submenu': 'Empty', 'items': []}, {'action': 'files'}, {'separator': True}]}
    target.write_text(json.dumps(config))
    return target, config, LayoutEdits(target)


def test_begin_is_complete_nonexecuting_and_cancel_writes_nothing(layout):
    target, config, edits = layout
    before = target.read_bytes()
    with patch('subprocess.Popen', side_effect=AssertionError('editing executed a program')):
        view = edits.begin()
        assert len(view['entries']) == len(config['menu'])
        assert view['entries'][0]['kind'] == 'separator'
        assert view['entries'][3]['items'] == []
        assert len(view['entries'][2]['items']) == 2
        assert 'private-argument' not in json.dumps(view) and 'command' not in view['entries'][1]
        assert edits.cancel(view['token'])
    assert target.read_bytes() == before and list(target.parent.iterdir()) == [target]


def definitions(items):
    result = []
    for entry in items:
        data = deepcopy(entry)
        if 'submenu' in entry:
            result.extend(definitions(data.pop('items')))
        result.append(json.dumps(data, sort_keys=True))
    return sorted(result)


def test_reorder_reparent_preserves_every_definition_and_general_setting(layout):
    target, original, edits = layout
    before = target.read_bytes()
    view = edits.begin()
    order = references(view['entries'])
    order[3]['items'].append(order[2]['items'].pop(0))
    order[3]['items'].append(order.pop(1))
    order.reverse()
    assert edits.save(view['token'], json.dumps(order)) == {'ok': True, 'changed': True}
    saved = load_config(target)
    assert {k: v for k, v in saved.items() if k != 'menu'} == {k: v for k, v in original.items() if k != 'menu'}
    assert definitions(saved['menu']) == definitions(original['menu'])
    assert len(saved['menu'][2]['items']) == 2  # previously empty submenu
    assert list(target.parent.glob('menu.json.bak-*'))[0].read_bytes() == before
    assert not edits.sessions


def test_unchanged_layout_does_not_write_or_backup(layout):
    target, _, edits = layout
    before = target.read_bytes()
    view = edits.begin()
    assert edits.save(view['token'], json.dumps(references(view['entries'])))['changed'] is False
    assert target.read_bytes() == before and list(target.parent.iterdir()) == [target]


@pytest.mark.parametrize('bad', ['duplicate', 'missing', 'unknown', 'argv', 'label', 'leaf-children',
                                'missing-children', 'cycle', 'not-array', 'bad-json', 'duplicate-field', 'oversize'])
def test_invalid_proposals_never_write(layout, bad):
    target, _, edits = layout
    view = edits.begin()
    order = references(view['entries'])
    if bad == 'duplicate': order.append(deepcopy(order[0]))
    elif bad == 'missing': order.pop()
    elif bad == 'unknown': order[0]['id'] = 'unknown'
    elif bad == 'argv': order[1]['command'] = ['untrusted-command']
    elif bad == 'label': order[1]['label'] = 'Changed'
    elif bad == 'leaf-children': order[1]['items'] = []
    elif bad == 'missing-children': del order[2]['items']
    elif bad == 'cycle': order[2]['items'].append(deepcopy(order[2]))
    elif bad == 'not-array': order = {'items': order}
    payload = json.dumps(order)
    if bad == 'bad-json': payload = '{broken'
    elif bad == 'duplicate-field': payload = '[{"id":"x","id":"y"}]'
    elif bad == 'oversize': payload = ' ' * (MAX_CONFIG_BYTES + 1)
    before = target.read_bytes()
    result = json.loads(reply(lambda: edits.save(view['token'], payload)))
    assert result['ok'] is False
    assert target.read_bytes() == before and list(target.parent.iterdir()) == [target]
    assert edits.keep(view['token'])  # rejected requests retain the draft


@pytest.mark.parametrize('change', ['content', 'replacement', 'deletion', 'symlink'])
def test_stale_or_unsafe_target_preserves_external_changes(layout, change):
    target, _, edits = layout
    view = edits.begin()
    order = list(reversed(references(view['entries'])))
    stamp = target.stat().st_mtime_ns
    if change == 'content':
        target.write_text('{"menu":[]}')
        os.utime(target, ns=(stamp, stamp))
    elif change == 'replacement':
        other = target.with_name('replacement')
        other.write_bytes(target.read_bytes())
        other.replace(target)
    else:
        target.unlink()
        if change == 'symlink': target.symlink_to(target.with_name('missing'))
    before = target.read_bytes() if target.is_file() else None
    result = json.loads(reply(lambda: edits.save(view['token'], json.dumps(order))))
    assert not result['ok']
    assert result['code'] == ('configuration' if change == 'symlink' else 'conflict')
    assert (target.read_bytes() if target.is_file() else None) == before
    assert not list(target.parent.glob('menu.json.bak-*'))


def test_failed_atomic_save_keeps_history_and_session(layout):
    target, _, edits = layout
    view = edits.begin()
    payload = json.dumps(list(reversed(references(view['entries']))))
    before = target.read_bytes()
    with patch('openpowermenu.core.os.replace', side_effect=OSError('disk full')):
        assert not json.loads(reply(lambda: edits.save(view['token'], payload)))['ok']
    assert target.read_bytes() == before and edits.keep(view['token'])
    assert list(target.parent.glob('menu.json.bak-*'))[0].read_bytes() == before
    assert edits.save(view['token'], payload)['ok']


def test_session_bounds_expiration_restart_and_repeated_cycles(layout):
    target, _, _ = layout
    now = [0]
    edits = LayoutEdits(target, clock=lambda: now[0])
    tokens = [edits.begin()['token'] for _ in range(edits.MAX_SESSIONS)]
    with pytest.raises(LayoutEditError, match='another'): edits.begin()
    now[0] = edits.IDLE_SECONDS - 1
    edits.keep(tokens[0])
    now[0] += 2
    with pytest.raises(LayoutEditError, match='expired'): edits.keep(tokens[1])
    assert edits.keep(tokens[0])
    with pytest.raises(LayoutEditError, match='restarted'): LayoutEdits(target).keep(tokens[0])
    assert edits.cancel(tokens[0])
    for _ in range(10):
        view = edits.begin()
        edits.cancel(view['token'])
    assert not edits.sessions


@pytest.mark.parametrize('limit', ['count', 'depth'])
def test_reparent_limits_rejected(tmp_path, limit):
    target = tmp_path / 'menu.json'
    if limit == 'count':
        menu = [{'submenu': 'Full', 'items': [{'action': 'files'}] * 200}, {'action': 'terminal'}]
    else:
        nested = {'action': 'files'}
        for _ in range(8): nested = {'submenu': 'Deep', 'items': [nested]}
        menu = [nested, {'submenu': 'Extra', 'items': []}]
    target.write_text(json.dumps({'menu': menu}))
    before = target.read_bytes()
    edits = LayoutEdits(target)
    view = edits.begin()
    order = references(view['entries'])
    destination = order[0]['items']
    if limit == 'depth':
        for _ in range(7): destination = destination[0]['items']
    destination.append(order.pop())
    assert not json.loads(reply(lambda: edits.save(view['token'], json.dumps(order))))['ok']
    assert target.read_bytes() == before
