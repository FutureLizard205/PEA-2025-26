from contextlib import contextmanager
import sys, os

@contextmanager
def suppress_output():
    """
    Silence almost everything printed to stdout/stderr (Python-level and native C-level).
    Use around the noisy calls:
        with suppress_output():
            ... noisy code ...
    Notes:
    - Cross-platform (uses os.devnull).
    - Flushes streams before/after to avoid truncation.
    - Will affect the whole process (other threads will be redirected too).
    """
    devnull_fd = None
    saved_stdout_fd = None
    saved_stderr_fd = None
    try:
        # Flush Python-level buffers
        try:
            sys.stdout.flush()
        except Exception:
            pass
        try:
            sys.stderr.flush()
        except Exception:
            pass

        # Open a handle to the null device
        devnull_fd = os.open(os.devnull, os.O_RDWR)

        # Save original file descriptors for stdout(1) and stderr(2)
        saved_stdout_fd = os.dup(1)
        saved_stderr_fd = os.dup(2)

        # Duplicate devnull over stdout/stderr
        os.dup2(devnull_fd, 1)
        os.dup2(devnull_fd, 2)

        # Also replace Python objects so prints/readers in Python see the change
        _old_stdout = sys.stdout
        _old_stderr = sys.stderr
        sys.stdout = open(os.devnull, "w")
        sys.stderr = open(os.devnull, "w")

        yield

    finally:
        # Flush and restore Python-level streams first
        try:
            sys.stdout.flush()
        except Exception:
            pass
        try:
            sys.stderr.flush()
        except Exception:
            pass

        # Restore fds (this restores native stdout/stderr)
        if saved_stdout_fd is not None:
            os.dup2(saved_stdout_fd, 1)
        if saved_stderr_fd is not None:
            os.dup2(saved_stderr_fd, 2)

        # Close duplicated fds
        if devnull_fd is not None:
            try:
                os.close(devnull_fd)
            except Exception:
                pass
        if saved_stdout_fd is not None:
            try:
                os.close(saved_stdout_fd)
            except Exception:
                pass
        if saved_stderr_fd is not None:
            try:
                os.close(saved_stderr_fd)
            except Exception:
                pass

        # Restore Python-level objects
        try:
            sys.stdout.close()
        except Exception:
            pass
        try:
            sys.stderr.close()
        except Exception:
            pass
        # restore to real file objects (best-effort)
        sys.stdout = _old_stdout
        sys.stderr = _old_stderr
