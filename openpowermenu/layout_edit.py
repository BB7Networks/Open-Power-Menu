"""Reference-only rearrangement of a complete configuration, never commands.

Each bounded, temporary session owns its original configuration and revision.
The client receives presentation data and opaque item IDs, then submits only a
hierarchy of those IDs. The existing guarded writer remains the only write path.
"""
from copy import deepcopy
from dataclasses import dataclass
import json
import time
from uuid import uuid4

from .core import COMMANDS, config_path, save_config, validate_configuration
from .recovery import (ConfigurationConflict, MAX_CONFIG_BYTES, Revision,
                       current_revision, decode_configuration)


class LayoutEditError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


@dataclass
class Session:
    config: dict
    revision: Revision
    references: dict
    touched: float


class LayoutEdits:
    MAX_SESSIONS = 4
    IDLE_SECONDS = 30 * 60

    def __init__(self, path=None, clock=time.monotonic):
        self.path = path if path is not None else config_path()
        self.clock = clock
        self.sessions = {}

    def expire(self):
        cutoff = self.clock() - self.IDLE_SECONDS
        self.sessions = {key: session for key, session in self.sessions.items() if session.touched > cutoff}

    def session(self, token):
        self.expire()
        if not isinstance(token, str) or token not in self.sessions:
            raise LayoutEditError('expired', 'The editing session expired or the backend restarted. Your draft is still visible. Cancel and unlock again to start a new session.')
        session = self.sessions[token]
        session.touched = self.clock()
        return session

    def begin(self):
        self.expire()
        if len(self.sessions) >= self.MAX_SESSIONS:
            raise LayoutEditError('busy', 'Close another layout-editing session before unlocking this menu.')
        revision = current_revision(self.path)
        config = decode_configuration(revision.content)
        references = {}

        def present(items):
            entries = []
            for item in items:
                identifier = uuid4().hex
                original = deepcopy(item)
                if item.get('separator') is True:
                    view = {'kind': 'separator', 'title': 'Separator', 'icon': 'list-remove'}
                elif 'submenu' in item:
                    view = {'kind': 'submenu', 'title': item['submenu'],
                            'icon': item.get('icon') or 'folder', 'items': present(item['items'])}
                    original.pop('items')
                else:
                    action = COMMANDS.get(item.get('action'), {})
                    view = {'kind': 'command', 'title': str(item.get('label') or action.get('title') or 'Custom command'),
                            'icon': item.get('icon') or action.get('icon') or 'system-run'}
                references[identifier] = original
                entries.append({'id': identifier, **view})
            return entries

        result = {'ok': True, 'token': uuid4().hex, 'entries': present(config['menu'])}
        if len(json.dumps(result).encode('utf-8')) > MAX_CONFIG_BYTES:
            raise LayoutEditError('too-large', 'This layout is too large for in-menu editing. Use Configure instead.')
        self.sessions[result['token']] = Session(config, revision, references, self.clock())
        return result

    def keep(self, token):
        self.session(token)
        return True

    def cancel(self, token):
        self.expire()
        return self.sessions.pop(token, None) is not None

    def save(self, token, payload):
        session = self.session(token)
        if not isinstance(payload, str) or len(payload.encode('utf-8')) > MAX_CONFIG_BYTES:
            raise LayoutEditError('too-large', 'The layout request exceeds the 4 MiB limit.')
        def unique_keys(pairs):
            if len(dict(pairs)) != len(pairs):
                raise ValueError('Repeated layout fields')
            return dict(pairs)
        try:
            proposal = json.loads(payload, object_pairs_hook=unique_keys)
        except (ValueError, RecursionError) as exc:
            raise LayoutEditError('invalid', 'The layout request is not valid JSON.') from exc
        seen = set()

        def rebuild(nodes, depth=0):
            if depth > 8 or not isinstance(nodes, list) or len(nodes) > 200:
                raise LayoutEditError('invalid', 'Keep at most eight submenu levels and 200 entries per menu.')
            result = []
            for node in nodes:
                if not isinstance(node, dict) or not isinstance(node.get('id'), str):
                    raise LayoutEditError('invalid', 'Each layout entry needs an existing item reference.')
                identifier = node['id']
                if identifier not in session.references or identifier in seen:
                    raise LayoutEditError('invalid', 'The layout contains an unknown or repeated item reference.')
                seen.add(identifier)
                original = session.references[identifier]
                submenu = 'submenu' in original and original.get('separator') is not True
                if set(node) != ({'id', 'items'} if submenu else {'id'}):
                    raise LayoutEditError('invalid', 'Rearrangement can change item positions only, not their definitions.')
                item = deepcopy(original)
                if submenu:
                    item['items'] = rebuild(node['items'], depth + 1)
                result.append(item)
            return result

        config = deepcopy(session.config)
        config['menu'] = rebuild(proposal)
        if seen != session.references.keys():
            raise LayoutEditError('invalid', 'The layout is missing entries. No items may be removed while rearranging.')
        validate_configuration(config)
        if current_revision(self.path) != session.revision:
            raise ConfigurationConflict('menu.json changed elsewhere. Your draft is retained. Cancel and unlock again to load the newer configuration.')
        changed = config['menu'] != session.config['menu']
        if changed:
            save_config(config, self.path, expected_revision=session.revision)
        del self.sessions[token]
        return {'ok': True, 'changed': changed}


def reply(operation):
    """Keep errors structured and avoid publishing executable command details."""
    try:
        return json.dumps(operation(), ensure_ascii=False)
    except ConfigurationConflict as exc:
        return json.dumps({'ok': False, 'code': 'conflict', 'message': str(exc)})
    except LayoutEditError as exc:
        return json.dumps({'ok': False, 'code': exc.code, 'message': str(exc)})
    except (OSError, ValueError):
        return json.dumps({'ok': False, 'code': 'configuration',
                           'message': 'Could not read or save the configuration safely. Check menu.json permissions, size and validity; your draft is retained.'})
