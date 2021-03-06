"""Flow for building a disk image."""

from collections import deque
from contextlib import ExitStack
from logging import getLogger


log = getLogger('ubuntu-image')


class State:
    def __init__(self):
        # Variables which manage state transitions.
        self._next = deque()
        self._debug_step = 1
        # Manage all resources so they get cleaned up whenever the state
        # machine exits for any reason.
        self.resources = ExitStack()

    def close(self):
        # Transfer all resources to a new ExitStack, and release them from
        # there.  That way, if .close() gets called more than once, only the
        # first call will release the resources, while subsequent ones will
        # no-op.
        self.resources.pop_all().close()

    def __enter__(self):
        return self

    def __exit__(self, *exception):
        self.close()
        # Don't suppress any exceptions.
        return False

    def __del__(self):
        self.close()

    def __iter__(self):
        return self

    def _pop(self):
        step = self._next.popleft()
        # step could be a partial or a method.
        name = getattr(step, 'func', step).__name__
        log.debug('-> [{:2}] {}'.format(self._debug_step, name))
        return step, name

    def __next__(self):
        try:
            step, name = self._pop()
            step()
            self._debug_step += 1
        except IndexError:
            # Do not chain the exception.
            self.close()
            raise StopIteration from None
        except:
            log.exception('uncaught exception in state machine')
            self.close()
            raise

    def run_thru(self, stop_after):
        """Partially run the state machine.

        Note that any resources maintained by this state machine are
        *not* automatically cleaned up when .run_thru() completes,
        unless an exception occurrs, because execution can be continued.
        Call .close() explicitly to release the resources.

        :param stop_after: Name of method to run the state machine
            through.  In other words, the state machine runs until the
            named method completes.
        """
        while True:
            try:
                step, name = self._pop()
            except (StopIteration, IndexError):
                # We're done.
                break
            try:
                step()
            except:
                self.close()
                raise
            self._debug_step += 1
            if name == stop_after:
                break

    def run_until(self, stop_before):
        """Partially run the state machine.

        Note that any resources maintained by this state machine are
        *not* automatically cleaned up when .run_until() completes,
        unless an exception occurs, because execution can be continued.
        Call .close() explicitly to release the resources.

        :param stop_before: Name of method that the state machine is run
            until the method is reached.  Unlike `run_thru()` the named
            method is not run.
        """
        while True:
            try:
                step, name = self._pop()
            except (StopIteration, IndexError):
                # We're done.
                break
            if name == stop_before:
                # Stop executing, but not before we push the last state back
                # onto the deque.  Otherwise, resuming the state machine would
                # skip this step.
                self._next.appendleft(step)
                break
            try:
                step()
            except:
                self.close()
                raise
            self._debug_step += 1
