# Copyright: (c) 2026, Get-Sybers <99623331+Get-Sybers@users.noreply.github.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
name: config_merge
short_description: Fill a configuration mapping from discovered values, or overwrite it with them
version_added: "0.2.0"
description:
  - Deep-merges a mapping of I(discovered) (As-Is) values into an existing configuration mapping.
  - In the default B(fill) mode a value already present in the configuration wins and discovery only
    adds what is missing. With O(overwrite=true) the discovered value wins wherever both exist.
    Keys that exist only in the configuration (hand annotations) are kept in both modes.
  - Lists named in O(list_keys) are lists of mappings merged element-wise by the identity key given
    (so a disk list keyed by C(dev) keeps its hand-written C(role) annotations and still gains new
    disks). Every other list is treated as one value and replaced or kept whole.
  - A discovered value of C(null) means "not observed" and never fills or overwrites anything.
  - Mapping key order is preserved (configuration keys first, then new discovered keys), so the
    rendered YAML is stable run to run.
positional: discovered
options:
  _input:
    description: The configuration mapping as it is now.
    type: dict
    required: true
  discovered:
    description: The mapping of discovered values to merge in.
    type: dict
    required: true
  overwrite:
    description: When true, a discovered value replaces the configured one wherever both exist.
    type: bool
    default: false
  list_keys:
    description:
      - Map of list name to the identity key its elements are matched on.
      - A bare name (C(disks)) applies to every list carrying that name at any depth; a dotted
        path (C(ceph.pools)) applies to that list only and wins over the bare name.
    type: dict
    default: {}
author:
  - Get-Sybers (@Get-Sybers)
'''

EXAMPLES = r'''
- name: Fill the node record with what the node reports (hand values win)
  ansible.builtin.set_fact:
    __node_merged: "{{ node | get_sybers.cluster.config_merge(__discovered, list_keys={'disks': 'dev'}) }}"

- name: Replace every discovered value with the live one (annotations survive)
  ansible.builtin.set_fact:
    __node_merged: "{{ node | get_sybers.cluster.config_merge(__discovered, overwrite=true) }}"
'''

RETURN = r'''
_value:
  description: The merged mapping.
  type: dict
'''

from collections.abc import Mapping, Sequence

from ansible.errors import AnsibleFilterError
from ansible.module_utils.common.text.converters import to_native


def _is_mapping(value):
    return isinstance(value, Mapping)


def _is_list(value):
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))


def _strip_none(value):
    """Drop null values from mappings at any depth: null means "not observed"."""
    if _is_mapping(value):
        return dict((k, _strip_none(v)) for k, v in value.items() if v is not None)
    if _is_list(value):
        return [_strip_none(v) for v in value]
    return value


def _identity_for(list_keys, path, key):
    return list_keys.get(path) or list_keys.get(key)


def _merge_keyed_list(existing, discovered, identity, overwrite, list_keys, path):
    """Merge two lists of mappings element-wise on the identity key, keeping order."""
    result = []
    discovered_by_id = {}
    for item in discovered:
        if _is_mapping(item) and identity in item:
            discovered_by_id.setdefault(item[identity], item)
    seen = set()
    for item in existing:
        if _is_mapping(item) and identity in item and item[identity] in discovered_by_id:
            seen.add(item[identity])
            result.append(_merge(item, discovered_by_id[item[identity]], overwrite, list_keys, path=path))
        else:
            result.append(item)
    for item in discovered:
        if _is_mapping(item) and identity in item:
            if item[identity] not in seen:
                seen.add(item[identity])
                result.append(item)
        else:
            result.append(item)
    return result


def _merge(existing, discovered, overwrite, list_keys, key=None, path=''):
    if discovered is None:
        return existing
    if _is_mapping(existing) and _is_mapping(discovered):
        result = dict(existing)
        for sub_key, sub_value in discovered.items():
            sub_path = '%s.%s' % (path, sub_key) if path else str(sub_key)
            if sub_key not in existing:
                if sub_value is not None:
                    result[sub_key] = sub_value
            else:
                result[sub_key] = _merge(existing[sub_key], sub_value, overwrite, list_keys, sub_key, sub_path)
        return result
    identity = _identity_for(list_keys, path, key)
    if _is_list(existing) and _is_list(discovered) and identity:
        return _merge_keyed_list(existing, discovered, identity, overwrite, list_keys, path)
    return discovered if overwrite else existing


def _diff(existing, discovered, list_keys, path, out, key=None, lookup_path=''):
    """Record every discovered leaf that the configuration lacks or contradicts."""
    if discovered is None:
        return
    if _is_mapping(discovered):
        if not _is_mapping(existing):
            out.append({'path': path, 'config': existing, 'live': discovered})
            return
        for sub_key, sub_value in discovered.items():
            sub_path = '%s.%s' % (path, sub_key) if path else str(sub_key)
            sub_lookup = '%s.%s' % (lookup_path, sub_key) if lookup_path else str(sub_key)
            if sub_key not in existing:
                if sub_value is not None:
                    out.append({'path': sub_path, 'config': None, 'live': sub_value})
            else:
                _diff(existing[sub_key], sub_value, list_keys, sub_path, out, sub_key, sub_lookup)
        return
    identity = _identity_for(list_keys, lookup_path, key)
    if _is_list(discovered) and identity and _is_list(existing):
        existing_by_id = dict((item[identity], item) for item in existing if _is_mapping(item) and identity in item)
        for item in discovered:
            if _is_mapping(item) and identity in item:
                item_path = '%s[%s=%s]' % (path, identity, item[identity])
                if item[identity] in existing_by_id:
                    _diff(existing_by_id[item[identity]], item, list_keys, item_path, out, lookup_path=lookup_path)
                else:
                    out.append({'path': item_path, 'config': None, 'live': item})
        return
    if existing != discovered:
        out.append({'path': path, 'config': existing, 'live': discovered})


def _check_args(name, existing, discovered, list_keys):
    if not _is_mapping(existing):
        raise AnsibleFilterError('%s: the input must be a mapping, got %s' % (name, type(existing).__name__))
    if not _is_mapping(discovered):
        raise AnsibleFilterError('%s: discovered must be a mapping, got %s' % (name, type(discovered).__name__))
    if list_keys is None:
        return {}
    if not _is_mapping(list_keys):
        raise AnsibleFilterError('%s: list_keys must be a mapping of list name to identity key' % name)
    return dict((to_native(k), to_native(v)) for k, v in list_keys.items())


def config_merge(existing, discovered, overwrite=False, list_keys=None):
    keys = _check_args('config_merge', existing, discovered, list_keys)
    return _merge(existing, _strip_none(discovered), bool(overwrite), keys)


def config_drift(existing, discovered, list_keys=None):
    keys = _check_args('config_drift', existing, discovered, list_keys)
    out = []
    _diff(existing, _strip_none(discovered), keys, '', out)
    return out


class FilterModule(object):
    """get_sybers.cluster configuration merge filters."""

    def filters(self):
        return {
            'config_merge': config_merge,
            'config_drift': config_drift,
        }
