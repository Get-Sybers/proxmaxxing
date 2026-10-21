# Copyright: (c) 2026, Get-Sybers <99623331+Get-Sybers@users.noreply.github.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
name: to_config_yaml
short_description: Render a mapping as the block-style YAML the inventory files are written in
version_added: "0.2.0"
description:
  - Serialises a mapping as YAML in the style the repository's yamllint enforces on its inventory
    files - two-space indentation, sequences indented under their key, keys in insertion order
    (never sorted), block style throughout, unicode kept as-is - so a file the discovery role
    writes passes the same gate a hand-written one does and diffs stay minimal run to run.
  - The output has no document-start marker; the calling template adds C(---) and its banner.
options:
  _input:
    description: The mapping to render.
    type: dict
    required: true
  width:
    description: Preferred line width before a long plain scalar is folded.
    type: int
    default: 120
author:
  - Get-Sybers (@Get-Sybers)
'''

EXAMPLES = r'''
- name: Render a node record the way host_vars/<host>/node.yml is written
  ansible.builtin.copy:
    content: "---\n{{ {'node': __node_merged} | get_sybers.cluster.to_config_yaml }}"
    dest: "{{ inventory_dir }}/host_vars/{{ inventory_hostname }}/node.yml"
    mode: "0644"
'''

RETURN = r'''
_value:
  description: The rendered YAML text.
  type: str
'''

from collections.abc import Mapping, Sequence

import yaml

from ansible.errors import AnsibleFilterError


def _is_list(value):
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))


def _plain(value):
    """Reduce Ansible's tagged/trusted scalar and container types to plain Python.

    The pure-Python emitter is the only one whose indentation can be controlled
    (libyaml's C emitter ignores a Python-level increase_indent), and
    SafeDumper represents exact types only, so every str/int/float subclass
    Ansible hands us becomes its plain value first.
    """
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, Mapping):
        return dict((str(k), _plain(v)) for k, v in value.items())
    if _is_list(value):
        return [_plain(v) for v in value]
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return float(value)
    if isinstance(value, (str, bytes, bytearray)):
        return str(value) if isinstance(value, str) else value.decode('utf-8', 'replace')
    return str(value)


class _ConfigDumper(yaml.SafeDumper):
    """PyYAML's pure-Python safe dumper with sequences indented under their key.

    Deliberately not the libyaml CSafeDumper: its C emitter cannot be told to
    indent sequences, which is exactly what the inventory's yamllint demands.
    """

    def increase_indent(self, flow=False, indentless=False):
        return super(_ConfigDumper, self).increase_indent(flow, False)


def to_config_yaml(data, width=120):
    if not isinstance(data, Mapping):
        raise AnsibleFilterError('to_config_yaml: the input must be a mapping, got %s' % type(data).__name__)
    return yaml.dump(
        _plain(data),
        Dumper=_ConfigDumper,
        sort_keys=False,
        indent=2,
        width=int(width),
        default_flow_style=False,
        allow_unicode=True,
    )


class FilterModule(object):
    """get_sybers.cluster inventory rendering filter."""

    def filters(self):
        return {'to_config_yaml': to_config_yaml}
