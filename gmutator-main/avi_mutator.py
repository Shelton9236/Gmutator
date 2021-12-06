import cProfile
import random

import core
import core.core_mutator as mu
from core.debug.timeout import timeout

# profiler = cProfile.Profile() # for debug only

OP_NAME_BYTES = b'op:avimu'
OP_NAME = OP_NAME_BYTES.decode("utf-8")

def init(seed):
    """
    Called once when AFLFuzz starts up. Used to seed our RNG.

    @type seed: int
    @param seed: A 32-bit random value
    """
    # global profiler
    # profiler.enable()
    random.seed(seed)
    mu.init(core.FORMAT.AVI)


def deinit():
    """
    Called once when AFLFuzz terminates. Only useful in C/C++.
    """
    # global profiler
    # profiler.disable()
    # stats = pstats.Stats(profiler).sort_stats('cumtime')
    # stats.print_stats()
    mu.get_instance().deinit()


@timeout(10)
def queue_get(filename):
    '''
    Called at the beginning of each fuzz iteration to determine whether the
    test case should be fuzzed

    @type filename: str
    @param filename: File name of the test case in the current queue entry

    @rtype: bool
    @return: Return True if the custom mutator decides to fuzz the test case,
        and False otherwise
    '''
    return mu.get_instance().eval_input(filename)


# debug only
# def fuzz_count(buf):
#     return 10

@timeout(10)
def havoc_mutation(buf, max_size):
    return mu.get_instance().get_havoc_mutation(buf)


def havoc_mutation_probability():
    return 100


@timeout(10)
def fuzz(buf, add_buf, max_size):
    """
    Called per fuzzing iteration.

    @type buf: bytearray
    @param buf: The buffer that should be mutated.

    @type add_buf: bytearray
    @param add_buf: A second buffer that can be used as mutation source.

    @type max_size: int
    @param max_size: Maximum size of the mutated output. The mutation must not
        produce data larger than max_size.

    @rtype: bytearray
    @return: A new bytearray containing the mutated data
    """
    if not mu.get_instance().feedback_received:
        mu.get_instance().receive_feedback(core.Feedback.BORING)
    return mu.get_instance().get_mutation(buf)


def describe(max_description_length):
    return OP_NAME_BYTES


def queue_new_entry(filename_new_queue, filename_orig_queue):
    '''
    Called after adding a new test case to the queue

    @type filename_new_queue: str
    @param filename_new_queue: File name of the new queue entry

    @type filename_orig_queue: str
    @param filename_orig_queue: File name of the original queue entry
    '''
    if filename_orig_queue is None or OP_NAME not in filename_new_queue:
        return

    with open(filename_new_queue, 'rb') as f:
        new_seed = f.read()

    # if 'crash' in filename_new_queue:
    #     feedback = core.Feedback.NEW_CRASH
    # elif 'hang' in filename_new_queue:
    #     feedback = core.Feedback.NEW_HANG
    if '+cov' in filename_new_queue:
        feedback = core.Feedback.NEW_COV
    else:
        feedback = core.Feedback.HIT_COUNT

    mu.get_instance().receive_feedback(feedback, new_seed)

# need to evaluate trim strategy
# @timeout(10)
# def init_trim(buf):
#     return mu.get_instance().trim_helper.init_trim(buf)
#
# @timeout(10)
# def trim():
#     return mu.get_instance().trim_helper.trim()
#
# @timeout(10)
# def post_trim(success):
#     return mu.get_instance().trim_helper.post_trim(success)
