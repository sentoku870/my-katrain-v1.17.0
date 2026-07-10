"""Cluster-classifier test subpackage (Phase G-1).

The original ``tests/test_cluster_classifier.py`` was 1075 lines and
contained 16 test classes covering several distinct concerns. It was
split into 3 themed submodules for navigability and faster pytest
collection:

- :mod:`tests.cluster_classifier.test_semantics` - ``ClusterSemantics``
  enum, ``is_opponent_gain`` predicate, ``get_semantics_label`` i18n
  (~120 lines, 3 classes)
- :mod:`tests.cluster_classifier.test_stone_reconstruction` -
  ``compute_stones_at_node``, ``get_stones_in_cluster``, ``StoneCache``
  (~330 lines, 3 classes)
- :mod:`tests.cluster_classifier.test_classification` - the
  ``classify_cluster`` dispatcher, three concrete classifiers
  (group_death / territory_loss / missed_kill), confidence scoring,
  should_inject gate, mainline-resolution failure, ownership-grid
  orientation (~530 lines, 10 classes)

The shared ``MockMove`` / ``MockGameNode`` / factory helpers live in
:mod:`tests.cluster_classifier._helpers`.

Pytest discovers all test classes in the submodules automatically;
the parent ``tests/test_cluster_classifier.py`` file is kept as a
thin deprecation shim that does not define any test classes.
"""
