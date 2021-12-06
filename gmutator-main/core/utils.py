import random
from collections import deque, Iterator
from typing import Deque

import pfp.fields


class ASTNode(object):
    def __init__(self, name: str, ntype: str):
        self.name = name
        self.ntype = ntype
        self.exts = {}  # external resources

    def __eq__(self, other):
        if isinstance(other, ASTNode):
            return self.name == other.name and self.ntype == other.ntype
        return False

    def __hash__(self):
        return hash((self.name, self.ntype))

    def pure_copy(self):
        return ASTNode(self.name, self.ntype)


class ASTPath(object):
    # Note: notes in the path may only have `name` and `ntype`
    def __init__(self, path: Deque[ASTNode]):
        self._path = path

    def leaf(self) -> ASTNode:
        return self._path[0]

    def root(self) -> ASTNode:
        return self._path[-1]

    def b_to_t_iter(self) -> Iterator:
        return iter(self._path)

    def t_to_b_iter(self) -> Iterator:
        return reversed(self._path)

    def __str__(self):
        return '.'.join(map(lambda n: n.name, reversed(self._path)))


class AST(object):
    # for now, it's being used as a Trie, and each leaf corresponds to a field
    def __init__(self, root: ASTNode):
        self.root = root.pure_copy()
        self.height = 1
        self.n_leaves = 0

    def get_leaf_by_path(self, path: ASTPath):
        # use the path to find the corresponding leaf in this tree
        # will update this tree if any nodes missing
        if self.root != path.root():
            raise RuntimeError(f'unexpected path {path}!')

        curr = self.root
        cur_height = 1
        new_branch = False
        path_nodes = path.t_to_b_iter()

        next(path_nodes)  # ignore root
        while (next_in_path := next(path_nodes, None)) is not None:
            if 'children' not in curr.exts:
                curr.exts['children'] = {}

            children = curr.exts['children']
            if next_in_path not in children:
                new_branch = True
                pure_copy = next_in_path.pure_copy()
                children[pure_copy] = pure_copy

            curr = children[next_in_path]
            cur_height += 1

        self.height = max(self.height, cur_height)
        if new_branch:
            self.n_leaves += 1

        return curr

    @staticmethod
    def from_path(path: ASTPath):
        root = path.root()
        new_tree = AST(root.pure_copy())
        new_tree.get_leaf_by_path(path)  # merge path into tree
        return new_tree


def get_ast_path(node: pfp.fields.Field) -> ASTPath:
    curr = node
    res = deque()

    while curr is not None:
        name_src = None

        if curr._pfp__name is not None and 'None' not in curr._pfp__name:
            name_src = curr
        elif isinstance(curr._pfp__parent, pfp.fields.Array):
            name_src = curr._pfp__parent

        name = name_src._pfp__name
        if name_src._pfp__parent is not None \
                and hasattr(name_src._pfp__parent, '_pfp__name_collisions') \
                and '_' in name:
            no_suffix_name = name[:name.rindex('_')]
            if no_suffix_name in name_src._pfp__parent._pfp__name_collisions:
                # name had a suffix due to name collision
                name = no_suffix_name

        res.append(ASTNode(name, qualified_name_for_class(type(curr))))

        if isinstance(curr._pfp__parent, pfp.fields.Array):
            curr = curr._pfp__parent._pfp__parent
        else:
            curr = curr._pfp__parent

    return ASTPath(res)


def qualified_name_for_class(klass):
    return f'{klass.__module__}.{klass.__qualname__}'

def likely():
    return random.randint(1, 5) < 5  # 80%

