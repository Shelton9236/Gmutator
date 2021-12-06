import concurrent.futures
import importlib
import io
import os
import random
import secrets
from collections import deque
from typing import Union

import pfp
import pfp.fields
from core import Feedback, FORMAT
from core.learn.field_selectors import FieldSelector, SmartFieldSelector
from core.utils import qualified_name_for_class
from pfp.fuzz.basic import BasicStrat


class CoreMutator:
    def __init__(self, template_path: str, for_format: FORMAT, field_selector: FieldSelector):
        # helpers
        self._interp = pfp.create_interp(template_path)
        self._field_selector = field_selector
        self._sample_provider = RandomStructProvider(template_path, for_format)
        self._trim_helper = TrimHelper(self._interp)

        # mutation-related data
        self._strat = BasicStrat()
        self._current_data = None
        self._current_dom = None
        self._current_structs = None
        self._last_mutation = None
        self._last_mutated_fields = None
        self._feedback_received = True
        self._mutatable_fields = None
        self._field_id_to_strat = None

    @property
    def feedback_received(self):
        return self._feedback_received

    # @property
    # def trim_helper(self):
    #     return self._trim_helper

    # TODO: 2. integrate ML-based generator
    def eval_input(self, filename: str) -> bool:
        if not self._feedback_received:
            self.receive_feedback(Feedback.BORING)

        with open(filename, 'rb') as f:
            raw_data = bytearray(f.read())
        self._reset(raw_data)

        if len(self._mutatable_fields) < 10:
            # either the file is too small or parser cannot parse it
            return False

        scores = self._field_selector.eval_fields()
        for id, score in scores.items():
            if score > -100:  # TODO: tuning
                return True

        return False

    def get_mutation(self, data: bytearray) -> bytearray:
        if self._current_data != data:
            self._reset(data)

        res, self._last_mutated_fields = self._internal_mutate()  # TODO: analyze fields, avoid repetition
        self._last_mutation = res
        self._feedback_received = False
        return res

    def get_havoc_mutation(self, data: bytearray) -> bytearray:
        if len(self._current_structs) == 0:
            return self._get_havoc_mutation_fallback(data)
        selected_struct, offset, size = random.choice(self._current_structs)

        if self._sample_provider.ready() and random.getrandbits(1) == 1:
            if random.getrandbits(1) == 1:
                # get random struct of same type
                random_struct = self._sample_provider.get_random_struct_for_type(type(selected_struct))

                # TODO: need to evaluate this and trim
                # if random_struct is not None and isinstance(selected_struct._pfp__parent, pfp.fields.Array):
                #     # the parent of this struct is an array, try expanding it
                #     if random.getrandbits(1) == 1:
                #         seoncd_random_struct = self._sample_provider.get_random_struct_for_type(type(selected_struct))
                #         if seoncd_random_struct is not None:
                #             random_struct += seoncd_random_struct

            else:
                # get random struct of random type
                random_struct = self._sample_provider.get_random_struct()

            if random_struct is not None:
                return self._current_data[:offset] + bytearray(random_struct) + self._current_data[offset + size:]

        # replace struct with random bytes
        random_bytes = secrets.token_bytes(size)
        return self._current_data[:offset] + bytearray(random_bytes) + self._current_data[offset + size:]

    def _get_havoc_mutation_fallback(self, data: bytearray) -> bytearray:
        if self._sample_provider.ready():
            # try to use a different dom
            new_data = self._sample_provider.get_random_struct_for_type(pfp.fields.Dom)
            new_data = bytearray(new_data)
            if new_data is not None:
                if not self.feedback_received:
                    self.receive_feedback(Feedback.BORING)
                self._reset(new_data)

                if len(self._current_structs) > 0:
                    return self.get_havoc_mutation(data)

        # worst case: randomly mutate 4 bytes
        random_offset = random.randint(0, len(data))
        return data[:random_offset] + secrets.token_bytes(4) + data[random_offset+4:]


    def _reset(self, data: bytearray):
        self._current_data = data
        with io.BytesIO(data) as data_stream:
            self._current_dom = self._interp.parse(data_stream, keep_successful=True)
        self._current_structs = []
        self._last_mutation = None
        self._last_mutated_fields = None
        self._mutatable_fields, self._field_id_to_strat = self._build_fields_with_strats(self._current_dom, self._strat)
        self._field_selector.refresh_fields(self._mutatable_fields)

        # re-generate data to track struct sizes (check _pfp__bytes_written)
        self._current_dom._pfp__build(save_offset=True)
        self._current_structs = RandomStructProvider.get_all_structs_with_details(self._current_dom)

    def _internal_mutate(self):
        # save the current value of all subfields without
        # triggering events
        # dom._pfp__snapshot(recurse=True)
        chosen_fields = []
        try:
            chosen_fields = self._field_selector.select_fields()
            for field in chosen_fields:
                field._pfp__snapshot(recurse=False)  # assuming no watchers...
                field_strat = self._field_id_to_strat[id(field)]
                field_strat.mutate(field)

            return bytearray(self._current_dom._pfp__build(save_offset=False)), chosen_fields

        finally:
            # restore the saved value of all subfields without
            # triggering events
            # dom._pfp__restore_snapshot(recurse=True)
            for field in chosen_fields:
                field._pfp__restore_snapshot(recurse=False)  # assuming no watchers...

    def receive_feedback(self, feedback: Feedback, new_seed=None):
        if new_seed is not None and self._last_mutation != new_seed:
            raise RuntimeError("Invalid state: feedback doesn't match with last mutation")

        self._field_selector.receive_feedback(self._last_mutated_fields, feedback)
        self._feedback_received = True

    def deinit(self):
        self._sample_provider.deinit()

    @staticmethod
    def _build_fields_with_strats(dom: pfp.fields.Dom, strat):
        to_mutate = strat.which(dom)

        # don't use dict to avoid comparing fields
        with_strats_fields = []
        strats = {}
        for to_mutate_field in to_mutate:
            field_strat = strat.get_field_strat(to_mutate_field)
            if field_strat is not None:
                with_strats_fields.append(to_mutate_field)
                strats[id(to_mutate_field)] = field_strat

        return with_strats_fields, strats


class TrimHelper(object):
    def __init__(self, interp: pfp.interp.PfpInterp):
        self._interp = interp
        self._current_data = None
        self._current_structs = None
        self._current_idx = 0

    def init_trim(self, buf: bytearray):
        dom = self._interp.parse(buf, keep_successful=True)

        # re-generate data to track struct sizes (check _pfp__bytes_written)
        dom._pfp__build(save_offset=True)
        self._current_data = buf
        self._current_structs = RandomStructProvider.get_all_structs_with_details(dom)
        self._current_idx = 0

        # for struct, offset, size in RandomStructProvider.get_all_structs_with_details(dom):
        #     if isinstance(struct._pfp__parent, pfp.fields.Array):
        #         # maybe we can remove this struct from array
        #         self._current_structs.append((struct, offset, size))

        return len(self._current_structs)

    def trim(self) -> bytearray:
        # try removing current struct
        struct, offset, size = self._current_structs[self._current_idx]
        return self._current_data[:offset] + self._current_data[offset + size:]

    def post_trim(self, success):
        self._current_idx += 1
        return self._current_idx


# def process_init():
#     os.nice(19)

class RandomStructProvider(object):
    CACHE_SIZE = 1000

    def __init__(self, template_path: str, for_format: FORMAT):
        self._template_path = template_path
        self._format = for_format
        self._sample_data = {}
        self._struct_samples = {}
        self._future = None
        self._failed_count = 0  # num of failures in get_random_struct
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        # self._executor = concurrent.futures.ProcessPoolExecutor(max_workers=1, initializer=process_init)

        self._maybe_generate_new_samples()

    def deinit(self):
        self._executor.shutdown(wait=False)

    def ready(self):
        if self._future is not None and self._future.done():
            if self._future.exception() is None:
                self._sample_data, self._struct_samples = self._future.result()
                self._failed_count = 0
            self._future = None

        return len(self._sample_data) > 0 and len(self._struct_samples) > 0

    def get_random_struct(self):
        t = None
        samples = None

        for key, value in self._struct_samples.items():
            if samples is None or len(value) > len(samples):
                t = key
                samples = value

        if t is None:
            return None
        return self.get_random_struct_for_type(t)

    def get_random_struct_for_type(self, struct_type: Union[type, str]):
        if not self.ready():
            self._maybe_generate_new_samples()
            return None

        if struct_type == pfp.fields.Dom:
            root_id, data = self._sample_data.popitem()
            return data

        t = struct_type if isinstance(struct_type, str) else qualified_name_for_class(struct_type)
        if t in self._struct_samples:
            samples = self._struct_samples[t]

            while len(samples) > 0:
                s: StructSample = samples.pop()
                if s.root_id in self._sample_data:
                    data = self._sample_data[s.root_id]
                    start = s.offset
                    end = s.offset + s.size

                    if end < len(data):
                        return data[start:end]

            if len(samples) == 0:
                del self._struct_samples[t]

        # fail to find any data for this type
        if isinstance(struct_type, type) and issubclass(struct_type, pfp.fields.Struct):
            self._failed_count += 1

            if self._failed_count > RandomStructProvider.CACHE_SIZE:
                # too many fails
                self._maybe_generate_new_samples()

        return None

    def _maybe_generate_new_samples(self):
        if self._future is None:
            self._future = self._executor.submit(RandomStructProvider._fetch_samples,
                                                 self._template_path, self._format, self.CACHE_SIZE)

    @staticmethod
    def _fetch_samples(template_path: str, for_format: FORMAT, n: int):
        # record_event(subthread="this thread has pid %s" % os.getpid())
        # NOTE: this function is extremely slow, should run in a separate process/thread!

        # create an interp for this process/thread
        global rsp_interp
        if 'rsp_interp' not in globals():
            rsp_interp = pfp.create_interp(template_path)

        pyff = importlib.import_module(f'core.formatfuzzer.wrappers.pyff_{for_format.value}')

        data = {}  # root id to raw data in bytes
        struct_samples = {}  # struct type to struct samples
        for i in range(0, n):
            generated_data = pyff.generate_random()
            with io.BytesIO(generated_data) as data_stream:
                dom = rsp_interp.parse(data_stream, keep_successful=True)

            # re-generate data to track struct sizes (check _pfp__bytes_written)
            generated_data = dom._pfp__build(save_offset=True)
            root_id = id(generated_data)

            data[root_id] = generated_data
            structs = RandomStructProvider.get_all_structs(dom)
            for struct in structs:
                RandomStructProvider._fetch_samples_for_struct(struct, root_id, struct_samples)

        # shuffle results
        for samples in struct_samples.values():
            random.shuffle(samples)

        return data, struct_samples

    @staticmethod
    def get_all_structs_with_details(dom: pfp.fields.Dom):
        res = []
        structs = RandomStructProvider.get_all_structs(dom)
        for struct in structs:
            struct_size = struct._pfp__bytes_written
            if struct_size <= 0:
                continue

            res.append((struct, struct._pfp__offset, struct_size))

        return res

    @staticmethod
    def get_all_structs(dom: pfp.fields.Dom):
        # BFS to find all structs in dom
        structs = []
        fields = deque()
        fields.append(dom)

        while len(fields) > 0:
            field = fields.pop()

            if (
                    not isinstance(field, (pfp.fields.Struct, pfp.fields.Array))
                    and field._ is None
            ):
                # this is a leaf
                continue

            if (
                    isinstance(field, pfp.fields.Struct)  # it's a struct
                    and not isinstance(field, pfp.fields.Dom)  # but not the root
            ):
                structs.append(field)

            # packed fields need to be checked first!
            if field._ is not None:
                fields.extend(field._._pfp__children)

            elif isinstance(field, pfp.fields.Struct):
                fields.extend(field._pfp__children)

            elif isinstance(field, pfp.fields.Array) and field.raw_data is None:
                fields.extend(field.items)

        return structs

    @staticmethod
    def _fetch_samples_for_struct(field: pfp.fields.Struct, root_id, struct_samples):
        # requires field._pfp__bytes_written
        field_size = field._pfp__bytes_written
        if field_size > 0:
            t = qualified_name_for_class(type(field))
            if t not in struct_samples:
                struct_samples[t] = []

            samples_for_type = struct_samples[t]
            samples_for_type.append(
                StructSample(root_id, field._pfp__offset, field_size)
            )


class StructSample(object):
    def __init__(self, root_id, offset, size):
        self.size = size
        self.offset = offset
        self.root_id = root_id

    def __reduce__(self):
        # make this class serializable for Ray
        return StructSample, (self.root_id, self.offset, self.size,)


CORE_MUTATOR: CoreMutator = None


def init(for_format: FORMAT):
    global CORE_MUTATOR

    template_path = f'{os.path.dirname(os.path.abspath(__file__))}/templates/{for_format.name}.bt'
    CORE_MUTATOR = CoreMutator(template_path, for_format, SmartFieldSelector())


def get_instance():
    global CORE_MUTATOR
    return CORE_MUTATOR

# def record_event(**kwargs):
#     with open("gmutator-events.txt", "a") as f:
#         # pid = "pid: %s," % os.getpid()
#         f.write(str(kwargs) + "\n")
