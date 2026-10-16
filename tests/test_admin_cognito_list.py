"""Tests for the admin Cognito user listing call pattern.

The listing must resolve group membership with a constant number of proxy
hops (one ``list_users`` plus one ``list_users_in_group`` per managed
group) rather than one ``admin_list_groups_for_user`` per user.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.api import admin_cognito
from app.api import admin_cognito_groups
from app.services.aws_proxy import AwsProxyError


def _user(username: str, sub: str) -> dict[str, Any]:
    return {
        'Username': username,
        'UserStatus': 'CONFIRMED',
        'Enabled': True,
        'Attributes': [
            {'Name': 'sub', 'Value': sub},
            {'Name': 'email', 'Value': f'{username}@example.com'},
        ],
    }


def _event(**query: str) -> dict[str, Any]:
    return {
        'httpMethod': 'GET',
        'path': '/v1/admin/cognito-users',
        'queryStringParameters': query or None,
        'headers': {},
        'requestContext': {'requestId': 'req-1', 'authorizer': {}},
    }


@pytest.fixture(autouse=True)
def _cognito_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('COGNITO_USER_POOL_ID', 'pool-1')
    monkeypatch.delenv('ADMIN_GROUP', raising=False)
    monkeypatch.delenv('MANAGER_GROUP', raising=False)


def _patch_proxy(monkeypatch: pytest.MonkeyPatch, responder) -> list[tuple]:
    calls: list[tuple[str, dict[str, Any]]] = []

    def fake_proxy(service: str, action: str, params: dict) -> dict:
        assert service == 'cognito-idp'
        calls.append((action, params))
        return responder(action, params)

    monkeypatch.setattr(admin_cognito, 'aws_proxy', fake_proxy)
    return calls


def test_list_users_uses_constant_number_of_proxy_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    users = [_user(f'user{i}', f'{i:08d}-0000-0000-0000-000000000000') for i in range(6)]

    def responder(action: str, params: dict) -> dict:
        if action == 'list_users':
            return {'Users': users}
        if action == 'list_users_in_group':
            if params['GroupName'] == 'admin':
                return {'Users': [users[0]]}
            return {'Users': [users[0], users[3]]}
        raise AssertionError(f'unexpected action {action}')

    calls = _patch_proxy(monkeypatch, responder)

    response = admin_cognito._handle_list_cognito_users(_event())

    actions = [action for action, _ in calls]
    assert actions == ['list_users', 'list_users_in_group', 'list_users_in_group']
    assert 'admin_list_groups_for_user' not in actions
    assert 'admin_get_user' not in actions

    body = json.loads(response['body'])
    groups = {item['username']: item['groups'] for item in body['items']}
    assert groups['user0'] == ['admin', 'manager']
    assert groups['user3'] == ['manager']
    assert groups['user1'] == []
    assert 'managed_organizations' not in body['items'][0]
    assert response['statusCode'] == 200


def test_group_listing_follows_pagination(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def responder(action: str, params: dict) -> dict:
        if action == 'list_users':
            return {'Users': [_user('a', 'aaaaaaaa-0000-0000-0000-000000000000')]}
        if params['GroupName'] == 'manager':
            return {'Users': []}
        if 'NextToken' not in params:
            return {'Users': [_user('a', 'x')], 'NextToken': 'page-2'}
        assert params['NextToken'] == 'page-2'
        return {'Users': []}

    calls = _patch_proxy(monkeypatch, responder)

    response = admin_cognito._handle_list_cognito_users(_event())

    admin_calls = [
        params
        for action, params in calls
        if action == 'list_users_in_group' and params['GroupName'] == 'admin'
    ]
    assert len(admin_calls) == 2
    assert all(
        p['Limit'] == admin_cognito_groups.GROUP_MEMBERS_PAGE_SIZE for p in admin_calls
    )
    body = json.loads(response['body'])
    assert body['items'][0]['groups'] == ['admin']


def test_group_lookup_failure_degrades_to_empty_groups(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def responder(action: str, params: dict) -> dict:
        if action == 'list_users':
            return {'Users': [_user('a', 'aaaaaaaa-0000-0000-0000-000000000000')]}
        if params['GroupName'] == 'admin':
            raise AwsProxyError('TooManyRequestsException', 'slow down')
        return {'Users': [_user('a', 'x')]}

    _patch_proxy(monkeypatch, responder)

    response = admin_cognito._handle_list_cognito_users(_event())

    body = json.loads(response['body'])
    assert response['statusCode'] == 200
    assert body['items'][0]['groups'] == ['manager']


def test_managed_group_names_respect_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('ADMIN_GROUP', 'ops')
    monkeypatch.setenv('MANAGER_GROUP', 'ops')
    assert admin_cognito_groups._managed_group_names() == ['ops']

def test_include_managed_organizations_attaches_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager_sub = 'aaaaaaaa-0000-0000-0000-000000000001'
    other_sub = 'bbbbbbbb-0000-0000-0000-000000000002'
    looked_up: list[list[str]] = []

    def responder(action: str, params: dict) -> dict:
        if action == 'list_users':
            return {
                'Users': [_user('manager', manager_sub), _user('plain', other_sub)]
            }
        return {'Users': []}

    def lookup(subs: list[str]) -> dict[str, list[dict[str, str]]]:
        looked_up.append(subs)
        return {
            manager_sub: [
                {
                    'id': '00000000-0000-0000-0000-000000000010',
                    'name': 'Alpha Club',
                }
            ]
        }

    _patch_proxy(monkeypatch, responder)
    monkeypatch.setattr(admin_cognito, '_managed_organizations_by_sub', lookup)

    response = admin_cognito._handle_list_cognito_users(
        _event(include='managed_organizations')
    )

    assert looked_up == [[manager_sub, other_sub]]
    body = json.loads(response['body'])
    by_username = {item['username']: item for item in body['items']}
    assert by_username['manager']['managed_organizations'] == [
        {'id': '00000000-0000-0000-0000-000000000010', 'name': 'Alpha Club'}
    ]
    assert by_username['plain']['managed_organizations'] == []
    assert response['statusCode'] == 200


def test_invalid_include_is_rejected() -> None:
    with pytest.raises(admin_cognito.ValidationError):
        admin_cognito._handle_list_cognito_users(_event(include='groups'))


def test_managed_organizations_by_sub_reads_repository(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, Any] = {}

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, *_args: object) -> bool:
            return False

    class FakeRepo:
        def __init__(self, session: FakeSession) -> None:
            seen['session'] = session

        def list_managed_for_subs(self, subs: list[str]) -> dict[str, list]:
            seen['subs'] = subs
            return {'sub-1': [{'id': 'id-1', 'name': 'Club'}]}

    monkeypatch.setattr(admin_cognito, 'Session', lambda _engine: FakeSession())
    monkeypatch.setattr(admin_cognito, 'get_engine', lambda: object())
    monkeypatch.setattr(admin_cognito, 'OrganizationRepository', FakeRepo)

    result = admin_cognito._managed_organizations_by_sub(['sub-1'])

    assert result == {'sub-1': [{'id': 'id-1', 'name': 'Club'}]}
    assert seen['subs'] == ['sub-1']


def test_managed_organizations_by_sub_skips_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom() -> object:
        raise AssertionError('engine should not open')

    monkeypatch.setattr(admin_cognito, 'get_engine', boom)
    assert admin_cognito._managed_organizations_by_sub([]) == {}
