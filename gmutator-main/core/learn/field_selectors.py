import random
from typing import List, Dict

from sortedcontainers import SortedKeyList

import pfp.fields
from core import Feedback
from core.utils import get_ast_path, AST, likely


class FieldSelector:
    def __init__(self):
        pass

    def refresh_fields(self, candidates: List[pfp.fields.Field]):
        # prepare for a new group of fields
        pass

    def eval_fields(self) -> Dict[int, float]:
        # returns a mapping from field id to score
        pass

    def select_fields(self):
        # select fields for fuzzing
        pass

    def receive_feedback(self, changed_fields: List[pfp.fields.Field], feedback: Feedback):
        pass


class SmartFieldSelector(FieldSelector):
    class Score:
        # score wrapper
        def __init__(self):
            self.score = 0

        def __repr__(self):
            return f"score={self.score}"

    def __init__(self):
        super().__init__()
        self._tree = None
        self._cache: SortedKeyList = SortedKeyList(key=lambda x: -x[1].score)
        self._last_selected_fields = None
        self._feedback_received = True
        self._learning_count = 0 # TODO: tuning

    def refresh_fields(self, candidates: List[pfp.fields.Field]):
        if not self._feedback_received:
            raise RuntimeError("Require feedback for previously selected fields")

        for field, score in self._cache:
            if self._learning_count < 100:
                factor = 1
            elif self._learning_count < 1000:
                factor = 0.9
            elif self._learning_count < 5000:
                factor = 0.8
            elif self._learning_count < 10000:
                factor = 0.7
            else:
                factor = 0.6
            score.score *= factor # the more we learnt for this round, the more bias the scores have

        self._cache.clear()
        self._last_selected_fields = None
        self._learning_count = 0

        for candidate in candidates:
            ast_path = get_ast_path(candidate)

            if self._tree is None:
                self._tree = AST(ast_path.root())

            leaf = self._tree.get_leaf_by_path(ast_path)
            if 'score' in leaf.exts:
                score = leaf.exts['score']
            else:
                score = SmartFieldSelector.Score()
                leaf.exts['score'] = score

            self._cache.add((candidate, score))

    def eval_fields(self) -> Dict[int, float]:
        result = {}
        for field, score in self._cache:
            result[id(field)] = score.score

        return result

    def select_fields(self):
        if not self._feedback_received:
            raise RuntimeError("Require feedback for previously selected fields")

        self._last_selected_fields = {}
        num_fields = random.randint(1, 5) # TODO: tuning
        cache_size = len(self._cache)
        res = []

        for i in range(0, min(num_fields, cache_size)):
            if self._learning_count > 1000 and likely():
                field, score = self._cache.pop(index=0)
            else:
                field, score = self._cache.pop(index=random.randint(0, len(self._cache) - 1))

            self._last_selected_fields[id(field)] = score
            res.append(field)

        self._feedback_received = False
        return res

    def receive_feedback(self, changed_fields: List[pfp.fields.Field], feedback: Feedback):
        if self._feedback_received:
            # ignore duplicate feedback
            return

        fields_count = len(changed_fields)
        if fields_count > 0:
            score_update = feedback.value / fields_count
        else:
            # in certain conditions, we may have to mutate a file we couldn't parse
            score_update = 0

        for field in changed_fields:
            field_id = id(field)

            if field_id not in self._last_selected_fields:
                raise RuntimeError(f'Expected feedback for {self._last_selected_fields}, '
                                   f'but received ${changed_fields}')

            field_score = self._last_selected_fields[field_id]
            field_score.score += score_update

            self._cache.add((field, field_score))

        self._feedback_received = True
        self._learning_count += 1
