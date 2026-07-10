"""Deprecation shim for tests/test_cluster_classifier.py.

Phase G-1: the 1075-line ``test_cluster_classifier.py`` was split into
3 themed submodules under :mod:`tests.cluster_classifier` for
navigability:

- ``tests.cluster_classifier.test_semantics`` - ClusterSemantics enum,
  opponent-gain predicate, get_semantics_label
- ``tests.cluster_classifier.test_stone_reconstruction`` -
  compute_stones_at_node, get_stones_in_cluster, StoneCache
- ``tests.cluster_classifier.test_classification`` - classify_cluster
  dispatcher, three concrete classifiers (group_death /
  territory_loss / missed_kill), confidence scoring, should_inject
  gate, mainline-resolution failure, ownership-grid orientation

The shared ``MockMove`` / ``MockGameNode`` / factory helpers live in
``tests.cluster_classifier._helpers``.

Pytest discovers the submodules automatically. This module remains
as a thin placeholder so that ``import tests.test_cluster_classifier``
(if anything ever did that) keeps resolving, and ``git log`` still
shows the refactor commit. The module intentionally exports no
symbols to avoid pytest double-collecting the moved test classes.
"""
