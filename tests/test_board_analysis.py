"""
test_board_analysis.py - board_analysis モジュールのテスト

テスト対象:
- Group dataclass
- BoardState dataclass
- compute_danger_scores (pure function)
- get_reason_tags_for_move (quasi-pure, needs minimal mocks)

Note: extract_groups_from_game, find_connect_points, find_cut_points,
      analyze_board_at_node は Game 依存が強いため、統合テストで扱う。
"""

import pytest
from dataclasses import FrozenInstanceError
from katrain.core.board_analysis import (
    Group,
    BoardState,
    compute_danger_scores,
    get_reason_tags_for_move,
)


# ==================== Fixtures ====================

@pytest.fixture
def simple_group():
    """基本的なグループ（3呼吸点）"""
    return Group(
        group_id=0,
        color='B',
        stones=[(3, 3), (3, 4)],
        liberties_count=3,
        liberties={(2, 3), (4, 3), (3, 5)},
        is_in_atari=False,
        is_low_liberty=False,
        adjacent_enemy_groups=[1]
    )


@pytest.fixture
def atari_group():
    """アタリ状態のグループ（1呼吸点）"""
    return Group(
        group_id=1,
        color='B',
        stones=[(5, 5)],
        liberties_count=1,
        liberties={(5, 6)},
        is_in_atari=True,
        is_low_liberty=True,
        adjacent_enemy_groups=[2]
    )


@pytest.fixture
def low_liberty_group():
    """2呼吸点のグループ"""
    return Group(
        group_id=2,
        color='W',
        stones=[(10, 10), (10, 11)],
        liberties_count=2,
        liberties={(9, 10), (11, 10)},
        is_in_atari=False,
        is_low_liberty=True,
        adjacent_enemy_groups=[0]
    )


@pytest.fixture
def large_group():
    """大きなグループ（10石以上）"""
    stones = [(i, 5) for i in range(10)]
    return Group(
        group_id=3,
        color='B',
        stones=stones,
        liberties_count=4,
        liberties={(0, 4), (9, 6), (0, 6), (9, 4)},
        is_in_atari=False,
        is_low_liberty=False,
        adjacent_enemy_groups=[]
    )


@pytest.fixture
def medium_group():
    """中程度のグループ（6-9石）"""
    stones = [(i, 8) for i in range(7)]
    return Group(
        group_id=4,
        color='W',
        stones=stones,
        liberties_count=5,
        liberties={(0, 7), (6, 9), (0, 9), (6, 7), (3, 7)},
        is_in_atari=False,
        is_low_liberty=False,
        adjacent_enemy_groups=[]
    )


# ==================== Group Dataclass Tests ====================

class TestGroup:
    """Group dataclass のテスト"""

    def test_group_creation(self, simple_group):
        """基本的なグループ作成"""
        assert simple_group.group_id == 0
        assert simple_group.color == 'B'
        assert len(simple_group.stones) == 2
        assert simple_group.liberties_count == 3
        assert not simple_group.is_in_atari
        assert not simple_group.is_low_liberty

    def test_atari_group_flags(self, atari_group):
        """アタリグループのフラグ"""
        assert atari_group.is_in_atari is True
        assert atari_group.is_low_liberty is True
        assert atari_group.liberties_count == 1

    def test_low_liberty_not_atari(self, low_liberty_group):
        """2呼吸点は low_liberty だが atari ではない"""
        assert low_liberty_group.is_low_liberty is True
        assert low_liberty_group.is_in_atari is False
        assert low_liberty_group.liberties_count == 2


# ==================== BoardState Dataclass Tests ====================

class TestBoardState:
    """BoardState dataclass のテスト"""

    def test_board_state_creation(self, simple_group, atari_group):
        """BoardState の基本作成"""
        groups = [simple_group, atari_group]
        connect_points = [((4, 4), [0, 1], 15.0)]
        cut_points = [((6, 6), [0, 1], 20.0)]
        danger_scores = {0: 15.0, 1: 60.0}

        state = BoardState(
            groups=groups,
            connect_points=connect_points,
            cut_points=cut_points,
            danger_scores=danger_scores
        )

        assert len(state.groups) == 2
        assert len(state.connect_points) == 1
        assert len(state.cut_points) == 1
        assert state.danger_scores[1] == 60.0

    def test_empty_board_state(self):
        """空の盤面状態"""
        state = BoardState(
            groups=[],
            connect_points=[],
            cut_points=[],
            danger_scores={}
        )

        assert len(state.groups) == 0
        assert len(state.danger_scores) == 0


# ==================== compute_danger_scores Tests ====================

class TestComputeDangerScores:
    """compute_danger_scores のテスト（pure function）"""

    def test_atari_group_danger_60(self, atari_group):
        """アタリグループの基本危険度は60"""
        cut_points = []
        scores = compute_danger_scores([atari_group], cut_points)
        assert scores[atari_group.group_id] == 60.0

    def test_low_liberty_danger_35(self, low_liberty_group):
        """2呼吸点グループの基本危険度は35"""
        cut_points = []
        scores = compute_danger_scores([low_liberty_group], cut_points)
        assert scores[low_liberty_group.group_id] == 35.0

    def test_three_liberties_danger_15(self, simple_group):
        """3呼吸点グループの基本危険度は15"""
        cut_points = []
        scores = compute_danger_scores([simple_group], cut_points)
        assert scores[simple_group.group_id] == 15.0

    def test_four_plus_liberties_danger_0_base(self):
        """4呼吸点以上のグループの基本危険度は0"""
        group = Group(
            group_id=0,
            color='B',
            stones=[(5, 5)],
            liberties_count=4,
            liberties={(4, 5), (6, 5), (5, 4), (5, 6)},
            is_in_atari=False,
            is_low_liberty=False,
            adjacent_enemy_groups=[]
        )
        cut_points = []
        scores = compute_danger_scores([group], cut_points)
        assert scores[0] == 0.0

    def test_nearby_cuts_add_danger(self, simple_group):
        """切断点が近くにあると危険度が上昇"""
        # simple_group は group_id=0
        cut_points = [
            ((4, 4), [0, 1], 20.0),  # group 0 が含まれる
            ((5, 5), [0, 2], 15.0),  # group 0 が含まれる
        ]
        scores = compute_danger_scores([simple_group], cut_points)
        # 基本15 + 切断点ボーナス (2 * 5 = 10)
        assert scores[simple_group.group_id] == 25.0

    def test_cut_bonus_capped_at_20(self, simple_group):
        """切断点ボーナスは最大20"""
        # 5つの切断点を追加
        cut_points = [
            ((4, 4), [0], 20.0),
            ((5, 5), [0], 20.0),
            ((6, 6), [0], 20.0),
            ((7, 7), [0], 20.0),
            ((8, 8), [0], 20.0),
        ]
        scores = compute_danger_scores([simple_group], cut_points)
        # 基本15 + 切断点ボーナス (min(20, 5*5) = 20)
        assert scores[simple_group.group_id] == 35.0

    def test_large_group_bonus(self, large_group):
        """10石以上のグループはボーナス+10"""
        cut_points = []
        scores = compute_danger_scores([large_group], cut_points)
        # 4呼吸点で基本0 + 大石ボーナス10
        assert scores[large_group.group_id] == 10.0

    def test_medium_group_bonus(self, medium_group):
        """6-9石のグループはボーナス+5"""
        cut_points = []
        scores = compute_danger_scores([medium_group], cut_points)
        # 5呼吸点で基本0 + 中石ボーナス5
        assert scores[medium_group.group_id] == 5.0

    def test_combined_danger_calculation(self, atari_group):
        """複合的な危険度計算"""
        # アタリ + 1切断点 + 1石（小石）
        cut_points = [((5, 6), [atari_group.group_id], 30.0)]
        scores = compute_danger_scores([atari_group], cut_points)
        # 基本60 + 切断点ボーナス5 + 小石ボーナス0
        assert scores[atari_group.group_id] == 65.0

    def test_empty_groups_list(self):
        """空のグループリスト"""
        scores = compute_danger_scores([], [])
        assert scores == {}

    def test_multiple_groups(self, simple_group, atari_group, low_liberty_group):
        """複数グループの危険度計算"""
        groups = [simple_group, atari_group, low_liberty_group]
        cut_points = []
        scores = compute_danger_scores(groups, cut_points)

        assert len(scores) == 3
        assert scores[simple_group.group_id] == 15.0
        assert scores[atari_group.group_id] == 60.0
        assert scores[low_liberty_group.group_id] == 35.0


# ==================== Invariant Tests ====================

class TestInvariants:
    """プロパティベースのテスト（数値に依存しない）"""

    def test_danger_scores_non_negative(
        self, simple_group, atari_group, low_liberty_group, large_group
    ):
        """危険度スコアは常に非負"""
        groups = [simple_group, atari_group, low_liberty_group, large_group]
        cut_points = []
        scores = compute_danger_scores(groups, cut_points)

        for score in scores.values():
            assert score >= 0

    def test_all_groups_have_danger_score(
        self, simple_group, atari_group, low_liberty_group
    ):
        """すべてのグループに危険度スコアが割り当てられる"""
        groups = [simple_group, atari_group, low_liberty_group]
        cut_points = []
        scores = compute_danger_scores(groups, cut_points)

        for group in groups:
            assert group.group_id in scores

    def test_atari_always_more_dangerous_than_non_atari(self):
        """アタリグループは常に非アタリより危険"""
        atari = Group(
            group_id=0, color='B', stones=[(5, 5)],
            liberties_count=1, liberties={(5, 6)},
            is_in_atari=True, is_low_liberty=True,
            adjacent_enemy_groups=[]
        )
        non_atari = Group(
            group_id=1, color='B', stones=[(10, 10)],
            liberties_count=4, liberties={(9, 10), (11, 10), (10, 9), (10, 11)},
            is_in_atari=False, is_low_liberty=False,
            adjacent_enemy_groups=[]
        )
        scores = compute_danger_scores([atari, non_atari], [])
        assert scores[0] > scores[1]


# ==================== get_reason_tags_for_move Tests ====================

class TestGetReasonTags:
    """get_reason_tags_for_move のテスト"""

    class MockMoveEval:
        """MoveEval のモック"""
        def __init__(
            self,
            player='B',
            move_number=50,
            points_lost=None,
            tag=None
        ):
            self.player = player
            self.move_number = move_number
            self.points_lost = points_lost
            self.tag = tag

    class MockNode:
        """GameNode のモック"""
        class MockMove:
            def __init__(self, coords):
                self.coords = coords

        def __init__(self, coords=None):
            self.move = self.MockMove(coords) if coords else None

    def test_empty_groups_returns_empty_tags(self):
        """グループがない場合は空のタグ"""
        board_state = BoardState(
            groups=[],
            connect_points=[],
            cut_points=[],
            danger_scores={}
        )
        move_eval = self.MockMoveEval()
        node = self.MockNode()

        tags = get_reason_tags_for_move(board_state, move_eval, node, [])
        assert tags == []

    def test_no_player_returns_empty_tags(self, simple_group):
        """プレイヤーがない場合は空のタグ"""
        board_state = BoardState(
            groups=[simple_group],
            connect_points=[],
            cut_points=[],
            danger_scores={0: 15.0}
        )
        move_eval = self.MockMoveEval(player=None)
        node = self.MockNode()

        tags = get_reason_tags_for_move(board_state, move_eval, node, [])
        assert tags == []

    def test_atari_tag_emitted(self, atari_group):
        """アタリ状態でatariタグが発行される"""
        board_state = BoardState(
            groups=[atari_group],
            connect_points=[],
            cut_points=[],
            danger_scores={atari_group.group_id: 60.0}
        )
        move_eval = self.MockMoveEval(player='B')
        # 着手がアタリグループの近く（3マス以内）
        node = self.MockNode(coords=(5, 5))

        tags = get_reason_tags_for_move(board_state, move_eval, node, [])
        assert "atari" in tags

    def test_low_liberties_tag_without_atari(self, low_liberty_group):
        """low_liberty かつ非アタリで low_liberties タグ"""
        board_state = BoardState(
            groups=[low_liberty_group],
            connect_points=[],
            cut_points=[],
            danger_scores={low_liberty_group.group_id: 35.0}
        )
        move_eval = self.MockMoveEval(player='W')
        node = self.MockNode()

        tags = get_reason_tags_for_move(board_state, move_eval, node, [])
        assert "low_liberties" in tags

    def test_chase_mode_conditions(self, atari_group, simple_group):
        """追撃モード: 敵が危険で自分が安全"""
        # atari_group を敵（W）に、simple_group を味方（B）に
        enemy_atari = Group(
            group_id=10,
            color='W',
            stones=[(15, 15)],
            liberties_count=1,
            liberties={(15, 16)},
            is_in_atari=True,
            is_low_liberty=True,
            adjacent_enemy_groups=[0]
        )
        board_state = BoardState(
            groups=[simple_group, enemy_atari],
            connect_points=[],
            cut_points=[],
            danger_scores={simple_group.group_id: 15.0, enemy_atari.group_id: 60.0}
        )
        move_eval = self.MockMoveEval(player='B')
        node = self.MockNode()

        tags = get_reason_tags_for_move(board_state, move_eval, node, [])
        assert "chase_mode" in tags

    def test_endgame_hint_after_move_150(self, simple_group):
        """150手以降でendgame_hintタグ"""
        board_state = BoardState(
            groups=[simple_group],
            connect_points=[],
            cut_points=[],
            danger_scores={simple_group.group_id: 15.0}
        )
        move_eval = self.MockMoveEval(player='B', move_number=160)
        node = self.MockNode()

        tags = get_reason_tags_for_move(board_state, move_eval, node, [])
        assert "endgame_hint" in tags

    def test_endgame_hint_with_yose_tag(self, simple_group):
        """yoseタグでendgame_hintタグ"""
        board_state = BoardState(
            groups=[simple_group],
            connect_points=[],
            cut_points=[],
            danger_scores={simple_group.group_id: 15.0}
        )
        move_eval = self.MockMoveEval(player='B', move_number=50, tag="yose")
        node = self.MockNode()

        tags = get_reason_tags_for_move(board_state, move_eval, node, [])
        assert "endgame_hint" in tags

    def test_need_connect_with_high_improvement(self, simple_group):
        """連絡点の改善値が高い場合 need_connect タグ"""
        connect_points = [((4, 4), [0, 1], 25.0)]  # 改善値20以上
        board_state = BoardState(
            groups=[simple_group],
            connect_points=connect_points,
            cut_points=[],
            danger_scores={simple_group.group_id: 15.0}
        )
        move_eval = self.MockMoveEval(player='B')
        node = self.MockNode()

        tags = get_reason_tags_for_move(board_state, move_eval, node, [])
        assert "need_connect" in tags

    def test_no_need_connect_with_low_improvement(self, simple_group):
        """連絡点の改善値が低い場合 need_connect タグなし"""
        connect_points = [((4, 4), [0, 1], 15.0)]  # 改善値20未満
        board_state = BoardState(
            groups=[simple_group],
            connect_points=connect_points,
            cut_points=[],
            danger_scores={simple_group.group_id: 15.0}
        )
        move_eval = self.MockMoveEval(player='B')
        node = self.MockNode()

        tags = get_reason_tags_for_move(board_state, move_eval, node, [])
        assert "need_connect" not in tags


# ==================== Threshold Consistency Tests ====================

class TestThresholdConsistency:
    """閾値の一貫性テスト"""

    def test_liberty_danger_ordering(self):
        """呼吸点数に応じた危険度順序"""
        lib1 = Group(
            group_id=0, color='B', stones=[(5, 5)],
            liberties_count=1, liberties={(5, 6)},
            is_in_atari=True, is_low_liberty=True,
            adjacent_enemy_groups=[]
        )
        lib2 = Group(
            group_id=1, color='B', stones=[(10, 10)],
            liberties_count=2, liberties={(9, 10), (11, 10)},
            is_in_atari=False, is_low_liberty=True,
            adjacent_enemy_groups=[]
        )
        lib3 = Group(
            group_id=2, color='B', stones=[(15, 15)],
            liberties_count=3, liberties={(14, 15), (16, 15), (15, 14)},
            is_in_atari=False, is_low_liberty=False,
            adjacent_enemy_groups=[]
        )
        lib4 = Group(
            group_id=3, color='B', stones=[(3, 3)],
            liberties_count=4, liberties={(2, 3), (4, 3), (3, 2), (3, 4)},
            is_in_atari=False, is_low_liberty=False,
            adjacent_enemy_groups=[]
        )

        scores = compute_danger_scores([lib1, lib2, lib3, lib4], [])

        # 呼吸点が少ないほど危険
        assert scores[0] > scores[1] > scores[2] > scores[3]
